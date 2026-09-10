#ifndef RISK_HTTP
#define RISK_HTTP
// Caller requires an HTTP 200 response. No socket listener or tokens in URLs/logs.
int PostJSON(string api,string path,string body,string agent,string secret,string &response) {
   if(StringFind(api,"https://")!=0 || StringLen(body)>65536) return -1;
   char payload[],output[]; string received;
   StringToCharArray(body,payload,0,WHOLE_ARRAY,CP_UTF8); ArrayResize(payload,ArraySize(payload)-1);
   string headers="Content-Type: application/json\r\n";
   if(agent!="") headers+="X-Agent-ID: "+agent+"\r\nAuthorization: Bearer "+secret+"\r\n";
   int status=WebRequest("POST",api+path,headers,2000,payload,output,received);
   if(ArraySize(output)>65536) return -1;
   response=CharArrayToString(output,0,WHOLE_ARRAY,CP_UTF8);
   return status;
}
#endif
