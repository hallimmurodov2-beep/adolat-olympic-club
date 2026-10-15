// M7 reconnect-safe, bounded event cursor and invalidation polling fallback.
// The frontend must call start() after a valid session and stop() on logout.
// Events intentionally contain NO private text or assessment material.
import {serverlessRpc,ServerlessApiError} from './serverless-client.js';
type Change={id:number;kind:string;created_at:string};
type Page={events:Change[];server_now:number};
export class PrivateChangeCursor {
  private cursor=0;
  private timer:number|undefined;
  private inFlight=false;
  private cancelled=false;
  constructor(private readonly onChange:(events:readonly Change[])=>void,
    private readonly onAvailability?:(up:boolean)=>void){}
  start():void {
    this.stop();
    this.cancelled=false;
    void this.refresh();
    this.timer=window.setInterval(()=>{if(!document.hidden&&navigator.onLine)
      void this.refresh();},20000);
    window.addEventListener('online',this.foreground);
    document.addEventListener('visibilitychange',this.foreground);
  }
  private foreground=()=>{if(!document.hidden&&navigator.onLine&&!this.cancelled)
    void this.refresh();};
  async refresh():Promise<void> {
    if(this.inFlight||this.cancelled)return;
    this.inFlight=true;
    try {
      // The database enforces recipient ownership and active account status.
      const page=await serverlessRpc<Page>('events_since',
        {last_id:this.cursor,limit_count:100});
      if(this.cancelled)return;
      const events=Array.isArray(page.events)?page.events:[];
      if(events.length) {
        this.cursor=Math.max(this.cursor,...events.map(e=>e.id));
        this.onChange(events);
      }
      this.onAvailability?.(true);
      if(events.length===100)queueMicrotask(()=>{void this.refresh();});
    }catch(err) {
      if(err instanceof ServerlessApiError&&err.status===401)this.stop();
      this.onAvailability?.(false);
    }finally{this.inFlight=false;}
  }
  stop():void {
    this.cancelled=true;
    if(this.timer!==undefined)window.clearInterval(this.timer);
    this.timer=undefined;
    window.removeEventListener('online',this.foreground);
    document.removeEventListener('visibilitychange',this.foreground);
    this.cursor=0;
  }
}
