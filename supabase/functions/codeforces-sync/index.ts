// M6 official Codeforces integration. Fixed host, bounded bytes and persistent 3-second rate slot.
const MAX_BYTES=4*1024*1024;
const HANDLE=/^[A-Za-z0-9_.-]{3,24}$/;
const ORIGIN=Deno.env.get('SESSION_ORIGIN')||'';
const URL_BASE=Deno.env.get('SUPABASE_URL')||'';
const KEY=Deno.env.get('SUPABASE_PUBLISHABLE_KEY')||'';
const SERVICE=Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')||'';
function result(obj:unknown,status=200) {
 return new Response(JSON.stringify(obj),{status,headers:{
 'Content-Type':'application/json','Cache-Control':'private, no-store',
 'X-Content-Type-Options':'nosniff','Vary':'Origin',
 ...(ORIGIN?{'Access-Control-Allow-Origin':ORIGIN}:{})}});
}
function headers(jwt:string,secret=false,post=true):HeadersInit {
 return {apikey:secret?SERVICE:KEY,Authorization:'Bearer '+(secret?SERVICE:jwt),
 ...(post?{'Content-Type':'application/json','Content-Profile':'api'}:
 {'Accept-Profile':'api'})};
}
async function rpc(jwt:string,name:string,args:Record<string,unknown>={},secret=false) {
 const r=await fetch(URL_BASE+'/rest/v1/rpc/'+name,{
 method:'POST',headers:headers(jwt,secret),body:JSON.stringify(args),redirect:'error',
 signal:AbortSignal.timeout(10000)});
 if(!r.ok) throw new Error('rpc_'+r.status);
 return r.json();
}
async function official(method:'user.info'|'contest.list',query:Record<string,string>) {
 const link=new URL('https://codeforces.com/api/'+method);
 for(const [k,v] of Object.entries(query)) link.searchParams.set(k,v);
 const r=await fetch(link,{method:'GET',redirect:'error',signal:AbortSignal.timeout(10000),
 headers:{'User-Agent':'AdolatOlympicClub/2.0 (school learning; public API)'}});
 if(r.status===429) throw new Error('rate_limited');
 if(!r.ok) throw new Error('provider_unavailable');
 if(Number(r.headers.get('Content-Length')||0)>MAX_BYTES) throw new Error('too_large');
 const reader=r.body?.getReader();if(!reader) throw new Error('no_body');
 const chunks:Uint8Array[]=[];let size=0;
 while(true) {const next=await reader.read();if(next.done)break;
  if(next.value) {size+=next.value.byteLength;if(size>MAX_BYTES) {
    reader.cancel();throw new Error('too_large');} chunks.push(next.value);}
 }
 const all=new Uint8Array(size);let offset=0;
 for(const chunk of chunks){all.set(chunk,offset);offset+=chunk.length;}
 const data=JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(all));
 if(!data||data.status!=='OK'||!Array.isArray(data.result)) throw new Error('invalid_upstream');
 return data.result as Record<string,unknown>[];
}
function safeProfile(data:Record<string,unknown>) {
 const h=data.handle;
 if(typeof h!=='string'||!HANDLE.test(h)) throw new Error('invalid_profile');
 const num=(v:unknown)=>typeof v==='number'&&Number.isSafeInteger(v)&&Math.abs(v)<=1000000?v:null;
 return {handle:h,rating:num(data.rating),maxRating:num(data.maxRating),
 rank:typeof data.rank==='string'?data.rank.slice(0,80):null,
 registrationTimeSeconds:typeof data.registrationTimeSeconds==='number'
 &&Number.isSafeInteger(data.registrationTimeSeconds)?data.registrationTimeSeconds:null};
}
export async function handleCodeforces(request:Request) {
 if(!ORIGIN.startsWith('https://')||request.headers.get('Origin')!==ORIGIN)
  return result({error:'forbidden'},403);
 if(request.method==='OPTIONS') return new Response(null,{status:204,headers:{
  'Access-Control-Allow-Origin':ORIGIN,
  'Access-Control-Allow-Methods':'POST, OPTIONS',
  'Access-Control-Allow-Headers':'authorization, apikey, content-type',
  'Access-Control-Max-Age':'600','Vary':'Origin'}});
 if(request.method!=='POST')return result({error:'method_not_allowed'},405);
 if(Deno.env.get('CODEFORCES_SYNC_ENABLED')!=='yes-reviewed'||!URL_BASE||!KEY||!SERVICE)
  return result({error:'integration_disabled'},503);
 const raw=request.headers.get('authorization')||'';
 if(!/^Bearer [A-Za-z0-9._-]+$/.test(raw)) return result({error:'unauthenticated'},401);
 const jwt=raw.slice(7);
 try{
  const user=await fetch(URL_BASE+'/auth/v1/user',{headers:headers(jwt,false,false),
    redirect:'error',signal:AbortSignal.timeout(10000)});
  if(!user.ok) return result({error:'unauthenticated'},401);
  const body=await request.text();if(body.length>4096)return result({error:'invalid_input'},413);
  const {action}=JSON.parse(body);
  if(action==='contests'){
   const cached=await rpc(jwt,'codeforces_contests');
   if(cached?.next_refresh_at && Date.parse(cached.next_refresh_at)>Date.now()
     &&Array.isArray(cached.contests)) return result({...cached,source:'cache'});
   if(!await rpc(jwt,'edge_reserve_codeforces_fetch',{},true))
     return result({...cached,source:'stale',error:'rate_slot_busy'});
   const original=await official('contest.list',{gym:'false'});
   const now=Math.floor(Date.now()/1000);
   const upcoming=original.filter(c=>typeof c.id==='number'&&c.phase==='BEFORE'
     &&typeof c.startTimeSeconds==='number'&&c.startTimeSeconds>=now-60
     &&typeof c.name==='string').slice(0,100).map(c=>({
      id:c.id,name:String(c.name).slice(0,250),start_time:c.startTimeSeconds,
      duration_seconds:typeof c.durationSeconds==='number'?c.durationSeconds:0}));
   await rpc(jwt,'edge_store_codeforces_contests',{contests:upcoming},true);
   return result({contests:upcoming,source:'official',fetched_at:new Date().toISOString()});
  }
  if(action==='validate') {
   const own=await rpc(jwt,'my_codeforces');
   if(!own?.id||!HANDLE.test(own.handle))return result({error:'not_linked'},422);
   if(!await rpc(jwt,'edge_reserve_codeforces_fetch',{},true))
     return result({error:'rate_slot_busy'},429);
   const profiles=await official('user.info',{handles:own.handle,checkHistoricHandles:'false'});
   if(profiles.length!==1||String(profiles[0].handle).toLowerCase()!==own.handle.toLowerCase())
     return result({error:'invalid_handle'},422);
   const profile=safeProfile(profiles[0]);
   const changed=await rpc(jwt,'edge_store_codeforces_profile',
    {account:own.id,expected_version:own.version,profile},true);
   if(!changed) return result({error:'stale_validation'},409);
   return result({profile,approval_status:'pending_approval'});
  }
  return result({error:'unsupported_action'},422);
 } catch {
  // No leakage of upstream headers, provider responses, or private infrastructure.
  return result({error:'provider_unavailable'},503);
 }
}
Deno.serve(handleCodeforces);
