#ifndef RISK_IDENTITY
#define RISK_IDENTITY
#include "Json.mqh"
string AccountJSON() {
   string mode=AccountInfoInteger(ACCOUNT_MARGIN_MODE)==ACCOUNT_MARGIN_MODE_RETAIL_HEDGING?"RETAIL_HEDGING":"UNSUPPORTED_NETTING";
   return "{\"login\":"+IntegerToString(AccountInfoInteger(ACCOUNT_LOGIN))+",\"server\":"+Q(AccountInfoString(ACCOUNT_SERVER))+
          ",\"margin_mode\":"+Q(mode)+",\"trade_allowed\":"+B((bool)AccountInfoInteger(ACCOUNT_TRADE_ALLOWED))+
          ",\"expert_trade_allowed\":"+B((bool)AccountInfoInteger(ACCOUNT_TRADE_EXPERT))+"}";
}
bool AccountMatches(long login,string server) { return AccountInfoInteger(ACCOUNT_LOGIN)==login && AccountInfoString(ACCOUNT_SERVER)==server; }
string PermissionError() {
   if(AccountInfoInteger(ACCOUNT_MARGIN_MODE)!=ACCOUNT_MARGIN_MODE_RETAIL_HEDGING) return "NOT_HEDGING";
   if(!TerminalInfoInteger(TERMINAL_CONNECTED)) return "TERMINAL_OFFLINE";
   if(!AccountInfoInteger(ACCOUNT_TRADE_ALLOWED)) return "TRADING_DISABLED";
   if(!AccountInfoInteger(ACCOUNT_TRADE_EXPERT) || !TerminalInfoInteger(TERMINAL_TRADE_ALLOWED) || !MQLInfoInteger(MQL_TRADE_ALLOWED)) return "EA_TRADING_DISABLED";
   return "OK";
}
#endif
