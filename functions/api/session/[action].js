// Cloudflare Pages Function: same-origin, HttpOnly cookie session broker.
// Requires SUPABASE_URL and SUPABASE_ANON_KEY as server-side Pages secrets.
const json=(value,status=200,headers={})=>new Response(JSON.stringify(value),{status,headers:{'Content-Type':'application/json','Cache-Control':'no-store',...headers}});
const error=(code,status)=>json({error:{code,message:code}},status);
const cookie=(name,value,maxAge)=>name+'='+encodeURIComponent(value)+'; Path=/api; HttpOnly; Secure; SameSite=Strict; Max-Age='+maxAge;
const parseCookie=(raw)=>Object.fromEntries((raw||'').split(';').map(x=>x.trim().split('=')).filter(x=>x.length===2).map(([k,v])=>[k,decodeURIComponent(v)]));
const sameOrigin=(req)=>{try{return new URL(req.headers.get('Origin')).origin===new URL(req.url).origin}catch{return false}};
const supa=(env,path,options={})=>fetch(env.SUPABASE_URL.replace(/\/$/,'')+path,{...options,headers:{apikey:env.SUPABASE_ANON_KEY,'Content-Type':'application/json',...(options.headers||{})}});
export async function onRequest({request,env,params}){
 const action=params.action;
 if(!env.SUPABASE_URL||!env.SUPABASE_ANON_KEY)return error('server_not_configured',503);
 if(!['login','me','logout'].includes(action))return error('not_found',404);
 if(action==='login'){
  if(request.method!=='POST')return error('method_not_allowed',405);
  if(!sameOrigin(request))return error('csrf_rejected',403);
  let body;try{body=await request.json()}catch{return error('invalid_json',400)}
  if(typeof body.email!=='string'||typeof body.password!=='string'||body.email.length>254||body.password.length>1024)return error('invalid_credentials',400);
  const r=await supa(env,'/auth/v1/token?grant_type=password',{method:'POST',body:JSON.stringify({email:body.email,password:body.password})});
  if(!r.ok)return error('invalid_credentials',401);
  const tokens=await r.json();
  if(!tokens.access_token||!tokens.refresh_token)return error('upstream_error',502);
  const profile=await supa(env,'/rest/v1/my_profile?select=user_id,display_name,role,locale,active',{headers:{Authorization:'Bearer '+tokens.access_token,'Accept-Profile':'api'}});
  if(!profile.ok)return error('profile_unavailable',403);
  const rows=await profile.json();
  if(!Array.isArray(rows)||rows.length!==1||!rows[0].active)return error('account_disabled',403);
  const headers=new Headers();
  headers.append('Set-Cookie',cookie('aoc_access',tokens.access_token,Math.min(tokens.expires_in||900,900)));
  headers.append('Set-Cookie',cookie('aoc_refresh',tokens.refresh_token,60*60*24*7));
  return json({user:rows[0]},200,headers);
 }
 const cookies=parseCookie(request.headers.get('Cookie'));
 if(action==='logout'){
  if(request.method!=='POST')return error('method_not_allowed',405);
  if(!sameOrigin(request))return error('csrf_rejected',403);
  if(cookies.aoc_access)await supa(env,'/rest/v1/rpc/revoke_my_session',{method:'POST',headers:{Authorization:'Bearer '+cookies.aoc_access,'Content-Profile':'api'},body:'{}'}).catch(()=>null);
  const headers=new Headers();
  headers.append('Set-Cookie',cookie('aoc_access','',0));headers.append('Set-Cookie',cookie('aoc_refresh','',0));
  return json({ok:true},200,headers);
 }
 if(request.method!=='GET')return error('method_not_allowed',405);
 if(!cookies.aoc_access)return error('unauthenticated',401);
 const r=await supa(env,'/rest/v1/my_profile?select=user_id,display_name,role,locale,active',{headers:{Authorization:'Bearer '+cookies.aoc_access,'Accept-Profile':'api'}});
 if(!r.ok)return error('unauthenticated',401);
 const rows=await r.json();
 return Array.isArray(rows)&&rows.length===1&&rows[0].active?json({user:rows[0]}):error('unauthenticated',401);
}
