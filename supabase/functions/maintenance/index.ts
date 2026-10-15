// M7 maintenance: machine-only, idempotent, guarded secret.
const BASE=Deno.env.get('SUPABASE_URL')||'';
const SECRET=Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')||'';
const CRON=Deno.env.get('ADOLAT_CRON_SECRET')||'';
function secureEqual(a:string,b:string):boolean {
 const x=new TextEncoder().encode(a),y=new TextEncoder().encode(b);
 if(!x.length||!y.length)return false;
 let acc=x.length^y.length;
 for(let i=0;i<Math.max(x.length,y.length);i++)
  acc|=(x[i%x.length]||0)^(y[i%y.length]||0);
 return acc===0;
}
const response=(obj:unknown,status=200)=>Response.json(obj,{status,
 headers:{'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'}});
export async function maintain(req:Request) {
 if(req.method!=='POST')return response({error:'method_not_allowed'},405);
 if(!BASE||!SECRET||CRON.length<32||!secureEqual(req.headers.get('X-Adolat-Cron')||'',CRON))
 return response({error:'forbidden'},403);
 if(Deno.env.get('MAINTENANCE_ENABLED')!=='yes-reviewed')
 return response({error:'disabled'},503);
 try{
  const q=await fetch(BASE+'/rest/v1/rpc/edge_expire_uploads',{
   method:'POST',headers:{apikey:SECRET,Authorization:'Bearer '+SECRET,
    'Content-Type':'application/json','Content-Profile':'api'},
   body:'{"max_count":40}',redirect:'error',signal:AbortSignal.timeout(12000)});
  if(!q.ok)throw Error('rpc_error');
  const names=await q.json();
  if(!Array.isArray(names))throw Error('invalid_cleanup');
  let removed=0,failed=0;
  for(const name of names){
   if(typeof name!=='string'||!/^quarantine\/[0-9a-f-]{36}\/[0-9a-f-]{36}$/.test(name))
   {failed++;continue;}
   try{
    const res=await fetch(BASE+'/storage/v1/object/adolat-quarantine/'+name,{
     method:'DELETE',headers:{apikey:SECRET,Authorization:'Bearer '+SECRET},
     redirect:'error',signal:AbortSignal.timeout(8000)});
    if(res.ok||res.status===404)removed++;else failed++;
   }catch{failed++;}
  }
  return response({expired:names.length,removed,failed});
 }catch{return response({error:'temporarily_unavailable'},503);}
}
Deno.serve(maintain);
