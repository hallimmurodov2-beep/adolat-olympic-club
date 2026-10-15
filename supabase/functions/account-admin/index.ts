// M3 protected Auth Admin invitation issuer, isolated staging only.
// Caller JWT verified by Supabase Auth and reauthorized in database RPC.
// Invite acceptance requires a verified account + one-time email-bound token.
import { createClient } from 'npm:@supabase/supabase-js@2';
const allowed = Deno.env.get('SESSION_ORIGIN') ?? '';
function respond(body:unknown,status=200) {
 return new Response(JSON.stringify(body),{status,headers:{
 'Content-Type':'application/json','Cache-Control':'no-store',
 'X-Content-Type-Options':'nosniff','Vary':'Origin'}});
}
Deno.serve(async request=>{
 if(!allowed.startsWith('https://')||request.method!=='POST'
 ||request.headers.get('Origin')!==allowed) return respond({error:'forbidden'},403);
 const url=Deno.env.get('SUPABASE_URL');
 const publishable=Deno.env.get('SUPABASE_PUBLISHABLE_KEY');
 const secret=Deno.env.get('SUPABASE_SERVICE_ROLE_KEY');
 if(!url||!publishable||!secret||
 Deno.env.get('ACCOUNT_ADMIN_ENABLED')!=='yes-reviewed') return respond({error:'disabled'},503);
 const authorization=request.headers.get('Authorization')??'';
 if(!/^Bearer [A-Za-z0-9._-]+$/.test(authorization)) return respond({error:'unauthenticated'},401);
 const jwt=authorization.slice(7);
 const actor=createClient(url,publishable,{global:{headers:{Authorization:authorization}},
 auth:{persistSession:false,autoRefreshToken:false}});
 const admin=createClient(url,secret,{auth:{persistSession:false,autoRefreshToken:false}});
 const {data:userData,error:userError}=await actor.auth.getUser(jwt);
 if(userError||!userData.user) return respond({error:'unauthenticated'},401);
 let body;
 try{body=await request.json();}catch{return respond({error:'invalid_input'},422);}
 if(!body||typeof body.email!=='string'||typeof body.role!=='string'
 ||body.email.length>254||!['student','teacher','admin'].includes(body.role)
 ||(body.classroom_id!=null&&typeof body.classroom_id!=='string'))
 return respond({error:'invalid_input'},422);
 // The RPC authorizes admin/teacher scope and creates a one-use token.
 const {data:issued,error:issueError}=await actor.schema('api')
 .rpc('issue_registration_invitation',{
 target_email:body.email,intended_role:body.role,target_classroom:body.classroom_id??null});
 if(issueError||!issued) return respond({error:'invitation_denied'},403);
 // Partial mail/provisioning failure leaves the account pending, not active.
 const {error:inviteError}=await admin.auth.admin.inviteUserByEmail(body.email,{
 redirectTo:allowed+'/#/register/'+encodeURIComponent(issued.token)
 });
 if(inviteError) return respond({error:'delivery_failed',invitation_id:issued.id},503);
 return respond({id:issued.id,expires_at:issued.expires_at,link:
  allowed+'/#/register/'+encodeURIComponent(issued.token)},201);
});
