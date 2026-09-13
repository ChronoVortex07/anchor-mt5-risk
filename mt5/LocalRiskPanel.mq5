#property strict
#property version "0.10"
#property description "Local-only native panel for break-even protection and bounded exposure reduction."

#include "Include/RiskAgent/Executor.mqh"

input bool ExecutionEnabled=false;       // Leave false while learning the panel.
input bool AllowLiveAccount=false;       // Deliberate second opt-in for real-money accounts.
input int BEBufferPoints=0;               // 0 = entry; positive values move beyond entry.
input int MaxDeviationPoints=20;
input int ConfirmationSeconds=15;
input int PanelX=16;
input int PanelY=28;

#define PANEL_WIDTH 390
#define PANEL_HEIGHT 402

color COLOR_PANEL=C'15,23,42';
color COLOR_BORDER=C'51,65,85';
color COLOR_TEXT=C'226,232,240';
color COLOR_MUTED=C'148,163,184';
color COLOR_ACCENT=C'52,211,153';
color COLOR_BLUE=C'56,189,248';
color COLOR_WARN=C'251,191,36';
color COLOR_DANGER=C'248,113,113';
color COLOR_BUTTON=C'30,41,59';
color COLOR_DISABLED=C'71,85,105';

string Prefix="";
long BoundLogin=0;
string BoundServer="";
double SelectedFraction=0.50;
bool HasPending=false;
bool Executing=false;
RiskCommand PendingCommand;
RiskPlan PendingPlan;
ulong PendingUntil=0;

string Name(string suffix) { return Prefix+suffix; }

bool CreateBackground() {
   string name=Name("Background");
   if(!ObjectCreate(0,name,OBJ_RECTANGLE_LABEL,0,0,0)) return false;
   ObjectSetInteger(0,name,OBJPROP_CORNER,CORNER_LEFT_UPPER);
   ObjectSetInteger(0,name,OBJPROP_XDISTANCE,PanelX);
   ObjectSetInteger(0,name,OBJPROP_YDISTANCE,PanelY);
   ObjectSetInteger(0,name,OBJPROP_XSIZE,PANEL_WIDTH);
   ObjectSetInteger(0,name,OBJPROP_YSIZE,PANEL_HEIGHT);
   ObjectSetInteger(0,name,OBJPROP_BGCOLOR,COLOR_PANEL);
   ObjectSetInteger(0,name,OBJPROP_COLOR,COLOR_BORDER);
   ObjectSetInteger(0,name,OBJPROP_BORDER_TYPE,BORDER_FLAT);
   ObjectSetInteger(0,name,OBJPROP_BACK,false);
   ObjectSetInteger(0,name,OBJPROP_SELECTABLE,false);
   ObjectSetInteger(0,name,OBJPROP_HIDDEN,true);
   ObjectSetInteger(0,name,OBJPROP_ZORDER,0);
   return true;
}

bool CreateLabel(string suffix,int x,int y,string text,int size,color foreground) {
   string name=Name(suffix);
   if(!ObjectCreate(0,name,OBJ_LABEL,0,0,0)) return false;
   ObjectSetInteger(0,name,OBJPROP_CORNER,CORNER_LEFT_UPPER);
   ObjectSetInteger(0,name,OBJPROP_ANCHOR,ANCHOR_LEFT_UPPER);
   ObjectSetInteger(0,name,OBJPROP_XDISTANCE,PanelX+x);
   ObjectSetInteger(0,name,OBJPROP_YDISTANCE,PanelY+y);
   ObjectSetInteger(0,name,OBJPROP_COLOR,foreground);
   ObjectSetInteger(0,name,OBJPROP_FONTSIZE,size);
   ObjectSetInteger(0,name,OBJPROP_SELECTABLE,false);
   ObjectSetInteger(0,name,OBJPROP_HIDDEN,true);
   ObjectSetInteger(0,name,OBJPROP_ZORDER,1);
   ObjectSetString(0,name,OBJPROP_FONT,"Segoe UI");
   ObjectSetString(0,name,OBJPROP_TEXT,text);
   return true;
}

bool CreateRule(string suffix,int y) {
   string name=Name(suffix);
   if(!ObjectCreate(0,name,OBJ_RECTANGLE_LABEL,0,0,0)) return false;
   ObjectSetInteger(0,name,OBJPROP_CORNER,CORNER_LEFT_UPPER);
   ObjectSetInteger(0,name,OBJPROP_XDISTANCE,PanelX+14);
   ObjectSetInteger(0,name,OBJPROP_YDISTANCE,PanelY+y);
   ObjectSetInteger(0,name,OBJPROP_XSIZE,PANEL_WIDTH-28);
   ObjectSetInteger(0,name,OBJPROP_YSIZE,1);
   ObjectSetInteger(0,name,OBJPROP_BGCOLOR,COLOR_BORDER);
   ObjectSetInteger(0,name,OBJPROP_COLOR,COLOR_BORDER);
   ObjectSetInteger(0,name,OBJPROP_SELECTABLE,false);
   ObjectSetInteger(0,name,OBJPROP_HIDDEN,true);
   ObjectSetInteger(0,name,OBJPROP_ZORDER,1);
   return true;
}

bool CreateButton(string suffix,int x,int y,int width,int height,string text,color background) {
   string name=Name(suffix);
   if(!ObjectCreate(0,name,OBJ_BUTTON,0,0,0)) return false;
   ObjectSetInteger(0,name,OBJPROP_CORNER,CORNER_LEFT_UPPER);
   ObjectSetInteger(0,name,OBJPROP_XDISTANCE,PanelX+x);
   ObjectSetInteger(0,name,OBJPROP_YDISTANCE,PanelY+y);
   ObjectSetInteger(0,name,OBJPROP_XSIZE,width);
   ObjectSetInteger(0,name,OBJPROP_YSIZE,height);
   ObjectSetInteger(0,name,OBJPROP_BGCOLOR,background);
   ObjectSetInteger(0,name,OBJPROP_COLOR,COLOR_TEXT);
   ObjectSetInteger(0,name,OBJPROP_BORDER_COLOR,COLOR_BORDER);
   ObjectSetInteger(0,name,OBJPROP_FONTSIZE,9);
   ObjectSetInteger(0,name,OBJPROP_STATE,false);
   ObjectSetInteger(0,name,OBJPROP_SELECTABLE,false);
   ObjectSetInteger(0,name,OBJPROP_HIDDEN,true);
   ObjectSetInteger(0,name,OBJPROP_ZORDER,2);
   ObjectSetString(0,name,OBJPROP_FONT,"Segoe UI Semibold");
   ObjectSetString(0,name,OBJPROP_TEXT,text);
   return true;
}

void SetLabel(string suffix,string text,color foreground) {
   ObjectSetString(0,Name(suffix),OBJPROP_TEXT,text);
   ObjectSetInteger(0,Name(suffix),OBJPROP_COLOR,foreground);
}

void SetButtonColor(string suffix,color background) {
   ObjectSetInteger(0,Name(suffix),OBJPROP_BGCOLOR,background);
   ObjectSetInteger(0,Name(suffix),OBJPROP_STATE,false);
}

string Lots(double value) {
   string result=DoubleToString(value,8);
   while(StringLen(result)>0 && StringSubstr(result,StringLen(result)-1)=="0")
      result=StringSubstr(result,0,StringLen(result)-1);
   if(StringLen(result)>0 && StringSubstr(result,StringLen(result)-1)==".")
      result=StringSubstr(result,0,StringLen(result)-1);
   return result==""?"0":result;
}

string SideTitle(string side) {
   if(side=="BUY") return "BUY positions";
   if(side=="SELL") return "SELL positions";
   return "BUY + SELL positions";
}

bool IsRealAccount() {
   return AccountInfoInteger(ACCOUNT_TRADE_MODE)==ACCOUNT_TRADE_MODE_REAL;
}

string MaskedLogin() {
   string login=IntegerToString(BoundLogin);
   int start=StringLen(login)-4;
   if(start<0) start=0;
   return "..."+StringSubstr(login,start);
}

string ExecutionGate() {
   if(IsRealAccount() && !AllowLiveAccount) return "LIVE ACCOUNT LOCKED";
   if(!ExecutionEnabled) return "PREVIEW ONLY";
   return PermissionError();
}

void UpdateMode() {
   string gate=ExecutionGate();
   color foreground=gate=="OK"?COLOR_ACCENT:(gate=="PREVIEW ONLY"?COLOR_WARN:COLOR_DANGER);
   SetLabel("Mode",gate,foreground);
}

void UpdateExposure() {
   double buy=0,sell=0,protected_volume=0;
   int positions=0;
   Quote quote;
   bool quote_ok=ReadQuote(_Symbol,quote);
   for(int i=0;i<PositionsTotal();i++) {
      Layer layer;
      if(!ReadLayer(PositionGetTicket(i),layer) || layer.symbol!=_Symbol) continue;
      positions++;
      if(layer.side=="BUY") buy+=layer.volume; else sell+=layer.volume;
      if(quote_ok && Protected(layer,StopFor(layer,quote,BEBufferPoints)))
         protected_volume+=layer.volume;
   }
   SetLabel("Account",_Symbol+"  |  MT5 "+MaskedLogin(),COLOR_MUTED);
   SetLabel("Exposure","Open exposure   BUY "+Lots(buy)+"   SELL "+Lots(sell)+"   ("+IntegerToString(positions)+" positions)",COLOR_TEXT);
   SetLabel("Protected","Protected at configured BE   "+(quote_ok?Lots(protected_volume):"quote unavailable")+" lots",COLOR_MUTED);
   UpdateMode();
}

void UpdateFractionButtons() {
   SetButtonColor("Pct25",MathAbs(SelectedFraction-0.25)<1e-9?COLOR_BLUE:COLOR_BUTTON);
   SetButtonColor("Pct50",MathAbs(SelectedFraction-0.50)<1e-9?COLOR_BLUE:COLOR_BUTTON);
   SetButtonColor("Pct100",MathAbs(SelectedFraction-1.00)<1e-9?COLOR_BLUE:COLOR_BUTTON);
}

void SetPendingButtons() {
   SetButtonColor("Confirm",HasPending?COLOR_ACCENT:COLOR_DISABLED);
   SetButtonColor("Cancel",HasPending?COLOR_BUTTON:COLOR_DISABLED);
}

void ClearPending(string message,color foreground) {
   HasPending=false;
   PendingUntil=0;
   SetLabel("PreviewTitle",message,foreground);
   SetLabel("PreviewVolume","Choose an action above to calculate a fresh preview.",COLOR_MUTED);
   SetLabel("PreviewDetail","Nothing is sent outside this MT5 terminal.",COLOR_MUTED);
   SetLabel("PreviewWarning","",COLOR_WARN);
   SetPendingButtons();
}

void ChooseFraction(double fraction) {
   SelectedFraction=fraction;
   UpdateFractionButtons();
   if(HasPending)
      ClearPending("Target changed — calculate a new preview",COLOR_WARN);
}

void LogPlan(RiskCommand &command,RiskPlan &plan) {
   Print("ANCHOR LOCAL PREVIEW | symbol=",command.symbol," action=",command.close?"CLOSE":"BREAK_EVEN",
         " side=",command.side," target=",Lots(plan.target)," planned=",Lots(plan.planned));
   for(int i=0;i<plan.count;i++)
      Print("  ticket=",plan.items[i].layer.ticket," side=",plan.items[i].layer.side,
            " volume=",Lots(plan.items[i].volume)," code=",plan.items[i].code,
            command.close?"":" stop="+DoubleToString(plan.items[i].stop,8));
}

bool SamePlan(RiskPlan &left,RiskPlan &right) {
   if(left.code!=right.code || left.side!=right.side || left.count!=right.count ||
      MathAbs(left.total-right.total)>1e-9 || MathAbs(left.target-right.target)>1e-9 ||
      MathAbs(left.already-right.already)>1e-9 || MathAbs(left.planned-right.planned)>1e-9)
      return false;
   for(int i=0;i<left.count;i++) {
      if(left.items[i].layer.ticket!=right.items[i].layer.ticket ||
         left.items[i].layer.identifier!=right.items[i].layer.identifier ||
         left.items[i].code!=right.items[i].code ||
         MathAbs(left.items[i].volume-right.items[i].volume)>1e-9 ||
         MathAbs(left.items[i].stop-right.items[i].stop)>1e-9)
         return false;
   }
   return true;
}

void DisplayPreview(RiskCommand &command,RiskPlan &plan,string heading="Preview") {
   string action=command.close?"Close worst-cost volume":"Move stops to configured BE";
   SetLabel("PreviewTitle",heading+" — "+action,COLOR_TEXT);
   SetLabel("PreviewVolume",SideTitle(command.side)+"  |  "+IntegerToString((int)MathRound(command.fraction*100))+"% target: "+Lots(plan.target)+" lots",COLOR_TEXT);
   if(command.close)
      SetLabel("PreviewDetail","Planned: "+Lots(plan.planned)+"   Gross: "+Lots(plan.total)+"   BUY: "+Lots(plan.buy)+"   SELL: "+Lots(plan.sell),COLOR_MUTED);
   else
      SetLabel("PreviewDetail","Planned: "+Lots(plan.planned)+"   Already protected: "+Lots(plan.already)+"   Gross: "+Lots(plan.total),COLOR_MUTED);
   SetLabel("PreviewWarning",command.close?"Closing one hedge leg can increase net directional exposure.":"Stops can slip or gap; BE is not guaranteed profit.",COLOR_WARN);
   SetPendingButtons();
}

void Preview(bool close,string side) {
   if(Executing) return;
   RiskCommand command;
   command.id="local-preview";
   command.type=close?"REDUCE_EXPOSURE":"PROTECT_BREAKEVEN";
   command.symbol=_Symbol;
   command.side=side;
   command.fraction=SelectedFraction;
   command.deadline=GetTickCount64()+(ulong)(ConfirmationSeconds*1000);
   command.preview=true;
   command.close=close;
   RiskPlan plan;
   if(!MakePlan(command,BEBufferPoints,plan)) {
      ClearPending("Preview unavailable — "+plan.code,COLOR_DANGER);
      Print("ANCHOR LOCAL PREVIEW REJECTED | ",plan.code," | symbol=",_Symbol," side=",side);
      ChartRedraw();
      return;
   }
   command.preview=false;
   PendingCommand=command;
   PendingPlan=plan;
   PendingUntil=command.deadline;
   HasPending=true;
   DisplayPreview(command,plan);
   LogPlan(command,plan);
   ChartRedraw();
}

void ShowExecutionResult(string raw) {
   Json json;
   if(!json.Parse(raw)) {
      SetLabel("PreviewTitle","Execution finished — unreadable local result",COLOR_DANGER);
      SetLabel("PreviewVolume","Inspect the Experts log before taking another action.",COLOR_WARN);
      return;
   }
   int summary=json.Get(0,"summary");
   string status=json.Str(0,"status");
   string code=json.Str(summary,"code");
   double confirmed=json.Num(summary,"confirmed_volume");
   int changed=(int)json.Num(summary,"changed_positions");
   color foreground=status=="SUCCEEDED"?COLOR_ACCENT:(status=="PARTIAL"?COLOR_WARN:COLOR_DANGER);
   SetLabel("PreviewTitle","Execution "+status+" — "+code,foreground);
   SetLabel("PreviewVolume","Broker-confirmed: "+Lots(confirmed)+" lots   Changed positions: "+IntegerToString(changed),COLOR_TEXT);
   SetLabel("PreviewDetail","The panel recalculated positions immediately before execution.",COLOR_MUTED);
   SetLabel("PreviewWarning",status=="UNCERTAIN"?"Do not repeat blindly. Reconcile against broker history.":"See the Experts log for ticket-level results.",status=="UNCERTAIN"?COLOR_DANGER:COLOR_WARN);
}

void ConfirmPending() {
   if(Executing || !HasPending) return;
   if(GetTickCount64()>=PendingUntil) {
      ClearPending("Preview expired — calculate it again",COLOR_WARN);
      return;
   }
   string gate=ExecutionGate();
   if(gate!="OK") {
      SetLabel("PreviewTitle","Execution blocked — "+gate,COLOR_DANGER);
      SetLabel("PreviewWarning","Change EA Inputs deliberately, then calculate a new preview.",COLOR_WARN);
      HasPending=false;
      SetPendingButtons();
      return;
   }
   if(!AccountMatches(BoundLogin,BoundServer)) {
      ClearPending("Execution blocked — ACCOUNT CHANGED",COLOR_DANGER);
      return;
   }
   Executing=true;
   RiskCommand command=PendingCommand;
   command.id="local-"+IntegerToString((long)TimeLocal())+"-"+IntegerToString((long)GetTickCount64());
   command.deadline=GetTickCount64()+10000;
   RiskPlan current;
   if(!MakePlan(command,BEBufferPoints,current)) {
      Executing=false;
      ClearPending("Execution cancelled — "+current.code,COLOR_DANGER);
      return;
   }
   if(!SamePlan(PendingPlan,current)) {
      PendingPlan=current;
      PendingCommand=command;
      PendingUntil=GetTickCount64()+(ulong)(ConfirmationSeconds*1000);
      PendingCommand.deadline=PendingUntil;
      HasPending=true;
      Executing=false;
      DisplayPreview(PendingCommand,PendingPlan,"Positions changed; review refreshed preview");
      LogPlan(PendingCommand,PendingPlan);
      ChartRedraw();
      return;
   }
   HasPending=false;
   SetPendingButtons();
   string result=BuildResult(command,current,BEBufferPoints,true,BoundLogin,BoundServer,MaxDeviationPoints);
   Print("ANCHOR LOCAL RESULT | ",result);
   ShowExecutionResult(result);
   Executing=false;
   UpdateExposure();
   ChartRedraw();
}

bool CreatePanel() {
   if(!CreateBackground()) return false;
   if(!CreateLabel("Title",14,12,"ANCHOR  /  LOCAL RISK PANEL",12,COLOR_TEXT)) return false;
   if(!CreateLabel("Account",14,36,"",9,COLOR_MUTED)) return false;
   if(!CreateLabel("Mode",276,36,"",9,COLOR_WARN)) return false;
   if(!CreateLabel("Exposure",14,62,"",10,COLOR_TEXT)) return false;
   if(!CreateLabel("Protected",14,82,"",9,COLOR_MUTED)) return false;
   if(!CreateRule("Rule1",105)) return false;
   if(!CreateLabel("TargetLabel",14,119,"TARGET VOLUME",8,COLOR_MUTED)) return false;
   if(!CreateButton("Pct25",132,112,70,28,"25%",COLOR_BUTTON)) return false;
   if(!CreateButton("Pct50",208,112,70,28,"50%",COLOR_BLUE)) return false;
   if(!CreateButton("Pct100",284,112,90,28,"100%",COLOR_BUTTON)) return false;
   if(!CreateLabel("ProtectLabel",14,153,"PROTECT STOP LOSS",8,COLOR_MUTED)) return false;
   if(!CreateButton("BeBuy",14,168,176,32,"BE  /  BUY",COLOR_BUTTON)) return false;
   if(!CreateButton("BeSell",198,168,176,32,"BE  /  SELL",COLOR_BUTTON)) return false;
   if(!CreateLabel("CloseLabel",14,213,"REDUCE EXPOSURE  /  WORST COST FIRST",8,COLOR_MUTED)) return false;
   if(!CreateButton("CloseBuy",14,228,116,32,"CLOSE BUY",COLOR_BUTTON)) return false;
   if(!CreateButton("CloseSell",137,228,116,32,"CLOSE SELL",COLOR_BUTTON)) return false;
   if(!CreateButton("CloseBoth",260,228,114,32,"CLOSE BOTH",COLOR_BUTTON)) return false;
   if(!CreateRule("Rule2",275)) return false;
   if(!CreateLabel("PreviewTitle",14,287,"Ready",10,COLOR_ACCENT)) return false;
   if(!CreateLabel("PreviewVolume",14,307,"Choose an action above to calculate a fresh preview.",9,COLOR_MUTED)) return false;
   if(!CreateLabel("PreviewDetail",14,325,"Nothing is sent outside this MT5 terminal.",9,COLOR_MUTED)) return false;
   if(!CreateLabel("PreviewWarning",14,343,"",8,COLOR_WARN)) return false;
   if(!CreateButton("Confirm",14,362,235,28,"CONFIRM EXECUTION",COLOR_DISABLED)) return false;
   if(!CreateButton("Cancel",257,362,117,28,"CANCEL",COLOR_DISABLED)) return false;
   return true;
}

int OnInit() {
   if(BEBufferPoints<0 || BEBufferPoints>10000 || MaxDeviationPoints<0 || MaxDeviationPoints>1000 ||
      ConfirmationSeconds<5 || ConfirmationSeconds>60 || PanelX<0 || PanelY<0)
      return INIT_PARAMETERS_INCORRECT;
   Prefix="AnchorLocal."+IntegerToString((long)ChartID())+".";
   BoundLogin=AccountInfoInteger(ACCOUNT_LOGIN);
   BoundServer=AccountInfoString(ACCOUNT_SERVER);
   if(!CreatePanel()) {
      ObjectsDeleteAll(0,Prefix);
      return INIT_FAILED;
   }
   UpdateFractionButtons();
   SetPendingButtons();
   UpdateExposure();
   if(!EventSetMillisecondTimer(500)) {
      ObjectsDeleteAll(0,Prefix);
      return INIT_FAILED;
   }
   ChartRedraw();
   Print("Anchor Local Risk Panel ready on ",_Symbol,". ExecutionEnabled=",ExecutionEnabled,
         "; AllowLiveAccount=",AllowLiveAccount);
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason) {
   EventKillTimer();
   ObjectsDeleteAll(0,Prefix);
   ChartRedraw();
}

void OnTimer() {
   UpdateExposure();
   if(HasPending) {
      ulong now=GetTickCount64();
      if(now>=PendingUntil) {
         ClearPending("Preview expired — calculate it again",COLOR_WARN);
      } else {
         int seconds=(int)((PendingUntil-now+999)/1000);
         ObjectSetString(0,Name("Confirm"),OBJPROP_TEXT,"CONFIRM EXECUTION  /  "+IntegerToString(seconds)+"s");
      }
   } else {
      ObjectSetString(0,Name("Confirm"),OBJPROP_TEXT,"CONFIRM EXECUTION");
   }
   ChartRedraw();
}

void OnChartEvent(const int id,const long &lparam,const double &dparam,const string &sparam) {
   if(id!=CHARTEVENT_OBJECT_CLICK || StringFind(sparam,Prefix)!=0) return;
   ObjectSetInteger(0,sparam,OBJPROP_STATE,false);
   string action=StringSubstr(sparam,StringLen(Prefix));
   if(action=="Pct25") ChooseFraction(0.25);
   else if(action=="Pct50") ChooseFraction(0.50);
   else if(action=="Pct100") ChooseFraction(1.00);
   else if(action=="BeBuy") Preview(false,"BUY");
   else if(action=="BeSell") Preview(false,"SELL");
   else if(action=="CloseBuy") Preview(true,"BUY");
   else if(action=="CloseSell") Preview(true,"SELL");
   else if(action=="CloseBoth") Preview(true,"BOTH");
   else if(action=="Confirm") ConfirmPending();
   else if(action=="Cancel" && HasPending) ClearPending("Preview cancelled",COLOR_MUTED);
   ChartRedraw();
}
