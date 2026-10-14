import { api } from './api.js';
import { date, dateInput, parseDateInput, plain, t } from './i18n.js';
import { serverNow, state } from './state.js';
import { navigate, refresh, routeURL, setView } from './router.js';
import { bilingual, biValue, bindForm, button, checkbox, confirmAction, content, empty, field, formActions, formChecked, formValue, h, icon, linkButton, onAction, panel, selectField, textarea, titleBlock, toast } from './ui.js';
const shortBi = (name, label, value = {}, required = false) => bilingual(name, label, value, required, 2).replaceAll('maxlength="50000"', 'maxlength="2000"');
const noteField = (label, name, value = {}) => textarea(label, name, value[state.locale] ?? plain(value), 3, 'maxlength="2000"');
const noteValue = (form, name, prior = {}) => ({ ...prior, [state.locale]: formValue(form, name).trim() });
const privacy = () => `<p class="training-privacy">${icon('lock')}${h(t('training.private'))}</p>`;
const trainingNav = () => `<nav class="training-tabs" aria-label="${h(t('nav.informatics'))}">${linkButton(t('nav.training'), '/training', 'assignment', 'secondary')}${linkButton(t('nav.circles'), '/circles', 'group', 'secondary')}${linkButton(t('nav.informatics'), '/informatics', 'code', 'secondary')}</nav>`;
const outward = (url, label, cls = 'link') => `<a class="${cls}" href="${h(url)}" target="_blank" rel="noopener noreferrer">${h(label)} ${icon('arrow')}</a>`;
const period = (cycle) => `${date(cycle.starts_at, false)} — ${date(cycle.ends_at, false)}`;
export async function trainingPage() {
    const [participation, plans, cycles] = await Promise.all([api('/subjects/mine'), api('/training/plans'), api('/training/cycles')]);
    const cards = (items) => items.map(p => `<a class="training-card panel" href="#/training/plans/${h(p.id)}">${privacy()}<h2>${content(p.context.title)}</h2><p>${content(p.goal)}</p><small>${h(period(p.context))}</small>${p.read_only ? `<span class="badge">${h(t('common.read_only'))}</span>` : ''}</a>`).join('');
    setView(titleBlock(t('nav.training'), t('training.subtitle'), participation.can_train ? linkButton(t('training.new'), '/training/new', 'plus') : '') + trainingNav() +
        (!participation.can_train ? `<div class="notice">${h(t('training.no_participation'))}</div>` : `<div class="training-intro">${icon('code')}<p>${h(t('training.no_teacher'))}</p></div>`) +
        `<div id="training-plan-list" class="training-grid">${cards(plans.items)}</div>` +
        (!plans.items.length ? empty(t('training.empty'), t('training.goal_help'), participation.can_train ? linkButton(t('training.new'), '/training/new', 'plus') : '') : '') +
        `<div id="training-more">${plans.next_cursor ? button(t('training.more'), 'more-plans') : ''}</div>` +
        (cycles.items.some(c => !c.my_plan_id) ? panel(t('training.create_plan'), cycles.items.filter(c => !c.my_plan_id).map(c => `<a class="list-row" href="#/training/cycles/${h(c.id)}">${content(c.title)}</a>`).join('')) : '') +
        `<div class="section-header">${button(t('training.export'), 'export-training', 'download', 'secondary')}</div><p class="field-help">${h(t('privacy.training'))}</p>`);
    let cursor = plans.next_cursor;
    onAction('more-plans', async (el) => {
        el.disabled = true;
        try {
            const page = await api('/training/plans?cursor=' + encodeURIComponent(cursor));
            document.getElementById('training-plan-list').insertAdjacentHTML('beforeend', cards(page.items));
            cursor = page.next_cursor;
            if (!cursor)
                el.remove();
        }
        finally {
            el.disabled = false;
        }
    });
    onAction('export-training', async (el) => {
        el.disabled = true;
        try {
            const records = [];
            let cursor = null;
            do {
                const page = await api('/me/training-export' + (cursor ? '?cursor=' + encodeURIComponent(cursor) : ''));
                records.push(...page.plans);
                cursor = page.next_cursor;
            } while (cursor && records.length < 1000);
            if (cursor)
                throw new Error(t('error.export_too_large'));
            const blob = new Blob([JSON.stringify({ product: 'Adolat Olympic Club', exported_at: new Date().toISOString(), plans: records }, null, 2)], { type: 'application/json' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'adolat-my-training.json';
            a.click();
            setTimeout(() => URL.revokeObjectURL(url), 1000);
        }
        finally {
            el.disabled = false;
        }
    });
}
export async function cycleForm(id) {
    const existing = id ? await api('/training/cycles/' + id) : null;
    const circleId = existing?.circle_id ?? routeURL().searchParams.get('circle');
    const circle = circleId ? await api('/circles/' + circleId) : null;
    const clientId = existing?.id ?? crypto.randomUUID();
    const now = Math.floor(serverNow() / 60000) * 60000;
    const start = existing?.starts_at ?? now;
    const end = existing?.ends_at ?? now + 7 * 86400000;
    setView(titleBlock(t(circleId ? 'circle.schedule' : 'training.new'), circle ? plain(circle.name) : t('training.goal_help')) +
        `<form id="cycle-form" class="form-panel wide">${existing?.content_frozen ? `<div class="notice warning">${h(t('circle.frozen'))}</div>` : ''}` +
        shortBi('title', t('common.title'), existing?.title, true) + (!circleId && !id ? noteField(t('training.goal'), 'goal') : '') +
        (circleId ? shortBi('guidance', t('circle.guidance'), existing?.guidance) : '') +
        `<div class="form-grid">${field(t('activity.starts_at'), 'starts_at', dateInput(start), 'datetime-local', 'required')}${field(t('activity.ends_at'), 'ends_at', dateInput(end), 'datetime-local', 'required')}</div><p class="field-help">${h(state.settings.timezone)}</p>` +
        (circleId ? selectField(t('circle.mode'), 'mode', ['individual', 'collaborative'].map(v => ({ value: v, label: t('circle.' + v) })), existing?.mode ?? 'individual') +
            `<div class="form-grid">${field(t('circle.practice_start'), 'practice_starts_at', dateInput(existing?.practice_starts_at ?? now + 3600000), 'datetime-local', 'required')}${field(t('circle.practice_end'), 'practice_ends_at', dateInput(existing?.practice_ends_at ?? now + 7200000), 'datetime-local', 'required')}${field(t('circle.discussion_at'), 'discussion_opens_at', dateInput(existing?.discussion_opens_at ?? now + 7200000), 'datetime-local', 'required')}</div>` +
            textarea(t('circle.shared_links'), 'links', existing?.links.map(v => v.title + ' | ' + v.url).join('\n') ?? '', 4, 'maxlength="45000"') + `<p class="field-help">${h(t('circle.links_format'))}</p>` +
            selectField(t('common.status'), 'status', ['draft', 'published', ...(existing ? ['cancelled'] : [])].map(v => ({ value: v, label: t('training.status_' + v) })), existing?.status ?? 'published') + `<p class="notice">${h(t('circle.integrity'))}</p>` : '') +
        formActions(t(id ? 'action.save' : 'action.create'), circleId ? '/circles/' + circleId : '/training') + '</form>');
    bindForm('cycle-form', async (form) => {
        const links = formValue(form, 'links').split('\n').filter(v => v.trim()).map(line => { const split = line.indexOf('|'); if (split < 1)
            throw new Error(t('circle.links_format')); return { title: line.slice(0, split).trim(), url: line.slice(split + 1).trim() }; });
        const body = { client_id: clientId, circle_id: circleId, title: biValue(form, 'title'), guidance: circleId ? biValue(form, 'guidance') : {}, links,
            starts_at: parseDateInput(formValue(form, 'starts_at')), ends_at: parseDateInput(formValue(form, 'ends_at')),
            practice_starts_at: circleId ? parseDateInput(formValue(form, 'practice_starts_at')) : null, practice_ends_at: circleId ? parseDateInput(formValue(form, 'practice_ends_at')) : null,
            discussion_opens_at: circleId ? parseDateInput(formValue(form, 'discussion_opens_at')) : null,
            mode: circleId ? formValue(form, 'mode') : 'individual', status: circleId ? formValue(form, 'status') : 'published', ...(existing ? { version: existing.version } : {}) };
        const cycle = await api('/training/cycles' + (id ? '/' + id : ''), id ? 'PATCH' : 'POST', body);
        if (!circleId && !id)
            await api('/training/cycles/' + cycle.id + '/my-plan', 'PUT', { version: 0, goal: noteValue(form, 'goal'), review: {}, next_step: {} });
        await navigate('/training/cycles/' + cycle.id, true);
    });
}
export async function cyclePage(id) {
    const cycle = await api('/training/cycles/' + id);
    const plan = state.user?.role === 'student' ? await api('/training/cycles/' + id + '/my-plan') : null;
    if (!cycle.circle_id && plan) {
        await planPage(plan.id);
        return;
    }
    setView(titleBlock(plain(cycle.title), period(cycle), cycle.can_manage ? linkButton(t('action.edit'), '/training/cycles/' + id + '/edit', 'edit', 'secondary') : '') + trainingNav() +
        (cycle.circle_id ? `<div class="training-cycle-summary panel"><div class="panel-body"><span class="badge">${h(t('circle.' + cycle.mode))}</span><p>${content(cycle.guidance)}</p>${cycle.links.map(v => `<p>${outward(v.url, v.title)}</p>`).join('')}<p>${h(t('circle.practice_start'))}: ${h(date(cycle.practice_starts_at))}<br>${h(t('circle.practice_end'))}: ${h(date(cycle.practice_ends_at))}<br>${h(t('circle.discussion_at'))}: ${h(date(cycle.discussion_opens_at))}</p><p class="field-help">${h(t('circle.integrity'))}</p></div></div>` : '') +
        (state.user?.role === 'student' ? `<div class="section-header"><h2>${h(t('training.private'))}</h2>${plan ? linkButton(t('training.own_plan'), '/training/plans/' + plan.id, 'lock', 'primary') : button(t('training.create_plan'), 'make-plan', 'plus', 'primary')}</div>` : '') +
        (cycle.circle_id ? `<section id="debrief-panel"></section>` : ''));
    onAction('make-plan', async () => { const p = await api('/training/cycles/' + id + '/my-plan', 'PUT', { version: 0, goal: {}, review: {}, next_step: {} }); await navigate('/training/plans/' + p.id, true); });
    if (cycle.circle_id)
        await renderDebrief(cycle);
}
export async function planPage(id) {
    const plan = await api('/training/plans/' + id);
    const selected = plan.items.find(i => i.id === routeURL().searchParams.get('item')) ?? plan.items[0];
    const editable = !plan.read_only;
    const related = plan.context.circle_id ? linkButton(t('circle.discussion'), '/training/cycles/' + plan.cycle_id, 'group', 'secondary') : '';
    const choice = (key, values, current) => selectField(t('training.' + key), key, values.map(v => ({ value: v, label: t('training.' + v) })), current);
    setView(titleBlock(plain(plan.context.title), period(plan.context), related) + trainingNav() + privacy() +
        (plan.read_only ? `<div class="notice">${h(t('training.read_only'))}</div>` : '') +
        `<div class="training-workspace"><section class="stack"><form id="plan-goal" class="form-panel">${noteField(t('training.goal'), 'goal', plan.goal)}${noteField(t('training.review'), 'review', plan.review)}${noteField(t('training.next_step'), 'next_step', plan.next_step)}${editable ? formActions() : ''}</form>` +
        panel(t('training.queue'), plan.items.length ? plan.items.map(i => `<a class="training-item ${selected?.id === i.id ? 'selected' : ''}" href="#/training/plans/${h(id)}?item=${h(i.id)}"><span class="badge ${i.status === 'completed' ? 'phase-active' : ''}">${h(t('training.' + i.status))}</span><h3>${h(i.title)}</h3></a>`).join('') : `<p>${h(t('training.no_items'))}</p>`) +
        (editable ? `<details class="panel"><summary class="panel-heading">${icon('plus')}${h(t('training.add_link'))}</summary><form id="add-link" class="panel-body">${field(t('common.title'), 'title', '', 'text', 'required maxlength="200"')}${field(t('training.url'), 'url', '', 'url', 'required maxlength="2000" placeholder="https://"')}<p class="field-help">${h(t('training.link_help'))}</p>${formActions(t('action.add'))}</form></details>` : '') +
        '</section><section class="stack">' + (selected ? panel(selected.title, `<p>${outward(selected.url, t('training.open_problem'), 'button primary')}</p><p class="field-help">${h(t('training.self_report'))}</p>` +
        (editable ? `<form id="practice-entry">${choice('outcome', ['not_started', 'attempted', 'revisit', 'completed'], selected.status)}${choice('assistance', ['independent', 'hints', 'editorial', 'peer'], 'independent')}${noteField(t('training.reflection'), 'reflection')}${noteField(t('training.next_step'), 'next_step')}${formActions(t('training.record'))}</form>` : '') +
        `<details><summary>${h(t('training.carry'))}</summary><form id="carry-item"><div id="carry-options"></div>${formActions(t('training.carry'))}</form></details>` +
        (editable ? button(t('action.delete'), 'delete-item', 'trash', 'danger small') : '')) +
        panel(t('training.history'), plan.entries.filter(e => e.item_id === selected.id).map(e => `<article class="practice-note"><header><span class="badge">${h(t('training.' + e.outcome))}</span> <small>${h(t('training.' + e.assistance))} · ${h(date(e.created_at))}</small></header><p>${content(e.reflection)}</p><p>${content(e.next_step)}</p></article>`).join('') || `<p>${h(t('training.no_history'))}</p>`) : empty(t('training.queue'), t('training.no_items'))) + '</section></div>' +
        `<div class="section-header">${button(t('training.delete_plan'), 'delete-plan', 'trash', 'danger small')}</div>`);
    if (!editable)
        document.querySelectorAll('#plan-goal input,#plan-goal textarea').forEach(i => i.readOnly = true);
    let planVersion = plan.version;
    bindForm('plan-goal', async (form) => { if (!editable)
        return; const p = await api('/training/cycles/' + plan.cycle_id + '/my-plan', 'PUT', { version: planVersion, goal: noteValue(form, 'goal', plan.goal), review: noteValue(form, 'review', plan.review), next_step: noteValue(form, 'next_step', plan.next_step) }); planVersion = p.version; toast(t('training.saved')); });
    const itemMutationId = crypto.randomUUID();
    bindForm('add-link', async (form) => { const item = await api('/training/plans/' + id + '/items', 'POST', { client_id: itemMutationId, title: formValue(form, 'title'), url: formValue(form, 'url') }); await navigate('/training/plans/' + id + '?item=' + item.id, true); });
    if (selected) {
        const mutationId = crypto.randomUUID();
        bindForm('practice-entry', async (form) => { await api('/training/items/' + selected.id + '/entries', 'POST', { client_id: mutationId, item_version: selected.version, outcome: formValue(form, 'outcome'), assistance: formValue(form, 'assistance'), reflection: noteValue(form, 'reflection'), next_step: noteValue(form, 'next_step') }); toast(t('training.saved')); state.dirty = false; await refresh(); });
        const destinations = await api('/training/plans');
        document.getElementById('carry-options').innerHTML = selectField(t('training.carry_target'), 'plan_id', destinations.items.filter(p => p.id !== id && !p.read_only).map(p => ({ value: p.id, label: plain(p.context.title) }))) + linkButton(t('training.new'), '/training/new', 'plus', 'ghost small');
        const carryId = crypto.randomUUID();
        bindForm('carry-item', async (form) => { const dest = formValue(form, 'plan_id'); if (!dest)
            throw new Error(t('training.new')); await api('/training/plans/' + dest + '/items', 'POST', { client_id: carryId, title: selected.title, url: selected.url, carried_from_id: selected.id }); await navigate('/training/plans/' + dest, true); });
        onAction('delete-item', async () => { if (await confirmAction(t('action.delete') + '?')) {
            await api('/training/items/' + selected.id + '?version=' + selected.version, 'DELETE');
            state.dirty = false;
            await refresh();
        } });
    }
    onAction('delete-plan', async () => { if (await confirmAction(t('training.delete_confirm'))) {
        await api('/training/plans/' + id, 'DELETE');
        await navigate('/training', true);
    } });
}
export async function circlesPage() {
    const data = await api('/circles');
    const cards = (items) => items.map(c => `<article class="training-card panel"><div class="section-header"><span class="badge">${h(c.locked ? t('circle.locked') : c.archived ? t('circle.archived') : t('count.students', { count: c.member_count }))}</span></div><h2>${content(c.name)}</h2><p>${content(c.description)}</p>${c.my_status === 'active' || state.user?.role === 'admin' ? linkButton(t('action.open'), '/circles/' + c.id, 'arrow', 'secondary') : c.my_status === 'pending' ? `<span class="badge">${h(t('circle.pending'))}</span>` : !c.archived && !c.locked ? button(t('circle.join'), 'join-circle', 'plus', 'secondary', `data-id="${h(c.id)}"`) : ''}</article>`).join('');
    setView(titleBlock(t('nav.circles'), t('circle.subtitle'), state.user?.role === 'student' ? linkButton(t('circle.new'), '/circles/new', 'plus') : '') + trainingNav() + `<p class="field-help">${h(t('circle.limit_note'))}</p><div id="circles-list" class="training-grid">${cards(data.items)}</div>` + (!data.items.length ? empty(t('circle.empty'), t('circle.limit_note')) : '') + (data.next_cursor ? button(t('training.more'), 'more-circles') : ''));
    const bindJoin = () => onAction('join-circle', async (el) => { await api('/circles/' + el.dataset.id + '/join', 'POST', {}); toast(t('circle.pending')); await refresh(); });
    bindJoin();
    let cursor = data.next_cursor;
    onAction('more-circles', async (el) => { const page = await api('/circles?cursor=' + encodeURIComponent(cursor)); document.getElementById('circles-list').insertAdjacentHTML('beforeend', cards(page.items)); cursor = page.next_cursor; if (!cursor)
        el.remove(); bindJoin(); });
}
export async function circleForm(id) {
    const c = id ? await api('/circles/' + id) : null;
    const mutation = crypto.randomUUID();
    setView(titleBlock(t(c ? 'action.edit' : 'circle.new'), t('circle.limit_note')) + `<form id="circle-form" class="form-panel wide">${shortBi('name', t('circle.name'), c?.name, true)}${shortBi('description', t('circle.purpose'), c?.description)}${checkbox(t('circle.discoverable'), 'discoverable', c?.discoverable ?? true)}${c ? checkbox(t('circle.archive'), 'archived', c.archived) : ''}${formActions(t(c ? 'action.save' : 'action.create'), '/circles')}</form>`);
    bindForm('circle-form', async (form) => { const result = await api('/circles' + (id ? '/' + id : ''), id ? 'PATCH' : 'POST', { name: biValue(form, 'name'), description: biValue(form, 'description'), discoverable: formChecked(form, 'discoverable'), ...(c ? { version: c.version, archived: formChecked(form, 'archived') } : { client_id: mutation }) }); await navigate('/circles/' + result.id, true); });
}
export async function circlePage(id) {
    const circle = await api('/circles/' + id);
    const cycles = circle.locked ? { items: [], next_cursor: null } : await api('/training/cycles?circle_id=' + id);
    const me = circle.members.find(m => m.id === state.user.id);
    const cycleRows = (items) => items.map(c => `<a class="list-row" href="#/training/cycles/${h(c.id)}"><div class="row-content"><strong>${content(c.title)}</strong><small>${h(period(c))} · ${h(t('circle.' + c.mode))}</small></div><span class="badge">${h(t('training.status_' + c.status))}</span></a>`).join('');
    setView(titleBlock(plain(circle.name), plain(circle.description), circle.can_manage && !circle.archived && !circle.locked ? linkButton(t('circle.schedule'), '/training/cycles/new?circle=' + id, 'plus') + linkButton(t('action.edit'), '/circles/' + id + '/edit', 'edit', 'secondary') : '') + trainingNav() +
        (circle.locked ? `<div class="notice warning">${h(t('circle.locked'))}</div>` : '') +
        `<div class="two-col"><section class="stack">${panel(t('circle.cycles'), `<div id="circle-cycles">${cycleRows(cycles.items) || empty(t('activity.empty'), '')}</div>` + (cycles.next_cursor ? button(t('training.more'), 'more-cycles') : ''))}${!circle.archived && !circle.locked ? `<div class="section-header">${button(t('circle.report'), 'report-circle', 'help', 'secondary')}</div>` : ''}</section>` +
        panel(t('circle.members'), circle.members.map(m => `<div class="circle-member"><div><strong>${h(m.display_name)}</strong><small>${h(m.status === 'pending' ? t('circle.pending') : t('circle.' + m.role))}</small></div><div class="compact-actions">${circle.can_manage && !circle.archived && !circle.locked ? (m.status === 'pending' ? button(t('circle.approve'), 'member-approve', 'check', 'secondary small', `data-id="${h(m.id)}"`) : '') + (m.id !== state.user.id ? button(t('circle.remove'), 'member-remove', 'close', 'ghost small', `data-id="${h(m.id)}"`) : '') + (m.transfer_consent && m.id !== state.user.id ? button(t('circle.transfer'), 'member-transfer', 'user', 'secondary small', `data-id="${h(m.id)}"`) : '') : ''}</div></div>`).join('') + `<p class="field-help">${h(t('circle.transfer_note'))}</p>` + (me && !circle.archived ? button(t(me.transfer_consent ? 'circle.decline_transfer' : 'circle.consent_transfer'), 'consent-transfer', 'check', 'secondary small') + button(t('circle.leave'), 'leave-circle', 'logout', 'ghost small') : '')) + '</div><div id="report-form-area"></div>');
    for (const action of ['approve', 'remove', 'transfer'])
        onAction('member-' + action, async (el) => { if (action !== 'approve' && !await confirmAction(t('circle.' + action) + '?'))
            return; await api('/circles/' + id + '/members', 'POST', { action, user_id: el.dataset.id }); await refresh(); });
    onAction('consent-transfer', async () => { await api('/circles/' + id + '/members', 'POST', { action: me?.transfer_consent ? 'decline_transfer' : 'consent_transfer', user_id: state.user.id }); await refresh(); });
    onAction('leave-circle', async () => { if (await confirmAction(t('circle.leave_confirm'))) {
        await api('/circles/' + id + '/members', 'POST', { action: 'remove', user_id: state.user.id });
        await navigate('/circles', true);
    } });
    onAction('report-circle', () => reportForm(id));
    let cursor = cycles.next_cursor;
    onAction('more-cycles', async (el) => { const page = await api('/training/cycles?circle_id=' + id + '&cursor=' + encodeURIComponent(cursor)); document.getElementById('circle-cycles').insertAdjacentHTML('beforeend', cycleRows(page.items)); cursor = page.next_cursor; if (!cursor)
        el.remove(); });
}
function reportForm(circleId, postId) {
    const target = document.getElementById('report-form-area');
    if (!target)
        return;
    target.innerHTML = `<form id="report-form" class="form-panel"><h2>${h(t('circle.report'))}</h2>${selectField(t('moderation.reason'), 'reason', ['unsafe', 'spoiler', 'harassment', 'facilitator', 'other'].map(v => ({ value: v, label: t('moderation.' + v) })))}${textarea(t('moderation.detail'), 'detail', '', 3, 'maxlength="1000"')}${formActions(t('action.send'))}</form>`;
    bindForm('report-form', async (form) => { await api('/reports', 'POST', { circle_id: circleId, post_id: postId ?? null, reason: formValue(form, 'reason'), detail: formValue(form, 'detail') }); toast(t('moderation.sent')); target.innerHTML = ''; });
    target.querySelector('select')?.focus();
}
async function renderDebrief(cycle) {
    const node = document.getElementById('debrief-panel');
    if (!cycle.discussion_open) {
        node.innerHTML = `<div class="notice warning">${icon('lock')}<p>${h(t('circle.gate', { time: date(cycle.discussion_opens_at) }))}</p></div>${button(t('action.refresh'), 'check-gate', 'clock', 'secondary')}`;
        onAction('check-gate', () => refresh());
        return;
    }
    const page = await api('/training/cycles/' + cycle.id + '/posts');
    const postRows = (rows) => rows.map(p => `<article class="peer-post"><header><strong>${h(p.author_name)}</strong><span class="badge">${h(t('circle.' + p.kind))}</span><small>${h(date(p.created_at))}</small></header><div class="prose">${content(p.body)}</div><div class="compact-actions">${button(t('circle.report'), 'report-post', 'help', 'ghost small', `data-id="${h(p.id)}"`)}${cycle.can_manage ? button(t('circle.hide'), 'hide-post', 'lock', 'ghost small', `data-id="${h(p.id)}"`) : ''}</div></article>`).join('');
    node.innerHTML = panel(t('circle.discussion'), `<p class="field-help">${h(t('circle.no_posts'))}</p>${page.next_cursor ? button(t('training.older'), 'older-posts') : ''}<div id="peer-posts">${postRows(page.items)}</div>`) + `<form id="peer-form" class="form-panel wide">${selectField(t('circle.post_kind'), 'kind', ['help', 'explanation', 'logistics'].map(v => ({ value: v, label: t('circle.' + v) })))}${noteField(t('circle.post'), 'body')}${formActions(t('action.send'))}</form><div id="report-form-area"></div>`;
    const bindPosts = () => {
        onAction('report-post', el => reportForm(cycle.circle_id, el.dataset.id));
        onAction('hide-post', el => {
            document.getElementById('report-form-area').innerHTML = `<form id="hide-form" class="form-panel">${textarea(t('moderation.reason'), 'reason', '', 3, 'required minlength="3" maxlength="1000"')}${formActions(t('circle.hide'))}</form>`;
            bindForm('hide-form', async (form) => { await api('/training/posts/' + el.dataset.id + '/hide', 'POST', { reason: formValue(form, 'reason') }); state.dirty = false; await refresh(); });
        });
    };
    bindPosts();
    const mutation = crypto.randomUUID();
    bindForm('peer-form', async (form) => { await api('/training/cycles/' + cycle.id + '/posts', 'POST', { client_id: mutation, kind: formValue(form, 'kind'), body: noteValue(form, 'body') }); state.dirty = false; await refresh(); });
    let cursor = page.next_cursor;
    onAction('older-posts', async (el) => { const older = await api('/training/cycles/' + cycle.id + '/posts?cursor=' + encodeURIComponent(cursor)); document.getElementById('peer-posts').insertAdjacentHTML('afterbegin', postRows(older.items)); cursor = older.next_cursor; if (!cursor)
        el.remove(); bindPosts(); });
}
export async function moderationPage() {
    const data = await api('/admin/reports');
    setView(titleBlock(t('nav.moderation'), t('privacy.training')) + (data.items.length ? data.items.map(r => `<section class="panel moderation-card"><div class="panel-body"><h2>${h(t('moderation.' + r.reason))}</h2><small>${h(date(r.created_at))}</small><p>${h(r.detail)}</p>${r.reported_post ? `<blockquote>${content(r.reported_post.body)}</blockquote>` : ''}<form id="resolve-${h(r.id)}">${textarea(t('moderation.resolution'), 'reason', '', 3, 'required minlength="3" maxlength="1000"')}${checkbox(t('moderation.hide_post'), 'hide_post')}${checkbox(t('moderation.lock_circle'), 'lock_circle')}${formActions(t('moderation.resolve'))}</form></div></section>`).join('') : empty(t('moderation.empty'), '')));
    for (const r of data.items)
        bindForm('resolve-' + r.id, async (form) => { await api('/admin/reports/' + r.id + '/resolve', 'POST', { reason: formValue(form, 'reason'), hide_post: formChecked(form, 'hide_post'), lock_circle: formChecked(form, 'lock_circle') }); state.dirty = false; await refresh(); });
}
export async function subjectParticipationPage() {
    const users = await api('/admin/users');
    setView(titleBlock(t('nav.subjects'), t('subject.manage_note')) + `<form id="participation-form" class="form-panel">${selectField(t('auth.name'), 'user_id', users.filter(u => u.role === 'student').map(u => ({ value: u.id, label: u.display_name + ' · ' + u.email })))}${selectField(t('common.subject'), 'subject_id', state.subjects.map(s => ({ value: s.id, label: plain(s.name) })), 'informatics')}${selectField(t('common.status'), 'active', [{ value: 'true', label: t('subject.enable') }, { value: 'false', label: t('subject.disable') }])}${formActions()}</form>`);
    bindForm('participation-form', async (form) => { await api('/admin/subjects/' + formValue(form, 'subject_id') + '/members/' + formValue(form, 'user_id'), 'PUT', { active: formValue(form, 'active') === 'true' }); toast(t('app.saved')); });
}
//# sourceMappingURL=pages-training.js.map