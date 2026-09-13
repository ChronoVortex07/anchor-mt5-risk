#ifndef RISK_HTTP
#define RISK_HTTP
// Caller requires an HTTP 200 response. No socket listener or tokens in URLs/logs.
int PostJSON(string api,string path,string body,string agent,string secret,string &response,int timeout=2000) {
   if(StringFind(api,"https://")!=0 || StringLen(body)>65536) return -1;
   char payload[],output[]; string received;
   StringToCharArray(body,payload,0,WHOLE_ARRAY,CP_UTF8); ArrayResize(payload,ArraySize(payload)-1);
   string headers="Content-Type: application/json\r\n";
   if(agent!="") headers+="X-Agent-ID: "+agent+"\r\nAuthorization: Bearer "+secret+"\r\n";
   ResetLastError();
   int status=WebRequest("POST",api+path,headers,timeout,payload,output,received);
   int error=GetLastError();
   if(status==-1) {
      Print("WEBREQUEST_FAILED path=",path," MQL error=",error);
      if(error==4014) Print("Allow your ApiUrl in MT5 Tools > Options > Expert Advisors > Allow WebRequest. Run on a chart, not in Strategy Tester.");
      else if(error==5200) Print("Invalid address. ApiUrl must be your operator's HTTPS origin, without an endpoint path.");
      else if(error==5201) Print("Connection failed. Check ApiUrl, Internet access, DNS, proxy and TLS on this computer.");
      else if(error==5202) Print("Request timed out. Pairing may have reached the server; check account status before using a fresh code.");
      else Print("Check MT5 WebRequest permissions and network connectivity. Share this numeric error, never credentials.");
   }
   if(status==301 || status==302 || status==307 || status==308 || status==403)
      Print("HTTP access blocked or redirected. Operator: check Cloudflare Access and browser challenges for the API.");
   if(ArraySize(output)>65536) return -1;
   response=CharArrayToString(output,0,WHOLE_ARRAY,CP_UTF8);
   return status;
}
#endif
