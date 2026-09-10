#property strict
#property script_show_inputs
#include "../Include/RiskAgent/Planner.mqh"
int failures=0;
void Check(bool yes,string name) { if(!yes) { failures++; Print("FAIL: ",name); } }
void OnStart() {
   Quote q; q.bid=110; q.ask=110.2; q.point=.01; q.tick=.25; q.stops=.2; q.freeze=0; q.digits=2;
   Layer p; p.side="BUY"; p.entry=100.13; p.sl=0; p.tp=130;
   Check(StopFor(p,q,0)==100.25,"BUY ceil tick");
   Check(StopCode(p,q,100.25)=="ELIGIBLE","BUY eligible");
   p.sl=105; Check(StopCode(p,q,100.25)=="ALREADY_PROTECTED","never lower BUY stop");
   p.sl=0; p.entry=109.9; Check(StopCode(p,q,110)=="SKIPPED_NOT_ENOUGH_DISTANCE","invalid distance");
   p.side="SELL"; p.entry=120.13; Check(StopFor(p,q,3)==120,"SELL floor tick");
   p.sl=119; Check(StopCode(p,q,120)=="ALREADY_PROTECTED","never raise SELL stop");
   q.step=.01; q.minimum=.01; q.maximum=100;
   Layer layers[3];
   for(int i=0;i<3;i++) { layers[i].ticket=i+1; layers[i].symbol="XAUUSD"; layers[i].side="BUY"; layers[i].volume=.1; layers[i].entry=100+i; layers[i].sl=0; layers[i].tp=130; }
   RiskCommand c; c.symbol="XAUUSD"; c.side="AUTO"; c.fraction=.5; c.close=false;
   RiskPlan plan;
   Check(PlanLayers(c,q,layers,3,0,plan),"pure layer plan");
   Check(MathAbs(plan.planned-.2)<1e-9 && plan.items[0].layer.ticket==3,"volume overshoot and closest first");
   layers[0].sl=105;
   Check(PlanLayers(c,q,layers,3,0,plan) && MathAbs(plan.already-.1)<1e-9 && MathAbs(plan.planned-.1)<1e-9,"already protected counts");
   layers[2].side="SELL"; layers[2].entry=108;
   Check(!PlanLayers(c,q,layers,3,0,plan) && plan.code=="AMBIGUOUS_SIDE","mixed BE side");
   c.close=true; c.side="BOTH";
   layers[0].volume=.4; layers[0].entry=100; layers[1].volume=.3; layers[1].entry=114; layers[2].volume=.3;
   Check(PlanLayers(c,q,layers,3,0,plan),"mixed close plan");
   Check(plan.items[0].layer.ticket==2 && plan.items[1].layer.ticket==3 && MathAbs(plan.items[1].volume-.2)<1e-9,"worst cost and partial final ticket");
   Json j; Check(!j.Parse("{\"id\":1,\"id\":2}"),"duplicate keys rejected");
   Check(!j.Parse("{\"x\":NaN}"),"NaN rejected");
   Check(!j.Parse("{\"x\":01}"),"leading zero rejected");
   Check(j.Parse("{\"x\":\"a\\\"b\",\"n\":0.5}"),"JSON escapes");
   Check(j.Str(0,"x")=="a\"b","string round trip");
   Print("Planner tests: ",failures==0?"PASS":"FAIL","; failures=",failures);
}
