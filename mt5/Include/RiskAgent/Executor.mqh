#ifndef RISK_EXECUTOR
#define RISK_EXECUTOR
#include "Planner.mqh"
#include "AccountIdentity.mqh"
// These are the only two broker mutation paths in the entire EA.
// All order direction, ticket, volume and price fields originate from live MT5 state.
bool DefinitiveReject(uint code) {
   return code==TRADE_RETCODE_REQUOTE || code==TRADE_RETCODE_REJECT || code==TRADE_RETCODE_CANCEL ||
          code==TRADE_RETCODE_INVALID || code==TRADE_RETCODE_INVALID_VOLUME || code==TRADE_RETCODE_INVALID_PRICE ||
          code==TRADE_RETCODE_INVALID_STOPS || code==TRADE_RETCODE_TRADE_DISABLED || code==TRADE_RETCODE_MARKET_CLOSED ||
          code==TRADE_RETCODE_NO_MONEY || code==TRADE_RETCODE_PRICE_CHANGED || code==TRADE_RETCODE_PRICE_OFF ||
          code==TRADE_RETCODE_INVALID_FILL || code==TRADE_RETCODE_FROZEN || code==TRADE_RETCODE_POSITION_CLOSED ||
          code==TRADE_RETCODE_INVALID_CLOSE_VOLUME;
}
string ExecuteItem(RiskCommand &c,PlanItem &item,int buffer,bool enabled,long bound_login,string bound_server,
                   int deviation,double &confirmed,uint &retcode,double &old_sl,double &new_sl,double &tp) {
   confirmed=0; retcode=0; old_sl=0; new_sl=0; tp=0;
   if(!enabled) return "EXECUTION_DISABLED";
   if(GetTickCount64()>=c.deadline) return "COMMAND_EXPIRED";
   if(!AccountMatches(bound_login,bound_server)) return "ACCOUNT_MISMATCH";
   string permission=PermissionError(); if(permission!="OK") return permission;
   Layer live; if(!ReadLayer(item.layer.ticket,live)) return "POSITION_DISAPPEARED";
   if(live.symbol!=c.symbol || live.side!=item.layer.side || live.identifier!=item.layer.identifier ||
      MathAbs(live.volume-item.layer.volume)>1e-9 || live.entry!=item.layer.entry) return "POSITION_CHANGED";
   Quote q; if(!ReadQuote(c.symbol,q)) return "STALE_QUOTE";
   old_sl=live.sl; new_sl=live.sl; tp=live.tp;
   MqlTradeRequest request={}; MqlTradeResult result={}; MqlTradeCheckResult check={};
   request.position=live.ticket; request.symbol=live.symbol;
   if(!c.close) {
      double stop=StopFor(live,q,buffer);
      string code=StopCode(live,q,stop); if(code!="ELIGIBLE") return code;
      // Independent final monotonic check; never zero a stop or overwrite TP.
      if(stop<=0 || (live.sl>0 && (live.side=="BUY"?stop<live.sl:stop>live.sl))) return "RISK_INVARIANT";
      request.action=TRADE_ACTION_SLTP; request.sl=stop; request.tp=live.tp;
   } else {
      if(item.volume<=0 || item.volume>live.volume+1e-9 || item.volume>q.maximum+1e-9 ||
         item.volume<q.minimum-1e-9 || MathAbs(item.volume/q.step-MathRound(item.volume/q.step))>1e-7) return "VOLUME_CONSTRAINT";
      double residual=live.volume-item.volume;
      if(residual>1e-9 && residual<q.minimum-1e-9) return "VOLUME_CONSTRAINT";
      long filling=SymbolInfoInteger(live.symbol,SYMBOL_FILLING_MODE);
      if((filling & SYMBOL_FILLING_FOK)!=0) request.type_filling=ORDER_FILLING_FOK;
      else if((filling & SYMBOL_FILLING_IOC)!=0) request.type_filling=ORDER_FILLING_IOC;
      else return "UNSUPPORTED_FILLING_MODE"; // Never RETURN/pending remainder.
      request.action=TRADE_ACTION_DEAL;
      request.type=live.side=="BUY"?ORDER_TYPE_SELL:ORDER_TYPE_BUY;
      request.price=live.side=="BUY"?q.bid:q.ask;
      request.volume=item.volume; request.deviation=(ulong)deviation;
      request.comment="Risk close "+StringSubstr(c.id,0,8);
   }
   if(!OrderCheck(request,check)) { retcode=check.retcode; return "BROKER_CHECK_REJECTED"; }
   // OrderCheck is advisory. Re-read immediately after it too; abort on any manual change.
   Layer final_state;
   if(!ReadLayer(live.ticket,final_state)) return "POSITION_DISAPPEARED";
   if(final_state.identifier!=live.identifier || final_state.symbol!=live.symbol || final_state.side!=live.side ||
      final_state.volume!=live.volume || final_state.entry!=live.entry || final_state.sl!=live.sl || final_state.tp!=live.tp) return "POSITION_CHANGED";
   if(GetTickCount64()>=c.deadline || !AccountMatches(bound_login,bound_server)) return "COMMAND_EXPIRED_OR_ACCOUNT_CHANGED";
   if(PermissionError()!="OK") return "TRADING_DISABLED";
   if(!ReadQuote(c.symbol,q)) return "STALE_QUOTE";
   if(!c.close && StopCode(final_state,q,request.sl)!="ELIGIBLE") return "STOP_LEVEL_INVALID";
   if(c.close) request.price=live.side=="BUY"?q.bid:q.ask;
   bool sent=OrderSend(request,result); retcode=result.retcode;
   if(!sent || (retcode!=TRADE_RETCODE_DONE && retcode!=TRADE_RETCODE_DONE_PARTIAL && retcode!=TRADE_RETCODE_NO_CHANGES))
      return DefinitiveReject(retcode)?"BROKER_REJECTED":"EXECUTION_UNCERTAIN";
   if(!c.close) {
      Layer after;
      if(!ReadLayer(live.ticket,after)) return "EXECUTION_UNCERTAIN";
      new_sl=after.sl;
      if(after.identifier!=live.identifier || !Protected(after,request.sl) || after.tp!=live.tp ||
         (live.sl>0 && (live.side=="BUY"?after.sl<live.sl:after.sl>live.sl))) return "EXECUTION_UNCERTAIN";
      confirmed=after.volume; return "CONFIRMED";
   }
   // Attribute closed volume to the returned broker deal, never just a position delta
   // that might include a manual trade. Delayed/unavailable evidence blocks the account.
   if(result.deal==0 || !HistoryDealSelect(result.deal)) return "EXECUTION_UNCERTAIN";
   long entry=HistoryDealGetInteger(result.deal,DEAL_ENTRY);
   double deal_volume=HistoryDealGetDouble(result.deal,DEAL_VOLUME);
   if(entry!=DEAL_ENTRY_OUT || (ulong)HistoryDealGetInteger(result.deal,DEAL_POSITION_ID)!=live.identifier ||
      HistoryDealGetString(result.deal,DEAL_SYMBOL)!=live.symbol || deal_volume<=0 || deal_volume>item.volume+1e-9 ||
      HistoryDealGetInteger(result.deal,DEAL_TYPE)!=(live.side=="BUY"?DEAL_TYPE_SELL:DEAL_TYPE_BUY)) return "EXECUTION_UNCERTAIN";
   Layer after; double remaining=ReadLayer(live.ticket,after)?after.volume:0;
   if(remaining>live.volume-deal_volume+1e-9) return "EXECUTION_UNCERTAIN";
   if(remaining>0 && (after.identifier!=live.identifier || after.sl!=live.sl || after.tp!=live.tp)) return "EXECUTION_UNCERTAIN";
   confirmed=deal_volume;
   return confirmed+1e-9<item.volume?"CONFIRMED_PARTIAL":"CONFIRMED";
}
string BuildResult(RiskCommand &c,RiskPlan &p,int buffer,bool enabled,long login,string server,int deviation) {
   double confirmed=0; int changed=0,ineligible=0; bool uncertain=false; string rows="";
   for(int i=0;i<p.count;i++) {
      string code=p.items[i].code; uint retcode=0; double volume=0,old_sl=p.items[i].layer.sl,new_sl=old_sl,tp=p.items[i].layer.tp;
      if(!c.preview && code=="ELIGIBLE" && !uncertain) {
         code=ExecuteItem(c,p.items[i],buffer,enabled,login,server,deviation,volume,retcode,old_sl,new_sl,tp);
         confirmed+=volume; if(volume>0) changed++;
         if(code=="EXECUTION_UNCERTAIN") uncertain=true;
      } else if(uncertain && code=="ELIGIBLE") code="SKIPPED_AFTER_UNCERTAIN";
      if(code!="ELIGIBLE" && code!="CONFIRMED" && code!="CONFIRMED_PARTIAL" && code!="ALREADY_PROTECTED") ineligible++;
      if(rows!="") rows+=",";
      rows+="{\"ticket\":"+Q(IntegerToString((long)p.items[i].layer.ticket))+",\"code\":"+Q(code)+
            ",\"volume\":"+N(c.preview?p.items[i].volume:volume)+",\"retcode\":"+IntegerToString(retcode)+
            ",\"old_sl\":"+N(old_sl)+",\"new_sl\":"+N(new_sl)+",\"tp\":"+N(tp)+"}";
   }
   double protected_volume=p.already;
   if(!c.preview && !c.close) { RiskPlan current; if(MakePlan(c,buffer,current)) protected_volume=current.already; else protected_volume=0; }
   string status=p.code=="OK"?"SUCCEEDED":"FAILED";
   if(!c.preview && p.planned>0 && confirmed+1e-9<p.planned) status=confirmed>0?"PARTIAL":"FAILED";
   if(!c.preview && c.close && confirmed+1e-9<p.target && confirmed>0) status="PARTIAL";
   if(!c.preview && !c.close && p.total>0) status=protected_volume+1e-9>=p.target?"SUCCEEDED":(confirmed>0?"PARTIAL":"FAILED");
   if(uncertain) status="UNCERTAIN";
   string outcome_code=uncertain?"EXECUTION_UNCERTAIN":p.code;
   if(!c.preview && outcome_code=="OK" && status!="SUCCEEDED") outcome_code=status=="PARTIAL"?"PARTIAL_COMPLETION":"EXECUTION_FAILED";
   return "{\"command_id\":"+Q(c.id)+",\"status\":"+Q(status)+",\"summary\":{\"code\":"+Q(outcome_code)+
          ",\"symbol\":"+Q(c.symbol)+",\"side\":"+Q(p.side)+",\"total_volume\":"+N(p.total)+
          ",\"requested_volume\":"+N(p.target)+",\"already_protected_volume\":"+N(p.already)+
          ",\"planned_volume\":"+N(p.planned)+",\"confirmed_volume\":"+N(confirmed)+
          ",\"protected_volume\":"+N(protected_volume)+",\"buy_volume\":"+N(p.buy)+",\"sell_volume\":"+N(p.sell)+
          ",\"changed_positions\":"+IntegerToString(changed)+",\"ineligible_positions\":"+IntegerToString(ineligible)+"},\"position_results\":["+rows+"]}";
}
#endif
