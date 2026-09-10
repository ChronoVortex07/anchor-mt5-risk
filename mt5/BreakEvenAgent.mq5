#property strict
#property version "0.10"
#property description "Telegram risk agent: hedging BE+ / bounded gross-volume close. Demo validation required."
#include "Include/RiskAgent/Protocol.mqh"
#include "Include/RiskAgent/HttpClient.mqh"
#include "Include/RiskAgent/CredentialStore.mqh"
#include "Include/RiskAgent/Executor.mqh"

input string ApiUrl="https://api.example.com";
input string PairingCode="";
input bool ExecutionEnabled=false;
input int BEBufferPoints=0; // Local-only BE+ estimate; never supplied remotely.
input int MaxDeviationPoints=20;

string BootID="";
string AgentID="",AgentSecret="",Installation="",BoundServer="",BoundPath="";
long BoundLogin=0;
string PendingResult="",PendingID="";
bool Fatal=false;
int LockHandle=INVALID_HANDLE;
ulong NextPoll=0;
int Backoff=1000;
string Api="";

string BaseState() {
   return "\"protocol_version\":1,\"session_id\":"+Q(BootID)+",\"installation_id\":"+Q(Installation)+",\"ea_version\":\"0.10\",\"account\":"+AccountJSON();
}
bool Journal(string state,string id,string result,bool execution) {
   return SaveFileText("journal.json","{\"state\":"+Q(state)+",\"id\":"+Q(id)+",\"execution\":"+B(execution)+",\"result\":"+Q(result)+"}");
}
bool LoadCredentials() {
   string raw; if(!ReadFileText("credentials.json",raw)) return false;
   Json j; if(!j.Parse(raw)) { Fatal=true; return false; }
   AgentID=j.Str(0,"agent_id"); AgentSecret=j.Str(0,"agent_secret"); Installation=j.Str(0,"installation_id");
   BoundLogin=StringToInteger(j.Str(0,"login")); BoundServer=j.Str(0,"server"); BoundPath=j.Str(0,"path");
   if(!UUIDValid(AgentID) || !UUIDValid(Installation) || StringLen(AgentSecret)!=43 || j.Str(0,"api")!=Api ||
      BoundPath!=HashText(TerminalInfoString(TERMINAL_DATA_PATH))) { Fatal=true; return false; }
   for(int i=0;i<StringLen(AgentSecret);i++) if(StringFind("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-",StringSubstr(AgentSecret,i,1))<0) { Fatal=true; return false; }
   return true;
}
bool PairAgent() {
   if(PairingCode=="") return false;
   string response;
   int status=PostJSON(Api,"/v1/agent/pair","{"+BaseState()+",\"pairing_code\":"+Q(PairingCode)+"}","","",response);
   if(status!=200) { Print("Pairing failed. HTTP ",status,". If response was lost, revoke in dashboard and use a new code."); return false; }
   Json j; if(!j.Parse(response) || j.Num(0,"protocol_version")!=1) return false;
   string id=j.Str(0,"agent_id"),secret=j.Str(0,"agent_secret");
   if(!UUIDValid(id) || StringLen(secret)!=43) return false;
   BoundLogin=AccountInfoInteger(ACCOUNT_LOGIN); BoundServer=AccountInfoString(ACCOUNT_SERVER);
   BoundPath=HashText(TerminalInfoString(TERMINAL_DATA_PATH));
   string credential="{\"agent_id\":"+Q(id)+",\"agent_secret\":"+Q(secret)+",\"installation_id\":"+Q(Installation)+
                     ",\"login\":"+Q(IntegerToString(BoundLogin))+",\"server\":"+Q(BoundServer)+",\"path\":"+Q(BoundPath)+",\"api\":"+Q(Api)+"}";
   if(!SaveFileText("credentials.json",credential)) { Fatal=true; return false; }
   AgentID=id; AgentSecret=secret; Print("Agent paired. ExecutionEnabled=",ExecutionEnabled); return true;
}
int OnInit() {
   Api=ApiUrl; while(StringLen(Api)>0 && StringSubstr(Api,StringLen(Api)-1)=="/") Api=StringSubstr(Api,0,StringLen(Api)-1);
   if(StringFind(Api,"https://")!=0 || StringFind(Api,"@")>=0 || StringFind(Api,"?")>=0 || StringFind(Api,"#")>=0 ||
      StringFind(Api,"\r")>=0 || StringFind(Api,"\n")>=0 || BEBufferPoints<0 || BEBufferPoints>10000 || MaxDeviationPoints<0 || MaxDeviationPoints>1000) return INIT_PARAMETERS_INCORRECT;
   FolderCreate("RiskAgent");
   // Exclusive local file lock. Multiple charts in this terminal cannot execute concurrently.
   LockHandle=FileOpen(StorePrefix+"instance.lock",FILE_WRITE|FILE_BIN);
   if(LockHandle==INVALID_HANDLE) { Print("Another RiskAgent instance is running, or storage unavailable."); return INIT_FAILED; }
   MathSrand((int)GetTickCount());
   BootID=NewInstallation(); if(!UUIDValid(BootID)) return INIT_FAILED;
   if(!LoadCredentials()) {
      if(Fatal) { Print("Invalid/copied credential file; execution blocked. Re-pair explicitly."); return INIT_FAILED; }
      if(!ReadFileText("installation.txt",Installation)) {
         Installation=NewInstallation(); if(!UUIDValid(Installation) || !SaveFileText("installation.txt",Installation)) return INIT_FAILED;
      }
      if(!PairAgent()) return INIT_FAILED;
   }
   ReadFileText("recent.txt",RecentIDs);
   string raw;
   if(ReadFileText("journal.json",raw) && raw!="") {
      Json j; if(!j.Parse(raw) || !UUIDValid(j.Str(0,"id"))) { Print("Corrupt journal. Reconcile before restarting."); return INIT_FAILED; }
      PendingID=j.Str(0,"id");
      if(j.Str(0,"state")=="DONE") PendingResult=j.Str(0,"result");
      else if(j.Str(0,"state")=="STARTED") {
         PendingResult=j.Str(0,"execution")=="true"?UncertainResult(PendingID):
                       "{\"command_id\":"+Q(PendingID)+",\"status\":\"FAILED\",\"summary\":{\"code\":\"PREVIEW_INTERRUPTED\"},\"position_results\":[]}";
         if(!Journal("DONE",PendingID,PendingResult,j.Str(0,"execution")=="true")) return INIT_FAILED;
      } else return INIT_FAILED;
   }
   if(!EventSetMillisecondTimer(250)) return INIT_FAILED;
   Print("RiskAgent ready; execution=",ExecutionEnabled,"; BE+ buffer points=",BEBufferPoints);
   return INIT_SUCCEEDED;
}
void OnDeinit(const int reason) { EventKillTimer(); if(LockHandle!=INVALID_HANDLE) FileClose(LockHandle); }
void OnTimer() {
   if(Fatal || GetTickCount64()<NextPoll || AgentID=="") return;
   ulong started=GetTickCount64();
   string response;
   string body="{"+BaseState()+",\"terminal\":{\"connected\":"+B((bool)TerminalInfoInteger(TERMINAL_CONNECTED))+"},\"execution_enabled\":"+B(ExecutionEnabled)+",\"result\":"+(PendingResult==""?"null":PendingResult)+"}";
   int status=PostJSON(Api,"/v1/agent/poll",body,AgentID,AgentSecret,response);
   if(status!=200) { Backoff=(int)MathMin(30000,Backoff*2); NextPoll=GetTickCount64()+Backoff+MathRand()%500; Print("Poll unavailable. HTTP ",status); return; }
   Json j;
   if(!j.Parse(response) || j.Kind(j.Get(0,"protocol_version"))!="number" || j.Num(0,"protocol_version")!=1) {
      NextPoll=GetTickCount64()+5000; Print("PROTOCOL_MISMATCH"); return;
   }
   Backoff=1000; NextPoll=GetTickCount64()+(ulong)MathMax(750,MathMin(5000,j.Num(0,"poll_after_ms")))+MathRand()%200;
   if(PendingID!="" && j.Str(0,"ack_result_id")==PendingID) {
      if(!Remember(PendingID)) { Fatal=true; return; }
      if(!FileDelete(StorePrefix+"journal.json")) { Fatal=true; return; }
      PendingID=""; PendingResult="";
   }
   if(j.Str(0,"code")!="OK" || !AccountMatches(BoundLogin,BoundServer)) { Print("Agent blocked: ",j.Str(0,"code")); return; }
   int node=j.Get(0,"command"); if(j.Kind(node)=="null") return;
   if(PendingResult!="") return;
   RiskCommand command;
   if(!ReadCommand(j,node,started,command)) { Print("INVALID_OR_EXPIRED_COMMAND"); return; }
   if(Seen(command.id)) { Print("REPLAY_REJECTED ",command.id); return; }
   RiskPlan plan; MakePlan(command,BEBufferPoints,plan);
   if(!Journal("STARTED",command.id,"",!command.preview)) { Fatal=true; Print("JOURNAL_WRITE_FAILED"); return; }
   string result=BuildResult(command,plan,BEBufferPoints,ExecutionEnabled,BoundLogin,BoundServer,MaxDeviationPoints);
   if(!Journal("DONE",command.id,result,!command.preview)) { Fatal=true; Print("JOURNAL_RESULT_WRITE_FAILED; reconcile on restart"); return; }
   PendingID=command.id; PendingResult=result;
   Print("Command evaluated: ",command.id,"; type=",command.type,"; execution=",ExecutionEnabled);
}
