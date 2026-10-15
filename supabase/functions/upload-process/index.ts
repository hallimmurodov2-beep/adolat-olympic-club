// M6: private file finalizer, deliberately OFF until hosted byte-level tests pass.
// The Edge service reads only user-owned reservations and only from quarantine.
import {ImageMagick, initializeImageMagick, MagickFormat}
 from 'npm:@imagemagick/magick-wasm@^0';
const ORIGIN=Deno.env.get('SESSION_ORIGIN')||'';
const URL_BASE=Deno.env.get('SUPABASE_URL')||'';
const KEY=Deno.env.get('SUPABASE_PUBLISHABLE_KEY')||'';
const SECRET=Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')||'';
let imageRuntime:Promise<void>|null=null;
const MAX=8388608;
function response(body:unknown,status=200) {
 return Response.json(body,{status,headers:{'Cache-Control':'no-store',
 'X-Content-Type-Options':'nosniff','Access-Control-Allow-Origin':ORIGIN,
 'Vary':'Origin'}});
}
function checkOrigin(request:Request) {
 return ORIGIN.startsWith('https://')&&request.headers.get('Origin')===ORIGIN;
}
async function rpc(jwt:string,name:string,args:Record<string,unknown>,secret=false) {
 const res=await fetch(URL_BASE+'/rest/v1/rpc/'+name,{
 method:'POST',redirect:'error',signal:AbortSignal.timeout(12000),
 headers:{apikey:secret?SECRET:KEY,Authorization:'Bearer '+(secret?SECRET:jwt),
 'Content-Type':'application/json','Content-Profile':'api'},
 body:JSON.stringify(args)});
 if(!res.ok)throw Error('rpc_failed');
 return res.json();
}
async function storage(method:string,bucket:string,name:string,jwt:string,body?:Uint8Array,mime?:string) {
 if(!/^(adolat-quarantine|adolat-files)$/.test(bucket)||!/^([a-z-]+)\/[a-z0-9-\/]+$/.test(name)) {
  throw Error('invalid_object_name');
 }
 const res=await fetch(URL_BASE+'/storage/v1/object/'+bucket+'/'+name,{
 method,headers:{apikey:SECRET,Authorization:'Bearer '+SECRET,
 ...(body?{'Content-Type':mime||'application/octet-stream','x-upsert':'false'}:{})},
 body:body?body:undefined,redirect:'error',signal:AbortSignal.timeout(12000)});
 if(!res.ok)throw Error('storage_unavailable');
 return res;
}
async function hex(bytes:Uint8Array) {
 const digest=await crypto.subtle.digest('SHA-256',bytes);
 return Array.from(new Uint8Array(digest),x=>x.toString(16).padStart(2,'0')).join('');
}
async function normalize(raw:Uint8Array,mime:string) {
 if(mime==='application/pdf') {
  const text=new TextDecoder('latin1').decode(raw.slice(0,5));
  const tail=new TextDecoder('latin1').decode(raw.slice(-2048));
  if(text!=='%PDF-'||!tail.includes('%%EOF'))throw Error('invalid_pdf');
  return {bytes:raw,mime};
 }
 if(mime==='text/plain') {
  const content=new TextDecoder('utf-8',{fatal:true}).decode(raw);
  if(content.includes('\0'))throw Error('invalid_text');
  return {bytes:raw,mime};
 }
 if(!['image/jpeg','image/png','image/webp'].includes(mime))throw Error('invalid_format');
 // Re-encoding into PNG discards original metadata and trailing bytes.
 if(!imageRuntime) imageRuntime=(async()=>{
 const data=await Deno.readFile(new URL('magick.wasm',
  import.meta.resolve('npm:@imagemagick/magick-wasm@^0')));
 await initializeImageMagick(data);
 })();
 await imageRuntime;
 let bytes:Uint8Array|null=null;
 ImageMagick.read(raw,(image)=>{
   if(image.width<1||image.height<1||image.width*image.height>16000000)
    throw Error('oversized_pixels');
   image.strip();
   bytes=image.write(MagickFormat.Png,(out)=>Uint8Array.from(out));
 });
 if(!bytes||bytes.length<1||bytes.length>MAX) throw Error('invalid_image');
 return {bytes,mime:'image/png'};
}
export async function processUpload(request:Request) {
 if(!checkOrigin(request))return response({error:'forbidden'},403);
 if(request.method==='OPTIONS')return new Response(null,{status:204,headers:{
  'Access-Control-Allow-Origin':ORIGIN,
  'Access-Control-Allow-Headers':'authorization, apikey, content-type',
  'Access-Control-Allow-Methods':'POST, OPTIONS','Vary':'Origin'}});
 if(request.method!=='POST')return response({error:'method_not_allowed'},405);
 if(Deno.env.get('UPLOAD_PROCESS_ENABLED')!=='yes-reviewed'||!URL_BASE||!KEY||!SECRET)
  return response({error:'disabled'},503);
 const authorization=request.headers.get('Authorization')||'';
 if(!/^Bearer [A-Za-z0-9._-]+$/.test(authorization))return response({error:'unauthenticated'},401);
 const jwt=authorization.slice(7);
 try {
   const identity=await fetch(URL_BASE+'/auth/v1/user',{
    headers:{apikey:KEY,Authorization:'Bearer '+jwt},signal:AbortSignal.timeout(10000),
    redirect:'error'});
   if(!identity.ok)return response({error:'unauthenticated'},401);
   const uid=(await identity.json()).id;
   if(typeof uid!=='string')return response({error:'unauthenticated'},401);
   const body=await request.text();if(body.length>1000)return response({error:'invalid_input'},413);
   const {intent_id}=JSON.parse(body);
   if(typeof intent_id!=='string'||!/^[0-9a-f-]{36}$/.test(intent_id))
    return response({error:'invalid_input'},422);
   const pending=await rpc(jwt,'edge_upload_intent',{intent:intent_id},true);
   if(!pending||pending.owner_id!==uid||pending.state!=='reserved')
    return response({error:'invalid_reservation'},403);
   // Fresh, database-enforced owner and membership status; status cannot be cached.
   const mine=await rpc(jwt,'bootstrap',{});
   if(mine?.user?.id!==uid) return response({error:'revoked'},403);
   const upstream=await storage('GET','adolat-quarantine',pending.object_path,jwt);
   if(Number(upstream.headers.get('content-length')||0)>MAX)
     return response({error:'file_too_large'},413);
   const raw=new Uint8Array(await upstream.arrayBuffer());
   if(raw.length!==pending.expected_bytes||raw.length>MAX||raw.length===0)
     return response({error:'size_mismatch'},422);
   if(await hex(raw)!==pending.expected_sha256)
     return response({error:'hash_mismatch'},422);
   const clean=await normalize(raw,pending.media_type);
   // Our M6 reservation reserves the *input* size. Fail safely when a
   // normalized image grows beyond that reservation; never overcommit budget.
   if(clean.bytes.length>pending.expected_bytes)
    return response({error:'normalized_size_exceeds_reservation'},422);
   const name='accepted/'+intent_id;
   await storage('POST','adolat-files',name,jwt,clean.bytes,clean.mime);
   try {
     const fid=await rpc(jwt,'edge_finish_upload',{intent:intent_id,
     accepted_name:name,new_mime:clean.mime,clean_sha256:await hex(clean.bytes),
     clean_bytes:clean.bytes.length},true);
     // Cleanup quarantine only after durable DB acceptance.
     try{await storage('DELETE','adolat-quarantine',pending.object_path,jwt);}catch{}
     return response({id:fid,status:'accepted'},201);
   } catch {
     try{await storage('DELETE','adolat-files',name,jwt);}catch{}
     throw Error('failed_to_finalize');
   }
 } catch {
  return response({error:'processing_unavailable_or_invalid'},503);
 }
}
Deno.serve(processUpload);
