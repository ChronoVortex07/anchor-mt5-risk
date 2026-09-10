#ifndef RISK_PLANNER
#define RISK_PLANNER
#include "Protocol.mqh"
#define MAX_RISK_POSITIONS 128
struct Layer { ulong ticket; ulong identifier; string symbol; string side; double volume; double entry; double sl; double tp; };
struct Quote { double bid; double ask; double point; double tick; double stops; double freeze; double step; double minimum; double maximum; int digits; };
struct PlanItem { Layer layer; string code; double volume; double stop; };
struct RiskPlan { string code; string side; double total; double target; double already; double planned; double buy; double sell; int count; PlanItem items[MAX_RISK_POSITIONS]; };
bool ReadLayer(ulong ticket,Layer &p) {
   if(!PositionSelectByTicket(ticket)) return false;
   p.ticket=ticket; p.identifier=(ulong)PositionGetInteger(POSITION_IDENTIFIER); p.symbol=PositionGetString(POSITION_SYMBOL);
   p.side=PositionGetInteger(POSITION_TYPE)==POSITION_TYPE_BUY?"BUY":"SELL";
   p.volume=PositionGetDouble(POSITION_VOLUME); p.entry=PositionGetDouble(POSITION_PRICE_OPEN);
   p.sl=PositionGetDouble(POSITION_SL); p.tp=PositionGetDouble(POSITION_TP);
   return p.volume>0 && p.entry>0;
}
bool ReadQuote(string symbol,Quote &q) {
   bool custom=false; if(!SymbolExist(symbol,custom) || custom || !SymbolSelect(symbol,true)) return false;
   MqlTick t; if(!SymbolInfoTick(symbol,t)) return false;
   // A stale quote must not turn a preview into an executable plan.
   long age=(long)TimeTradeServer()-(long)t.time;
   if(age>10 || age< -5) return false;
   q.bid=t.bid; q.ask=t.ask; q.point=SymbolInfoDouble(symbol,SYMBOL_POINT);
   q.tick=SymbolInfoDouble(symbol,SYMBOL_TRADE_TICK_SIZE);
   q.stops=(double)SymbolInfoInteger(symbol,SYMBOL_TRADE_STOPS_LEVEL)*q.point;
   q.freeze=(double)SymbolInfoInteger(symbol,SYMBOL_TRADE_FREEZE_LEVEL)*q.point;
   q.step=SymbolInfoDouble(symbol,SYMBOL_VOLUME_STEP); q.minimum=SymbolInfoDouble(symbol,SYMBOL_VOLUME_MIN);
   q.maximum=SymbolInfoDouble(symbol,SYMBOL_VOLUME_MAX); q.digits=(int)SymbolInfoInteger(symbol,SYMBOL_DIGITS);
   return q.bid>0 && q.ask>=q.bid && q.point>0 && q.tick>0 && q.step>0 && q.minimum>0 && q.maximum>=q.minimum;
}
double StopFor(Layer &p,Quote &q,int buffer) {
   double raw=p.entry+(p.side=="BUY"?1:-1)*buffer*q.point;
   // Tick normalization goes in the protective direction.
   double ticks=raw/q.tick;
   return NormalizeDouble((p.side=="BUY"?MathCeil(ticks-1e-9):MathFloor(ticks+1e-9))*q.tick,q.digits);
}
bool Protected(Layer &p,double stop) { return p.sl>0 && (p.side=="BUY"?p.sl>=stop:p.sl<=stop); }
string StopCode(Layer &p,Quote &q,double stop) {
   if(Protected(p,stop)) return "ALREADY_PROTECTED";
   if(stop<=0 || !MathIsValidNumber(stop)) return "STOP_LEVEL_INVALID";
   double price=p.side=="BUY"?q.bid:q.ask;
   double distance=p.side=="BUY"?price-stop:stop-price;
   if(distance<=0 || distance+1e-9<q.stops) return "SKIPPED_NOT_ENOUGH_DISTANCE";
   if(distance<=q.freeze+1e-9 || (p.sl>0 && MathAbs(price-p.sl)<=q.freeze+1e-9) || (p.tp>0 && MathAbs(price-p.tp)<=q.freeze+1e-9)) return "FREEZE_LEVEL";
   return "ELIGIBLE";
}
double Rank(Layer &p,Quote &q,bool closing) {
   if(closing) return p.side=="BUY"?q.bid-p.entry:p.entry-q.ask;
   return MathAbs((p.side=="BUY"?q.bid:q.ask)-p.entry);
}
bool PlanLayers(RiskCommand &c,Quote &q,Layer &layers_input[],int input_count,int buffer,RiskPlan &plan) {
   plan.code="OK"; plan.side=c.side; plan.total=0; plan.target=0; plan.already=0; plan.planned=0; plan.buy=0; plan.sell=0; plan.count=0;
   if(c.fraction<=0 || c.fraction>1 || buffer<0 || q.tick<=0 || q.step<=0) { plan.code="INVALID_PARAMETERS"; return false; }
   Layer rows[MAX_RISK_POSITIONS]; int count=0; bool buy=false,sell=false;
   for(int i=0;i<input_count;i++) {
      Layer p=layers_input[i]; if(p.symbol!=c.symbol) continue;
      if(p.side=="BUY") buy=true; else sell=true;
      if(c.side!="AUTO" && c.side!="BOTH" && p.side!=c.side) continue;
      if(count>=MAX_RISK_POSITIONS) { plan.code="TOO_MANY_POSITIONS"; return false; }
      rows[count++]=p;
   }
   if(!c.close && c.side=="AUTO" && buy && sell) { plan.code="AMBIGUOUS_SIDE"; return false; }
   if(count==0) { plan.code="NO_POSITIONS"; return false; }
   if(c.side=="AUTO") plan.side=rows[0].side;
   for(int i=0;i<count;i++) {
      plan.total+=rows[i].volume;
      if(rows[i].side=="BUY") plan.buy+=rows[i].volume; else plan.sell+=rows[i].volume;
      if(!c.close && Protected(rows[i],StopFor(rows[i],q,buffer))) plan.already+=rows[i].volume;
   }
   plan.target=plan.total*c.fraction;
   for(int i=0;i<count;i++) for(int j=i+1;j<count;j++) {
      double a=Rank(rows[i],q,c.close),b=Rank(rows[j],q,c.close);
      if(b<a || (b==a && rows[j].ticket<rows[i].ticket)) { Layer tmp=rows[i]; rows[i]=rows[j]; rows[j]=tmp; }
   }
   for(int i=0;i<count;i++) {
      PlanItem item; item.layer=rows[i]; item.stop=0; item.volume=rows[i].volume;
      if(c.close) {
         double remaining=plan.target-plan.planned;
         if(remaining<q.step-1e-9) break;
         double volume=MathMin(MathMin(rows[i].volume,remaining),q.maximum);
         volume=NormalizeDouble(MathFloor(volume/q.step+1e-9)*q.step,8);
         if(rows[i].volume-volume>1e-9 && rows[i].volume-volume<q.minimum-1e-9)
            volume=NormalizeDouble(MathFloor((rows[i].volume-q.minimum)/q.step+1e-9)*q.step,8);
         item.volume=volume;
         item.code=volume>=q.minimum-1e-9?"ELIGIBLE":"VOLUME_CONSTRAINT";
      } else {
         item.stop=StopFor(rows[i],q,buffer); item.code=StopCode(rows[i],q,item.stop);
         if(item.code!="ALREADY_PROTECTED" && plan.already+plan.planned>=plan.target-1e-9) continue;
      }
      if(item.code=="ELIGIBLE") plan.planned+=item.volume;
      plan.items[plan.count++]=item;
   }
   if(plan.planned<=0 && (c.close || plan.already<plan.target-1e-9)) { plan.code="NO_ELIGIBLE_POSITIONS"; return false; }
   return true;
}
bool MakePlan(RiskCommand &c,int buffer,RiskPlan &plan) {
   plan.code="OK"; plan.side=c.side; plan.total=0; plan.target=0; plan.already=0; plan.planned=0; plan.buy=0; plan.sell=0; plan.count=0;
   if(AccountInfoInteger(ACCOUNT_MARGIN_MODE)!=ACCOUNT_MARGIN_MODE_RETAIL_HEDGING) { plan.code="NOT_HEDGING"; return false; }
   Quote q; if(!ReadQuote(c.symbol,q)) { plan.code="SYMBOL_NOT_FOUND_OR_STALE"; return false; }
   Layer rows[MAX_RISK_POSITIONS]; int count=0;
   for(int i=0;i<PositionsTotal();i++) {
      Layer p; if(!ReadLayer(PositionGetTicket(i),p) || p.symbol!=c.symbol) continue;
      if(count>=MAX_RISK_POSITIONS) { plan.code="TOO_MANY_POSITIONS"; return false; }
      rows[count++]=p;
   }
   return PlanLayers(c,q,rows,count,buffer,plan);
}
#endif
