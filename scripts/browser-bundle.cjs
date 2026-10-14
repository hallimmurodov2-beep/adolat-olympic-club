/* Test-only, dependency-free CommonJS bundling via the installed TypeScript compiler.
   The actual shipped application uses native browser ES modules, not this bundle. */
const fs=require('node:fs');const path=require('node:path');const cp=require('node:child_process');
let ts;try{ts=require('typescript');}catch{ts=require(path.join(cp.execSync('npm root -g',{encoding:'utf8'}).trim(),'typescript'));}
const root=path.resolve(__dirname,'..');let bundle='(()=>{const modules={},cache={};\n';
for(const file of fs.readdirSync(path.join(root,'frontend')).filter(f=>f.endsWith('.ts'))){
 const source=fs.readFileSync(path.join(root,'frontend',file),'utf8');
 const output=ts.transpileModule(source,{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.CommonJS}}).outputText;
 bundle+=`modules[${JSON.stringify('./'+file.replace(/\.ts$/,'.js'))}]=function(exports,require){\n${output}\n};\n`;
}
bundle+='function require(id){if(cache[id])return cache[id];const exports={};cache[id]=exports;if(!modules[id])throw new Error("Module not found: "+id);modules[id](exports,require);return exports;}require("./app.js");})();';
fs.writeFileSync(process.argv[2]||'/tmp/olympiados-browser-test.js',bundle);
