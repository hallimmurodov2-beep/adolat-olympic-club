// M6: per-request authenticated delivery; no reusable public/signed URLs.
const ORIGIN=Deno.env.get('SESSION_ORIGIN')||'';
const URL_BASE=Deno.env.get('SUPABASE_URL')||'';
const KEY=Deno.env.get('SUPABASE_PUBLISHABLE_KEY')||'';
const SECRET=Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')||'';
function reply(body:unknown,status=403) {return Response.json(body,{status,headers:{
 'Cache-Control':'no-store','Access-Control-Allow-Origin':ORIGIN,'Vary':'Origin'}});}
export async function deliver(request:Request) {
 if(!ORIGIN.startsWith('https://')||request.headers.get('Origin')!==ORIGIN)
  return reply({error:'forbidden'});
 if(request.method==='OPTIONS')return new Response(null,{status:204,headers:{
  'Access-Control-Allow-Origin':ORIGIN,'Access-Control-Allow-Methods':'POST, OPTIONS',
  'Access-Control-Allow-Headers':'authorization, apikey, content-type','Vary':'Origin'}});
 if(request.method!=='POST')return reply({error:'method_not_allowed'},405);
 if(Deno.env.get('FILE_DELIVERY_ENABLED')!=='yes-reviewed'||!URL_BASE||!KEY||!SECRET)
  return reply({error:'disabled'},503);
 const raw=request.headers.get('Authorization')||'';
 if(!/^Bearer [A-Za-z0-9._-]+$/.test(raw))return reply({error:'unauthenticated'},401);
 try {
  const body=await request.text();if(body.length>500)return reply({error:'invalid_input'},422);
  const {file_id}=JSON.parse(body);
  if(typeof file_id!=='string'||!/^[0-9a-f-]{36}$/.test(file_id))
   return reply({error:'invalid_file'},422);
  // Authorize *this* request with user's live JWT and current DB membership.
  const metaResp=await fetch(URL_BASE+'/rest/v1/rpc/file_metadata',{
   method:'POST',headers:{apikey:KEY,Authorization:raw,
    'Content-Type':'application/json','Content-Profile':'api'},
   body:JSON.stringify({file:file_id}),redirect:'error',signal:AbortSignal.timeout(10000)});
  if(!metaResp.ok)return reply({error:'not_found'},404);
  const meta=await metaResp.json();
  const loc=await fetch(URL_BASE+'/rest/v1/rpc/edge_file_location',{
    method:'POST',headers:{apikey:SECRET,Authorization:'Bearer '+SECRET,
    'Content-Type':'application/json','Content-Profile':'api'},
    body:JSON.stringify({fid:file_id}),redirect:'error',signal:AbortSignal.timeout(10000)});
  if(!loc.ok)return reply({error:'unavailable'},503);
  const name=await loc.json();
  if(typeof name!=='string'||!/^accepted\/[0-9a-f-]{36}$/.test(name))
   return reply({error:'not_found'},404);
  const blob=await fetch(URL_BASE+'/storage/v1/object/authenticated/adolat-files/'+name,{
    headers:{apikey:SECRET,Authorization:'Bearer '+SECRET},
    redirect:'error',signal:AbortSignal.timeout(12000)});
  if(!blob.ok)return reply({error:'unavailable'},503);
  // Force attachment for documents. Images may be displayed inline.
  const inline=meta.mime==='image/png'||meta.mime==='image/jpeg';
  const filename=encodeURIComponent(String(meta.filename||'file').slice(0,180));
  return new Response(blob.body,{status:200,headers:{
   'Cache-Control':'private, no-store','X-Content-Type-Options':'nosniff',
   'Content-Security-Policy':"default-src 'none'; sandbox",
   'Content-Disposition':(inline?'inline':'attachment')+"; filename*=UTF-8''"+filename,
   'Content-Type':meta.mime||'application/octet-stream',
   'Access-Control-Allow-Origin':ORIGIN,'Vary':'Origin'}});
 }catch{return reply({error:'temporarily_unavailable'},503);}
}
Deno.serve(deliver);
