// M3–M5 staging-only data transport. Not yet wired into legacy UI endpoints.
// Secrets never enter browser state; only a publishable key and memory-only access JWT.
export type ServerlessPublicConfig = Readonly<{
  supabaseUrl: string;
  publishableKey: string;
}>;
type BrokerSession = {
  access_token:string; expires_in:number;
  profile:{user_id:string;role:'student'|'teacher'|'admin';active:boolean;display_name:string;locale:'ru'|'en'};
  server_now:number;
};
export class ServerlessApiError extends Error {
  constructor(readonly code:string, readonly status:number) {super(code);this.name='ServerlessApiError';}
}
let cfg:ServerlessPublicConfig|null=null;
let accessToken:string|null=null;
let expiresAt=0;
let refreshInFlight:Promise<BrokerSession>|null=null;
function apiOrigin():string {
  if(!cfg) throw new ServerlessApiError('not_configured',503);
  return new URL(cfg.supabaseUrl).origin;
}
export function configureServerlessApi(value:ServerlessPublicConfig):void {
  const url=new URL(value.supabaseUrl);
  if(url.protocol!=='https:'||url.username||url.password||url.hash||url.search
    ||!/^sb_publishable_[A-Za-z0-9_-]+$/.test(value.publishableKey)) {
    throw new ServerlessApiError('invalid_public_configuration',400);
  }
  cfg={supabaseUrl:url.origin,publishableKey:value.publishableKey};
  accessToken=null;expiresAt=0;
}
export function clearServerlessSession():void {accessToken=null;expiresAt=0;}
async function broker(path:'login'|'access'|'logout',body?:unknown):Promise<BrokerSession> {
  const method=path==='access'?'GET':'POST';
  let response:Response;
  try {
    response=await fetch('/api/session/'+path,{method,credentials:'same-origin',
      headers:method==='POST'?{'Content-Type':'application/json'}:undefined,
      body:body===undefined?undefined:JSON.stringify(body),cache:'no-store'});
  } catch {throw new ServerlessApiError('network',0);}
  if(!response.ok) {
    clearServerlessSession();
    throw new ServerlessApiError(response.status===401?'unauthenticated':'broker_unavailable',response.status);
  }
  return response.json() as Promise<BrokerSession>;
}
function install(session:BrokerSession):BrokerSession {
  if(!session.access_token||!session.profile?.active||!Number.isFinite(session.expires_in))
    throw new ServerlessApiError('invalid_broker_response',502);
  accessToken=session.access_token;
  // Refresh in advance, never persist bearer credentials in web storage.
  expiresAt=Date.now()+Math.max(0,session.expires_in-45)*1000;
  return session;
}
export async function loginServerless(email:string,password:string):Promise<BrokerSession> {
  return install(await broker('login',{email,password}));
}
export async function restoreServerlessSession():Promise<BrokerSession> {
  if(refreshInFlight) return refreshInFlight;
  refreshInFlight=broker('access').then(install).finally(()=>{refreshInFlight=null;});
  return refreshInFlight;
}
export async function logoutServerless():Promise<void> {
  // Do not silently report a successful remote logout if revocation fails.
  try {await broker('logout',{});} finally{clearServerlessSession();}
}
async function token():Promise<string> {
  if(!accessToken||Date.now()>=expiresAt) await restoreServerlessSession();
  if(!accessToken) throw new ServerlessApiError('unauthenticated',401);
  return accessToken;
}
export async function serverlessRpc<T>(functionName:string,args:Record<string,unknown>={}):Promise<T> {
  if(!/^[a-z][a-z0-9_]*$/.test(functionName)) throw new ServerlessApiError('invalid_function',400);
  const bearer=await token();
  let response:Response;
  try {
    response=await fetch(apiOrigin()+'/rest/v1/rpc/'+functionName,{
      method:'POST',cache:'no-store',redirect:'error',
      headers:{'Content-Type':'application/json','apikey':cfg!.publishableKey,
        'Authorization':'Bearer '+bearer,'Content-Profile':'api','Accept-Profile':'api'},
      body:JSON.stringify(args)
    });
  } catch {throw new ServerlessApiError('network',0);}
  if(!response.ok) {
    if(response.status===401) clearServerlessSession();
    throw new ServerlessApiError('rpc_rejected',response.status);
  }
  return response.json() as Promise<T>;
}
export async function serverlessView<T>(view:string,query=''):Promise<T> {
  if(!/^[a-z][a-z0-9_]*$/.test(view)||query.length>2000)
    throw new ServerlessApiError('invalid_view',400);
  const bearer=await token();
  const response=await fetch(apiOrigin()+'/rest/v1/'+view+(query?'?'+query:''),{
    cache:'no-store',redirect:'error',
    headers:{'apikey':cfg!.publishableKey,
      'Authorization':'Bearer '+bearer,'Accept-Profile':'api'}
  });
  if(!response.ok) throw new ServerlessApiError('view_rejected',response.status);
  return response.json() as Promise<T>;
}
export const domain = {
  bootstrap:()=>serverlessRpc<Record<string,unknown>>('bootstrap'),
  myPrivatePlans:()=>serverlessView<Record<string,unknown>[]>('my_training_plans'),
  createClassroom:(subject:string,classroom_name:Record<string,string>)=>
    serverlessRpc<string>('create_classroom',{subject,classroom_name}),
  myClassrooms:()=>serverlessView<Record<string,unknown>[]>('my_classrooms'),
  classroomProblems:(room:string)=>serverlessRpc<Record<string,unknown>[]>(
    'list_classroom_problems',{room}),
  submitPersonal:(item:string,client_id:string,answer:unknown)=>
    serverlessRpc<Record<string,unknown>>('submit_personal_attempt',{item,client_id,answer}),
  createCycle:(cycle_title:Record<string,string>)=>
    serverlessRpc<string>('create_personal_cycle',{cycle_title}),
  savePlan:(cycle:string,goal:string,version:number)=>
    serverlessRpc<{id:string;version:number}>('save_personal_plan',
      {cycle,plan_goal:goal,plan_review:'',plan_next_step:'',plan_context:{},expected_version:version}),
  createCircle:(circle_name:Record<string,string>)=>
    serverlessRpc<string>('create_training_circle',{circle_name,is_discoverable:true})
};
