#ifndef RISK_PROTOCOL
#define RISK_PROTOCOL
#include "Json.mqh"
struct RiskCommand { string id; string type; string symbol; string side; double fraction; ulong deadline; bool preview; bool close; };
bool ReadCommand(Json &json,int node,ulong request_started,RiskCommand &c) {
   if(json.Kind(node)!="object" || !json.Fields(node,"id|type|symbol|side|target_fraction|expires_in_ms",6)) return false;
   string keys[]={"id","type","symbol","side"};
   for(int i=0;i<4;i++) if(json.Kind(json.Get(node,keys[i]))!="string") return false;
   if(json.Kind(json.Get(node,"target_fraction"))!="number" || json.Kind(json.Get(node,"expires_in_ms"))!="number") return false;
   c.id=json.Str(node,"id"); c.type=json.Str(node,"type"); c.symbol=json.Str(node,"symbol"); c.side=json.Str(node,"side");
   c.fraction=json.Num(node,"target_fraction"); double ttl=json.Num(node,"expires_in_ms");
   if(!UUIDValid(c.id) || c.fraction<=0 || c.fraction>1 || ttl<=0 || ttl>30000) return false;
   if(StringLen(c.symbol)<1 || StringLen(c.symbol)>64) return false;
   for(int i=0;i<StringLen(c.symbol);i++) if(StringFind("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_.#-",StringSubstr(c.symbol,i,1))<0) return false;
   if(c.side!="AUTO" && c.side!="BUY" && c.side!="SELL" && c.side!="BOTH") return false;
   if(c.type!="PREVIEW_PROTECT_BREAKEVEN" && c.type!="PROTECT_BREAKEVEN" && c.type!="PREVIEW_REDUCE_EXPOSURE" && c.type!="REDUCE_EXPOSURE") return false;
   c.preview=(StringFind(c.type,"PREVIEW_")==0); c.close=(StringFind(c.type,"REDUCE_EXPOSURE")>=0);
   if(!c.close && c.side=="BOTH") return false;
   if(c.close && c.side=="AUTO") return false;
   // Conservative: subtract full request round trip, not just processing elapsed time.
   c.deadline=request_started+(ulong)ttl;
   return GetTickCount64()<c.deadline;
}
#endif
