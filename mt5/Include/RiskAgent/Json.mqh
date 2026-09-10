// Small original JSON parser. No external binary or library dependencies.
// Bounded size/depth; duplicate object keys and invalid numbers fail closed.
#ifndef RISK_JSON
#define RISK_JSON
struct JsonToken { int parent; string key; string value; string kind; };
class Json {
private:
   string source; int offset; int count;
   JsonToken nodes[2048];
   void Space() { while(offset<StringLen(source) && StringFind(" \r\n\t",StringSubstr(source,offset,1))>=0) offset++; }
   bool ReadString(string &out) {
      if(StringSubstr(source,offset++,1)!="\"") return false;
      out="";
      while(offset<StringLen(source)) {
         ushort c=StringGetCharacter(source,offset++);
         if(c==34) return true;
         if(c<32) return false;
         if(c==92) {
            if(offset>=StringLen(source)) return false;
            c=StringGetCharacter(source,offset++);
            if(c==34 || c==92 || c==47) out+=ShortToString(c);
            else if(c==98) out+=ShortToString(8);
            else if(c==102) out+=ShortToString(12);
            else if(c==110) out+="\n";
            else if(c==114) out+="\r";
            else if(c==116) out+="\t";
            else if(c==117) {
               int value=0;
               for(int j=0;j<4;j++) {
                  if(offset>=StringLen(source)) return false;
                  string h=StringSubstr(source,offset++,1); StringToLower(h);
                  int n=StringFind("0123456789abcdef",h); if(n<0) return false;
                  value=value*16+n;
               }
               out+=ShortToString((ushort)value);
            } else return false;
         } else out+=ShortToString(c);
      }
      return false;
   }
   bool Digit() { if(offset>=StringLen(source)) return false; ushort c=StringGetCharacter(source,offset); return c>=48 && c<=57; }
   int Value(int parent,string key,int depth) {
      Space(); if(depth>12 || count>=2048 || offset>=StringLen(source)) return -1;
      int id=count++; nodes[id].parent=parent; nodes[id].key=key;
      nodes[id].value=""; nodes[id].kind="";
      string c=StringSubstr(source,offset,1);
      if(c=="{" || c=="[") {
         bool object=(c=="{"); nodes[id].kind=object?"object":"array"; offset++; Space();
         string closing=object?"}":"]";
         if(StringSubstr(source,offset,1)==closing) { offset++; return id; }
         while(true) {
            string childkey="";
            if(object) {
               Space(); if(!ReadString(childkey)) return -1;
               for(int k=id+1;k<count;k++) if(nodes[k].parent==id && nodes[k].key==childkey) return -1;
               Space(); if(StringSubstr(source,offset++,1)!=":") return -1;
            }
            if(Value(id,childkey,depth+1)<0) return -1;
            Space(); c=StringSubstr(source,offset++,1);
            if(c==closing) return id;
            if(c!=",") return -1;
         }
      }
      if(c=="\"") { nodes[id].kind="string"; if(!ReadString(nodes[id].value)) return -1; return id; }
      if(StringSubstr(source,offset,4)=="null") { nodes[id].kind="null"; offset+=4; return id; }
      if(StringSubstr(source,offset,4)=="true") { nodes[id].kind="bool"; nodes[id].value="true"; offset+=4; return id; }
      if(StringSubstr(source,offset,5)=="false") { nodes[id].kind="bool"; nodes[id].value="false"; offset+=5; return id; }
      int start=offset;
      if(c=="-") offset++;
      if(!Digit()) return -1;
      if(StringSubstr(source,offset,1)=="0") offset++;
      else while(Digit()) offset++;
      if(StringSubstr(source,offset,1)==".") { offset++; if(!Digit()) return -1; while(Digit()) offset++; }
      c=StringSubstr(source,offset,1);
      if(c=="e" || c=="E") {
         offset++; c=StringSubstr(source,offset,1); if(c=="+" || c=="-") offset++;
         if(!Digit()) return -1; while(Digit()) offset++;
      }
      nodes[id].kind="number"; nodes[id].value=StringSubstr(source,start,offset-start);
      if(!MathIsValidNumber(StringToDouble(nodes[id].value))) return -1;
      return id;
   }
public:
   bool Parse(string input_text) { source=input_text; offset=0; count=0; if(StringLen(input_text)>65536) return false; if(Value(-1,"",0)!=0) return false; Space(); return offset==StringLen(source); }
   int Get(int parent,string key) { for(int i=0;i<count;i++) if(nodes[i].parent==parent && nodes[i].key==key) return i; return -1; }
   string Kind(int id) { return id>=0 && id<count?nodes[id].kind:"missing"; }
   string Text(int id) { return id>=0 && id<count?nodes[id].value:""; }
   string Str(int parent,string key) { return Text(Get(parent,key)); }
   double Num(int parent,string key) { return StringToDouble(Str(parent,key)); }
   bool Fields(int parent,string allowed,int expected) {
      int n=0;
      for(int i=0;i<count;i++) if(nodes[i].parent==parent) {
         if(StringFind("|"+allowed+"|","|"+nodes[i].key+"|")<0) return false;
         n++;
      }
      return n==expected;
   }
};
string Q(string value) {
   string out="\"";
   for(int i=0;i<StringLen(value);i++) {
      ushort c=StringGetCharacter(value,i);
      if(c==34) out+="\\\"";
      else if(c==92) out+="\\\\";
      else if(c<32) out+=StringFormat("\\u%04x",c);
      else out+=ShortToString(c);
   }
   return out+"\"";
}
string N(double value) { return DoubleToString(value,8); }
string B(bool value) { return value?"true":"false"; }
bool UUIDValid(string value) {
   if(StringLen(value)!=36) return false;
   for(int i=0;i<36;i++) {
      string c=StringSubstr(value,i,1);
      if(i==8 || i==13 || i==18 || i==23) { if(c!="-") return false; }
      else if(StringFind("0123456789abcdef",c)<0) return false;
   }
   return true;
}
#endif
