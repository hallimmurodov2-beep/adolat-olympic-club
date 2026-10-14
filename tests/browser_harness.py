"""Browser test transport adapter for environments whose Chromium URL policy blocks navigation.

BROWSER_BRIDGE=1 mounts the real built UI in a DOM and forwards fetch/SSE to a real,
local HTTP server via httpx. It does not invent API responses, bypass authorization,
change browser policies, or modify the application. Default mode uses normal navigation.
CSP and cookie flags are covered by independent HTTP tests, not this DOM transport.
"""
from __future__ import annotations
import base64
import json
import os
from pathlib import Path
import queue
import re
import subprocess
import threading
import httpx

ROOT=Path(__file__).resolve().parents[1]

BRIDGE_JS=r'''
(()=>{
 if(!crypto.randomUUID)crypto.randomUUID=()=>{const bytes=crypto.getRandomValues(new Uint8Array(16));bytes[6]=(bytes[6]&15)|64;bytes[8]=(bytes[8]&63)|128;const value=[...bytes].map(b=>b.toString(16).padStart(2,'0')).join('');return value.slice(0,8)+'-'+value.slice(8,12)+'-'+value.slice(12,16)+'-'+value.slice(16,20)+'-'+value.slice(20);};
 const storage=()=>{const data=new Map();return {getItem:k=>data.get(String(k))??null,setItem:(k,v)=>data.set(String(k),String(v)),removeItem:k=>data.delete(String(k)),clear:()=>data.clear(),key:n=>[...data.keys()][n]??null,get length(){return data.size}}};
 Object.defineProperty(window,'localStorage',{value:storage()});Object.defineProperty(window,'sessionStorage',{value:storage()});
 window.fetch=async(url,options={})=>{let body=options.body;let files=null;if(body instanceof FormData){files=[];for(const [name,value] of body.entries()){if(value instanceof File){const bytes=new Uint8Array(await value.arrayBuffer());let text='';for(const byte of bytes)text+=String.fromCharCode(byte);files.push({name,filename:value.name,type:value.type,data:btoa(text)});}}body=null;}
 const result=await window._osFetch(String(url),{method:options.method||'GET',headers:options.headers||{},body,files});return new Response(result.body,{status:result.status,headers:result.headers});};
 class HTTPEventSource{
  constructor(url){this.listeners={};this.closed=false;this.id=null;this.onerror=null;this.readyState=0;this.start(url);}
  addEventListener(name,fn){(this.listeners[name]??=[]).push(fn);}
  async start(url){this.id=await window._osOpenStream(url);if(this.closed){window._osCloseStream(this.id);return;}this.timer=setInterval(async()=>{if(this.closed)return;const messages=await window._osReadStream(this.id);for(const message of messages){const event=new MessageEvent(message.event,{data:message.data,lastEventId:message.id||''});if(message.event==='error'){this.onerror?.(event);continue;}this.readyState=1;for(const fn of this.listeners[message.event]||[])fn(event);}},100);}
  close(){this.closed=true;this.readyState=2;clearInterval(this.timer);if(this.id!==null)window._osCloseStream(this.id);}
 }
 window.EventSource=HTTPEventSource;
})();
'''

class BrowserTab:
    def __init__(self,browser,url,viewport=None):
        self.url=url
        self.page=browser.new_page(viewport=viewport or {'width':1440,'height':1100})
        self.page.set_default_timeout(8000)
        self.errors=[]
        self.page.on('pageerror',lambda error:self.errors.append(str(error)))
        self.page.on('console',lambda message:self.errors.append(message.text) if message.type=='error' and ('Missing translation' in message.text or 'Refused' in message.text) else None)
        self.http=httpx.Client(base_url=url,timeout=15)
        self.streams={};self.sequence=0
        if os.getenv('BROWSER_BRIDGE')!='1':
            self.page.goto(url);return
        self.page.expose_function('_osFetch',self.fetch)
        self.page.expose_function('_osOpenStream',self.open_stream)
        self.page.expose_function('_osReadStream',self.read_stream)
        self.page.expose_function('_osCloseStream',self.close_stream)
        html=(ROOT/'static/index.html').read_text()
        html=re.sub(r'<script\b[^>]*>[\s\S]*?</script>','',html)
        html=re.sub(r'<link\b[^>]*>','',html)
        self.page.set_content(html)
        self.page.add_style_tag(content=(ROOT/'static/styles.css').read_text())
        self.page.add_script_tag(content=BRIDGE_JS)
        # This supplementary DOM harness has no origin for relative image URLs.
        # Embed the exact local public asset bytes, not a fabricated screenshot.
        brand_assets={('/static/brand/'+p.name):'data:image/png;base64,'+base64.b64encode(p.read_bytes()).decode()
                      for p in (ROOT/'static/brand').glob('*.png')}
        self.page.add_script_tag(content="const brandAssets="+json.dumps(brand_assets)+";new MutationObserver(()=>{document.querySelectorAll('img').forEach(img=>{const path=img.getAttribute('src');if(brandAssets[path]){img.removeAttribute('srcset');img.src=brandAssets[path];}});}).observe(document.documentElement,{childList:true,subtree:true});")

        self.page.add_script_tag(content=(ROOT/'static/math-config.js').read_text())
        self.page.add_script_tag(content=(ROOT/'static/vendor/mathjax-tex-svg.js').read_text())
        self.page.add_script_tag(content=(ROOT/'static/vendor/prism.js').read_text())
        bundle=Path('/tmp/olympiados-browser-test.js')
        if not bundle.exists():subprocess.run(['node',str(ROOT/'scripts/browser-bundle.cjs'),str(bundle)],check=True)
        self.page.add_script_tag(content=bundle.read_text())
    def fetch(self,url,options):
        # Only the explicitly supplied local test application is reachable through this adapter.
        if not url.startswith('/') or url.startswith('//'):raise ValueError('Nonlocal test request')
        headers={**options['headers'],'Origin':self.url}
        if options.get('files'):
            files=[(f['name'],(f['filename'],base64.b64decode(f['data']),f['type'])) for f in options['files']]
            response=self.http.request(options['method'],url,headers=headers,files=files)
        else:response=self.http.request(options['method'],url,headers=headers,content=options.get('body'))
        return {'status':response.status_code,'body':response.text,'headers':{'Content-Type':response.headers.get('content-type','text/plain')}}
    def open_stream(self,url):
        if not re.fullmatch(r'/api/events(?:\?cursor=\d{1,18})?',url):raise ValueError('Invalid event endpoint')
        self.sequence+=1;sid=self.sequence
        state={'queue':queue.Queue(),'stop':threading.Event(),'response':None}
        self.streams[sid]=state;cookies=httpx.Cookies(self.http.cookies)
        def reader():
            try:
                with httpx.Client(base_url=self.url,cookies=cookies,timeout=httpx.Timeout(15)) as client:
                    with client.stream('GET',url) as response:
                        state['response']=response
                        if response.status_code!=200:
                            state['queue'].put({'event':'error','data':'{}'});return
                        event={'event':'message','data':'','id':''}
                        for line in response.iter_lines():
                            if state['stop'].is_set():return
                            if not line:
                                if event['data']:state['queue'].put(event.copy())
                                event={'event':'message','data':'','id':''}
                            elif ':' in line:
                                key,value=line.split(':',1)
                                if key in event:event[key]=value.strip()
            except Exception:
                if not state['stop'].is_set():state['queue'].put({'event':'error','data':'{}'})
        threading.Thread(target=reader,daemon=True).start()
        return sid
    def read_stream(self,sid):
        result=[];state=self.streams.get(sid)
        if state:
            while True:
                try:result.append(state['queue'].get_nowait())
                except queue.Empty:break
        return result
    def close_stream(self,sid):
        state=self.streams.get(sid)
        if state:
            state['stop'].set()
            response=state.get('response')
            if response is not None:
                try:response.close()
                except (OSError,httpx.HTTPError):pass
    def goto(self,path):
        self.page.evaluate('(path)=>{location.hash=path}',path)
    def login(self,handle,password,locale='ru'):
        self.page.wait_for_selector('#auth-form')
        self.page.click('[data-locale='+locale+']')
        self.page.fill('[name=email]',handle+'@demo.school.test')
        self.page.fill('[name=password]',password)
        self.page.click('#auth-form button[type=submit]')
        self.page.wait_for_selector('.sidebar')
        self.page.wait_for_selector('#main h1')
    def close(self):
        # Let the application's own session cleanup stop polling/streams before
        # destroying the page, so exposed bridge bindings can finish safely.
        if not self.page.is_closed():
            self.page.evaluate("window.dispatchEvent(new Event('auth-expired'))")
            self.page.wait_for_timeout(200)
        for sid in self.streams:self.close_stream(sid)
        self.page.close();self.http.close()
