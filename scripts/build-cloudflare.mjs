import { cp, mkdir, readFile, readdir, rm, writeFile } from 'node:fs/promises';
import { join } from 'node:path';
// M1 ONLY: packages an unauthenticated static shell. Auth and data are M3+ work.
// Fail rather than copy secrets, old database scripts, or hidden repository files.
const root = process.cwd(), staticDir = join(root, 'static'), outDir = join(root, 'dist');
for (const f of ['index.html','styles.css','math-config.js','assets/app.js','brand/logo-login.png','vendor/prism.js']) await readFile(join(staticDir,f));
for (const lang of ['ru','en']) {
  const data=JSON.parse(await readFile(join(root,'locales',lang+'.json'),'utf8'));
  if (!data || typeof data!=='object' || Array.isArray(data)) throw Error('Invalid '+lang+' locale');
}
await rm(outDir,{recursive:true,force:true});
await mkdir(join(outDir,'static'),{recursive:true});
const allow = new Set(['assets','brand','vendor','styles.css','math-config.js','favicon.svg','manifest.webmanifest']);
for(const file of await readdir(staticDir,{withFileTypes:true})) {
  if(!allow.has(file.name)) continue;
  await cp(join(staticDir,file.name),join(outDir,'static',file.name),{
    recursive:true,filter:(src)=>!src.endsWith('.map')
  });
}
await cp(join(staticDir,'index.html'),join(outDir,'index.html'));
await cp(join(root,'locales'),join(outDir,'locales'),{recursive:true});
const headers = `/*
  X-Content-Type-Options: nosniff
  Referrer-Policy: no-referrer
  X-Frame-Options: DENY
  Permissions-Policy: camera=(), microphone=(), geolocation=()
  Content-Security-Policy: default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' blob: data:; font-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'

/index.html
  Cache-Control: no-cache

/locales/*
  Cache-Control: no-cache
`;
await writeFile(join(outDir,'_headers'),headers);
await writeFile(join(outDir,'_routes.json'),JSON.stringify({version:1,include:['/api/session/*'],exclude:[]},null,2)+'\n');
const html=await readFile(join(outDir,'index.html'),'utf8');
if(!html.includes('/static/assets/app.js') || !html.includes('/static/styles.css')) throw Error('Asset URLs changed');
console.log('Cloudflare static shell packaged; authenticated flows require M3.');
