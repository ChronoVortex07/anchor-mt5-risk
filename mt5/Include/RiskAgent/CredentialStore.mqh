#ifndef RISK_STORE
#define RISK_STORE
#include "Json.mqh"
string StorePrefix="RiskAgent\\";
bool ReadFileText(string name,string &value) {
   int h=FileOpen(StorePrefix+name,FILE_READ|FILE_TXT|FILE_ANSI,0,CP_UTF8);
   if(h==INVALID_HANDLE) return false;
   value="";
   while(!FileIsEnding(h)) value+=FileReadString(h);
   FileClose(h); return true;
}
bool SaveFileText(string name,string value) {
   string tmp=StorePrefix+name+".tmp";
   int h=FileOpen(tmp,FILE_WRITE|FILE_TXT|FILE_ANSI,0,CP_UTF8);
   if(h==INVALID_HANDLE) return false;
   uint n=FileWriteString(h,value); FileFlush(h); FileClose(h);
   if(n==0 || !FileMove(tmp,0,StorePrefix+name,FILE_REWRITE)) return false;
   string check; return ReadFileText(name,check) && check==value;
}
string HashText(string text) {
   uchar data[],key[],result[]; StringToCharArray(text,data,0,WHOLE_ARRAY,CP_UTF8); ArrayResize(data,ArraySize(data)-1);
   if(CryptEncode(CRYPT_HASH_SHA256,data,key,result)<=0) return "";
   string out=""; for(int i=0;i<ArraySize(result);i++) out+=StringFormat("%02x",result[i]); return out;
}
string NewInstallation() {
   // Installation ID is an identifier, never an authentication secret.
   string seed=TerminalInfoString(TERMINAL_DATA_PATH)+IntegerToString(AccountInfoInteger(ACCOUNT_LOGIN))+
               IntegerToString((long)GetMicrosecondCount())+IntegerToString((long)TimeLocal())+IntegerToString(MathRand());
   string h=HashText(seed); if(StringLen(h)!=64) return "";
   return StringSubstr(h,0,8)+"-"+StringSubstr(h,8,4)+"-4"+StringSubstr(h,13,3)+"-a"+StringSubstr(h,17,3)+"-"+StringSubstr(h,20,12);
}
string UncertainResult(string id) { return "{\"command_id\":"+Q(id)+",\"status\":\"UNCERTAIN\",\"summary\":{\"code\":\"EXECUTION_UNCERTAIN\"},\"position_results\":[]}"; }
// STARTED is flushed before the first broker request. DONE holds the exact result.
// A single active journal is retained until server acknowledgement. Recent IDs are
// retained separately so an acknowledged execution cannot be replayed.
string RecentIDs="";
bool Seen(string id) { return StringFind("|"+RecentIDs+"|","|"+id+"|")>=0; }
bool Remember(string id) {
   if(Seen(id)) return true;
   string next=RecentIDs+(RecentIDs==""?"":"|")+id;
   if(StringLen(next)>37*128) next=StringSubstr(next,StringLen(next)-37*128+1);
   if(!SaveFileText("recent.txt",next)) return false;
   RecentIDs=next; return true;
}
#endif
