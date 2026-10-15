import test from 'node:test';
import assert from 'node:assert/strict';
import {onRequest} from '../functions/api/session/[[path]].js';
const base='https://staging.example.pages.dev';
const env={BROKER_ENABLED:'yes-reviewed',SUPABASE_URL:'https://sample.supabase.co',
 SUPABASE_PUBLISHABLE_KEY:'sb_publishable_dummy',
 SESSION_ORIGIN:base};
function request(path,method='GET',opts={}) {
 const headers=new Headers(opts.headers||{});
 if(method==='POST'&&!opts.noOrigin&&!headers.has('Origin')) headers.set('Origin',base);
 return {env:{...env,...opts.env},request:new Request(base+'/api/session/'+path,{
 method,headers,body:opts.body})};
}
test('disabled by default / missing settings fail closed',async()=>{
 const r=await onRequest(request('access','GET',{env:{BROKER_ENABLED:'off'}}));
 assert.equal(r.status,503);assert.equal(r.headers.get('Set-Cookie'),null);
});
test('reject cross-origin mutating request',async()=>{
 const q=request('login','POST',{body:'{}',headers:{Origin:'https://evil.example'}});
 const r=await onRequest(q);assert.equal(r.status,403);
});
test('reject cross-site fetch metadata and invalid methods',async()=>{
 assert.equal((await onRequest(request('access','GET',{headers:{'Sec-Fetch-Site':'cross-site'}}))).status,403);
 assert.equal((await onRequest(request('login'))).status,405);
});
test('no cookie means no session; response has no cache',async()=>{
 const r=await onRequest(request('access'));assert.equal(r.status,401);
 assert.equal(r.headers.get('Cache-Control'),'no-store');
});
test('reject oversized or malformed credentials before provider',async()=>{
 const a=await onRequest(request('login','POST',{body:JSON.stringify({email:'',password:'x'.repeat(400)})}));
 assert.equal(a.status,422);
});
test('successful login issues secure HttpOnly cookie and memory-only JWT payload',async()=>{
 const original=globalThis.fetch;
 globalThis.fetch=async(input)=>{
   if(String(input).includes('/auth/v1/token')) return Response.json({
    access_token:'jwt-token',refresh_token:'refresh-token-0123456789012',expires_in:900});
   if(String(input).includes('/rest/v1/my_profile')) return Response.json([
    {user_id:'x',active:true,role:'student',locale:'en',display_name:'Example'}]);
   throw Error('unexpected call');
 };
 try {
   const r=await onRequest(request('login','POST',{body:JSON.stringify({email:'a@example.org',password:'long-secret'})}));
   assert.equal(r.status,200);
   const cookie=r.headers.get('Set-Cookie');
   assert.match(cookie,/Secure; HttpOnly; SameSite=Strict/);
   assert.match(cookie,/__Host-adolat-refresh=/);
   assert.equal(r.headers.get('Cache-Control'),'no-store');
   const obj=await r.json();assert.equal(obj.access_token,'jwt-token');
   assert.equal(JSON.stringify(obj).includes('refresh-token-0123'),false);
 } finally {globalThis.fetch=original;}
});
test('unauthorized profile cannot gain a refresh cookie',async()=>{
 const old=globalThis.fetch;globalThis.fetch=async(input)=>String(input).includes('token?')
 ? Response.json({access_token:'jwt',refresh_token:'refresh-token-0123456789',expires_in:900})
 : Response.json([]);
 try {const r=await onRequest(request('login','POST',{body:JSON.stringify({email:'a@b.org',password:'yes'})}));
  assert.equal(r.status,403);assert.equal(r.headers.get('Set-Cookie'),null);}
 finally{globalThis.fetch=old;}
});
