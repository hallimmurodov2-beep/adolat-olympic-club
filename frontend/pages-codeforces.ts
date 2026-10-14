import { api } from './api.js';
import { date, number, t } from './i18n.js';
import { state, serverNow } from './state.js';
import { refresh, routeURL, setCleanup, setView } from './router.js';
import { bindForm, button, checkbox, empty, field, formActions, formChecked, formValue, h, icon, linkButton, onAction, panel, selectField, textarea, titleBlock, toast, confirmAction } from './ui.js';
import type { CFState, Contests, Leaderboard, LeaderRow, Participation } from './types-training.js';

const outward=(url:string,label:string,cls='link')=>`<a class="${cls}" href="${h(url)}" rel="noopener noreferrer" target="_blank">${h(label)} ${icon('arrow')}</a>`;
const updated=(value:number|null)=>value===null?t('cf.not_updated'):date(value);
const zone=()=>Intl.DateTimeFormat().resolvedOptions().timeZone;
const localDate=(instant:number)=>new Intl.DateTimeFormat(state.locale==='ru'?'ru-RU':'en-GB',{dateStyle:'medium',timeStyle:'short'}).format(instant);
const rank=(value:string|null)=>{if(!value)return '—';const known=['newbie','pupil','specialist','expert','candidate master','master','international master','grandmaster','international grandmaster','legendary grandmaster'];return known.includes(value)?t('cf.rank_'+value.replaceAll(' ','_')):value;};
const navigation=()=>`<nav class="training-tabs" aria-label="${h(t('nav.informatics'))}">${linkButton(t('nav.training'),'/training','assignment','primary')}${linkButton(t('nav.circles'),'/circles','group','secondary')}${state.user?.role==='student'?linkButton(t('cf.account'),'/informatics/account','user','secondary'):''}</nav>`;

function countdown(at:number):string{
    const remaining=Math.max(0,Math.ceil((at-serverNow())/60000));
    if(!remaining)return t('cf.starting');
    return t('cf.countdown',{days:Math.floor(remaining/1440),hours:Math.floor(remaining%1440/60),minutes:remaining%60});
}

export function contestHTML(data:Contests):string{
    return `<p class="field-help">${h(t('cf.contests_note'))}</p>`+
        (data.stale?`<div class="notice warning">${h(t(data.available?'cf.stale':'cf.unavailable'))}</div>`:'')+
        `<div class="contest-grid">${data.items.map(c=>`<article class="contest-card"><span class="eyebrow">Codeforces</span><h3>${h(c.name)}</h3><p><time datetime="${new Date(c.starts_at).toISOString()}">${h(localDate(c.starts_at))}</time></p><p>${h(t('cf.duration',{minutes:number(c.duration_seconds/60)}))}</p><strong class="contest-countdown" data-contest-start="${c.starts_at}" role="timer" aria-live="off">${h(countdown(c.starts_at))}</strong>${outward(c.url,t('cf.contest_link'))}</article>`).join('')}</div>`+
        (!data.items.length&&data.available?`<p>${h(t('cf.no_contests'))}</p>`:'')+
        `<div class="provider-footer"><small>${h(t('cf.updated'))}: ${h(updated(data.last_updated_at))}<br>${h(t('cf.timezone',{zone:zone()}))}</small>${outward(data.source_url,t('cf.all_contests'))}</div>`;
}
function runCountdowns():void{
    const update=()=>document.querySelectorAll<HTMLElement>('[data-contest-start]').forEach(el=>{el.textContent=countdown(Number(el.dataset.contestStart));});
    update();const timer=setInterval(()=>{if(!document.hidden)update();},1000);setCleanup(()=>clearInterval(timer));
    // Only local DOM updates: countdowns never trigger API requests.
}
function rankingTable(items:LeaderRow[]):string{
    if(!items.length)return empty(t('cf.empty'),t('cf.opt_note'));
    return `<div class="table-wrap"><table class="cf-table"><caption class="visually-hidden">${h(t('cf.ratings'))}</caption><thead><tr><th>#</th>${['cf.handle','cf.rating','cf.max_rating','cf.rank','cf.updated'].map(k=>`<th scope="col">${h(t(k))}</th>`).join('')}</tr></thead><tbody>${items.map(row=>`<tr class="${row.rating===null?'unrated-row':''}"><td>${row.position??'—'}</td><th scope="row">${outward(row.profile_url,row.handle)}<small class="school-approved">${icon('check')}${h(t('cf.school_approved'))}</small></th><td class="rating-value">${row.rating===null?h(t('cf.unrated')):h(number(row.rating))}</td><td>${row.max_rating===null?'—':h(number(row.max_rating))}</td><td>${h(rank(row.rank))}</td><td><time datetime="${new Date(row.last_updated_at).toISOString()}">${h(updated(row.last_updated_at))}</time>${row.stale?`<small class="stale-label">${h(t('cf.stale'))}</small>`:''}</td></tr>`).join('')}</tbody></table></div>`;
}

export async function informaticsPage():Promise<void>{
    const participation=await api<Participation>('/subjects/mine');
    if(state.user?.role==='student'&&!participation.can_train){setView(titleBlock(t('nav.informatics'),t('cf.subtitle'))+empty(t('training.empty'),t('training.no_participation'),linkButton(t('nav.training'),'/training','assignment')));return;}
    setView(titleBlock(t('nav.informatics'),t('cf.subtitle'))+navigation()+
        `<section class="informatics-hero"><div><p class="eyebrow">ADOLAT OLYMPIC CLUB</p><h2>${h(t('training.empty'))}</h2><p>${h(t('training.subtitle'))}</p>${linkButton(t('nav.training'),'/training','arrow','primary')}</div><div class="training-loop" aria-hidden="true">${icon('assignment')}${icon('arrow')}${icon('code')}${icon('arrow')}${icon('group')}</div></section>`+
        panel(t('cf.contests'),`<div class="panel-body hub-provider-body"><div id="hub-contests" aria-busy="true"><p>${h(t('app.loading'))}</p></div></div>`,button(t('cf.refresh'),'refresh-contests','clock','ghost small'))+
        `<div class="section-header"><h2>${h(t('cf.ratings'))}</h2>${linkButton(t('action.view_all'),'/informatics/leaderboard','arrow','secondary')}</div><section class="panel hub-leaderboard-panel"><div id="hub-leaderboard" class="panel-body" aria-busy="true"><p>${h(t('app.loading'))}</p></div></section>`);
    let disposed=false;setCleanup(()=>{disposed=true;});
    // Provider work is isolated from the first useful training action and from the
    // rest of the dashboard. A Codeforces failure never replaces the application.
    const loadContests=async()=>{try{const data=await api<Contests>('/informatics/contests/upcoming');if(disposed)return;document.getElementById('hub-contests')!.innerHTML=contestHTML(data);document.getElementById('hub-contests')!.setAttribute('aria-busy','false');}catch{if(!disposed)document.getElementById('hub-contests')!.innerHTML=`<div class="notice">${h(t('cf.unavailable'))}</div>${outward('https://codeforces.com/contests',t('cf.all_contests'))}`;}};
    onAction('refresh-contests',async el=>{el.disabled=true;try{await loadContests();}finally{el.disabled=false;}});
    // Sequential loads avoid two cold-cache requests competing for the shared budget.
    await loadContests();if(disposed)return;runCountdowns();
    try{const data=await api<Leaderboard>('/informatics/leaderboard?limit=5');if(!disposed){document.getElementById('hub-leaderboard')!.innerHTML=rankingTable(data.items);document.getElementById('hub-leaderboard')!.setAttribute('aria-busy','false');}}
    catch{if(!disposed)document.getElementById('hub-leaderboard')!.innerHTML=`<p>${h(t('cf.unavailable'))}</p>`;}
}

export async function leaderboardPage():Promise<void>{
    const offset=Number(routeURL().searchParams.get('offset')??0);
    const data=await api<Leaderboard>('/informatics/leaderboard?offset='+Math.max(0,offset));
    setView(titleBlock(t('cf.ratings'),t('cf.sort_note'))+navigation()+`<div class="notice">${h(t('cf.opt_note'))} ${h(t('cf.approval_note'))}</div>`+panel(t('cf.ratings'),`<div class="panel-body">${rankingTable(data.items)}</div>`)+
        `<div class="section-header">${offset?linkButton(t('action.back'),'/informatics/leaderboard?offset='+Math.max(0,offset-50),'back','secondary'):''}${data.next_offset!==null?linkButton(t('training.more'),'/informatics/leaderboard?offset='+data.next_offset,'arrow','secondary'):''}</div>`);
}

export async function cfAccountPage():Promise<void>{
    const data=await api<CFState>('/informatics/codeforces/me');const a=data.account;
    setView(titleBlock(t('cf.account'),t('cf.change_note'))+navigation()+
        `<div class="two-col"><section class="stack"><div class="panel"><div class="panel-body"><span class="badge">${h(t('cf.'+data.state))}</span>${a?.last_error?`<p class="notice warning">${h(t('cf.'+a.last_error))}</p>`:''}${a?.profile?`<h2>${outward(a.profile.profile_url,a.profile.handle)}</h2><p>${h(t('cf.rating'))}: <strong>${a.profile.rating===null?h(t('cf.unrated')):h(number(a.profile.rating))}</strong> · ${h(t('cf.max_rating'))}: ${a.profile.max_rating===null?'—':h(number(a.profile.max_rating))}</p><p>${h(rank(a.profile.rank))}</p>`:''}<small>${h(t('cf.updated'))}: ${h(updated(a?.last_success_at??null))}</small></div></div>`+
        `<form id="cf-link" class="form-panel">${field(t('cf.handle'),'handle',a?.handle??'','text','required minlength="3" maxlength="24" pattern="[A-Za-z0-9_.\\-]+" autocomplete="off" autocapitalize="none" spellcheck="false"')}${checkbox(t('cf.consent'),'consent')}<p class="field-help">${h(t('cf.ownership'))}</p>${formActions(t('cf.connect'))}</form></section>`+
        `<section class="stack"><div class="panel"><div class="panel-body"><h2>${h(t('cf.ratings'))}</h2><p>${h(t('cf.opt_note'))}</p>${a?`<form id="cf-consent">${checkbox(t('cf.opt_in'),'opt_in',a.leaderboard_opt_in)}${formActions()}</form>`:''}</div></div>${a?`<div class="provider-actions">${button(t('cf.refresh'),'cf-refresh','clock','secondary')}${button(t('cf.disconnect'),'cf-disconnect','logout','danger')}</div>`:''}<p class="field-help">${h(t('privacy.training'))}</p></section></div>`);
    bindForm('cf-link',async form=>{if(!formChecked(form,'consent'))throw new Error(t('cf.consent'));await api('/integrations/codeforces/account','PUT',{handle:formValue(form,'handle'),consent:true});state.dirty=false;await refresh();});
    bindForm('cf-consent',async form=>{await api('/integrations/codeforces/leaderboard-consent','POST',{opt_in:formChecked(form,'opt_in')});state.dirty=false;toast(t('app.saved'));await refresh();});
    onAction('cf-refresh',async el=>{el.disabled=true;try{await api('/integrations/codeforces/validate','POST',{});await refresh();}finally{el.disabled=false;}});
    onAction('cf-disconnect',async()=>{if(await confirmAction(t('cf.disconnect_confirm'))){await api('/integrations/codeforces/account','DELETE');state.dirty=false;await refresh();}});
}

export async function cfApprovalsPage():Promise<void>{
    const data=await api<{items:(CFState&{student_name:string})[]}>('/admin/codeforces/approvals');
    setView(titleBlock(t('nav.cf_approvals'),t('cf.ownership'))+`<p class="notice">${h(t('cf.approval_note'))}</p>`+
        (data.items.length?`<div class="training-grid">${data.items.map(d=>{const a=d.account!;return `<article class="panel approval-card"><div class="panel-body"><h2>${h(d.student_name)}</h2><p>${h(a.handle)} · <span class="badge">${h(t('cf.'+d.state))}</span></p><small>${h(t('cf.updated'))}: ${h(updated(a.last_success_at))}</small><form id="cf-review-${h(a.id)}">${selectField(t('cf.method'),'method',[{value:'observed_login',label:t('cf.observed_login')},{value:'school_equivalent',label:t('cf.school_equivalent')}])}${textarea(t('moderation.reason'),'reason','',2,'maxlength="500"')}${selectField(t('common.status'),'action',[...(a.approval_status==='pending_approval'?[{value:'approve',label:t('cf.approve')}]:[]),{value:'reject',label:t('cf.reject')},{value:'revoke',label:t('cf.revoke')}])}${formActions(t('action.confirm'))}</form></div></article>`;}).join('')}</div>`:empty(t('cf.approvals_empty'),'')));
    for(const d of data.items){const a=d.account!;bindForm('cf-review-'+a.id,async form=>{const action=formValue(form,'action');if(!await confirmAction(t(action==='approve'?'cf.ownership':'action.confirm')))return;await api('/admin/codeforces/approvals/'+a.id,'POST',{version:a.version,action,method:action==='approve'?formValue(form,'method'):null,reason:formValue(form,'reason')});state.dirty=false;await refresh();});}
}
