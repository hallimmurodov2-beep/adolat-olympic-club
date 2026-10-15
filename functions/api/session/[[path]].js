// M3 session broker prototype. Default OFF until hosted security acceptance.
// Same-origin only. Supabase publishable key is public; service keys never used here.
const REFRESH = '__Host-adolat-refresh';
const limits = {login:8192,logout:1024};
function reply(body,status=200,cookie) {
 const headers = new Headers({'Content-Type':'application/json; charset=utf-8',
 'Cache-Control':'no-store','X-Content-Type-Options':'nosniff','Referrer-Policy':'no-referrer'});
 if (cookie) headers.set('Set-Cookie',cookie);
 return new Response(JSON.stringify(body),{status,headers});
}
const clearCookie = REFRESH+'=; Path=/; Max-Age=0; Secure; HttpOnly; SameSite=Strict';
function cookieFor(token) {
 if (!token || !/^[A-Za-z0-9._-]{12,4096}$/.test(token)) throw Error('invalid_refresh_token');
 return REFRESH+'='+encodeURIComponent(token)+'; Path=/; Max-Age=2592000; Secure; HttpOnly; SameSite=Strict';
}
function refreshFrom(request) {
 const cookie=request.headers.get('cookie')||'';
 const match=cookie.match(/(?:^|;\s*)__Host-adolat-refresh=([^;]+)/);
 if (!match) return null;
 try {const val=decodeURIComponent(match[1]);return /^[A-Za-z0-9._-]{12,4096}$/.test(val)?val:null;} catch{return null;}
}
function config(context) {
 const {SUPABASE_URL:url,SUPABASE_PUBLISHABLE_KEY:key,SESSION_ORIGIN:origin}=context.env||{};
 if(context.env?.BROKER_ENABLED!=='yes-reviewed') return null;
 if(!url||!key||!origin || !/^https:\/\//.test(url)||!/^https:\/\//.test(origin)) return null;
 const parsed=new URL(url);
 if(parsed.username||parsed.password||parsed.search||parsed.hash) return null;
 return {url:parsed.origin,key,origin};
}
function allowed(request,origin,mutate) {
 const url=new URL(request.url);
 if(url.origin!==origin) return false;
 const site=request.headers.get('Sec-Fetch-Site');
 if(site && site!=='same-origin' && site!=='none') return false;
 if(mutate && request.headers.get('Origin')!==origin) return false;
 return true;
}
async function fromAuth(cfg,grant,credentials) {
 const res=await fetch(cfg.url+'/auth/v1/token?grant_type='+grant,{
   method:'POST',headers:{'Content-Type':'application/json','apikey':cfg.key},
   body:JSON.stringify(credentials),redirect:'error',signal:AbortSignal.timeout(12000)});
 if(!res.ok) return null;
 const result=await res.json();
 if(typeof result.access_token!=='string'||typeof result.refresh_token!=='string'
 || !Number.isInteger(result.expires_in)||result.expires_in<1) return null;
 return result;
}
async function scopedProfile(cfg,access) {
 const resp=await fetch(cfg.url+'/rest/v1/my_profile?select=user_id,display_name,role,locale,active&limit=1',{
 headers:{apikey:cfg.key,Authorization:'Bearer '+access,'Accept-Profile':'api'},
 redirect:'error',signal:AbortSignal.timeout(12000)});
 if(!resp.ok) return null;
 const rows=await resp.json();
 if(!Array.isArray(rows)||rows.length!==1||rows[0].active!==true) return null;
 return rows[0];
}
function payload(session,profile) {
 return {access_token:session.access_token,expires_in:session.expires_in,
 token_type:'bearer',profile,server_now:Date.now()};
}
export async function onRequest(context) {
 const cfg=config(context);if(!cfg) return reply({error:{code:'broker_disabled'}},503);
 const request=context.request, path=new URL(request.url).pathname;
 const action=path.startsWith('/api/session/')?path.slice('/api/session/'.length):'';
 const methods={login:'POST',access:'GET',logout:'POST'};
 if(!Object.hasOwn(methods,action)) return reply({error:{code:'not_found'}},404);
 if(request.method!==methods[action]) return reply({error:{code:'method_not_allowed'}},405);
 if(!allowed(request,cfg.origin,action!=='access')) return reply({error:{code:'origin_rejected'}},403);
 try{
   if(action==='login') {
     const len=Number(request.headers.get('Content-Length')||0);
     if(len>limits.login) return reply({error:{code:'invalid_input'}},413);
     const raw=await request.text();if(raw.length>limits.login) return reply({error:{code:'invalid_input'}},413);
     let body;try{body=JSON.parse(raw);}catch{return reply({error:{code:'invalid_input'}},422);}
     if(typeof body.email!=='string'||typeof body.password!=='string'
     ||body.email.length>254||body.password.length>256||body.password.length<1)
       return reply({error:{code:'invalid_input'}},422);
     const session=await fromAuth(cfg,'password',{email:body.email.trim(),password:body.password});
     if(!session) return reply({error:{code:'invalid_credentials'}},401);
     const profile=await scopedProfile(cfg,session.access_token);
     if(!profile) return reply({error:{code:'not_authorized'}},403);
     return reply(payload(session,profile),200,cookieFor(session.refresh_token));
   }
   const refresh=refreshFrom(request);
   if(!refresh) return reply({error:{code:'unauthenticated'}},401,action==='logout'?clearCookie:undefined);
   const session=await fromAuth(cfg,'refresh_token',{refresh_token:refresh});
   if(!session) return reply({error:{code:'unauthenticated'}},401,clearCookie);
   if(action==='logout') {
     const revoke=await fetch(cfg.url+'/rest/v1/rpc/revoke_my_session',{
       method:'POST',headers:{apikey:cfg.key,Authorization:'Bearer '+session.access_token,
       'Content-Type':'application/json','Content-Profile':'api'},
       body:'{}',redirect:'error',signal:AbortSignal.timeout(12000)});
     const signout=await fetch(cfg.url+'/auth/v1/logout',{
       method:'POST',headers:{apikey:cfg.key,Authorization:'Bearer '+session.access_token},
       redirect:'error',signal:AbortSignal.timeout(12000)});
     if(!revoke.ok||!signout.ok) return reply({error:{code:'revocation_unverified'}},503,clearCookie);
     return reply({ok:true},200,clearCookie);
   }
   const profile=await scopedProfile(cfg,session.access_token);
   if(!profile) return reply({error:{code:'not_authorized'}},403,clearCookie);
   return reply(payload(session,profile),200,cookieFor(session.refresh_token));
 }catch {
   return reply({error:{code:'temporarily_unavailable'}},503);
 }
}
