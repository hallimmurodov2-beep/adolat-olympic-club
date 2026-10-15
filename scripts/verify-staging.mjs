// M8 hosted acceptance smoke. Run manually only against a NEW isolated staging project.
// Never logs JWTs. Intentionally requires real student identities for privacy check.
const {STAGING_URL,SUPABASE_URL,SUPABASE_PUBLISHABLE_KEY,
 STUDENT_A_JWT,STUDENT_B_JWT,STUDENT_A_PRIVATE_PLAN_ID}=process.env;
if(![STAGING_URL,SUPABASE_URL,SUPABASE_PUBLISHABLE_KEY,
 STUDENT_A_JWT,STUDENT_B_JWT,STUDENT_A_PRIVATE_PLAN_ID].every(Boolean)) {
 console.error('BLOCKED: supply isolated staging URLs, a public key, separate student JWTs and a synthetic private plan ID. No deployment performed.');
 process.exit(2);
}
function httpsOrigin(value) {
 const x=new URL(value);if(x.protocol!=='https:'||x.username||x.password||x.search||x.hash)
 throw Error('Expected a plain HTTPS origin');
 return x.origin;
}
const cloud=httpsOrigin(STAGING_URL),supabase=httpsOrigin(SUPABASE_URL);
if(cloud.includes('onrender.com'))throw Error('Legacy Render target refused');
async function get(url,headers={}) {
 const t=Date.now(),res=await fetch(url,{headers,redirect:'error',
  signal:AbortSignal.timeout(12000)});
 console.log(new URL(url).pathname,res.status,Date.now()-t+'ms');
 return res;
}
const shell=await get(cloud+'/');if(shell.status!==200)throw Error('No Cloudflare static shell');
const stylesheet=await get(cloud+'/static/styles.css');
if(stylesheet.status!==200)throw Error('Missing brand stylesheet');
async function plans(jwt) {
 const r=await get(supabase+'/rest/v1/my_training_plans?select=id',{
 'apikey':SUPABASE_PUBLISHABLE_KEY,'Authorization':'Bearer '+jwt,'Accept-Profile':'api'});
 if(r.status!==200)throw Error('Authenticated isolated Data API failed');
 return r.json();
}
const [a,b]=await Promise.all([plans(STUDENT_A_JWT),plans(STUDENT_B_JWT)]);
if(!Array.isArray(a)||!Array.isArray(b))throw Error('Unexpected Data API response');
if(!a.some(p=>p.id===STUDENT_A_PRIVATE_PLAN_ID))
 throw Error('Student A cannot read own synthetic plan');
if(b.some(p=>p.id===STUDENT_A_PRIVATE_PLAN_ID))
 throw Error('CRITICAL: Student B can read A private plan');
console.log('PASS: new static shell, assets and cross-student private-plan isolation');
console.log('PENDING: Auth browser flows, all M4/M5 journeys, uploads, Codeforces, realtime, backups, after-idle measurements.');
