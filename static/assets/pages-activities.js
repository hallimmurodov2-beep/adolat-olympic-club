import { api } from './api.js';
import { date, dateInput, parseDateInput, plain, t, number } from './i18n.js';
import { isStaff, serverNow, state } from './state.js';
import { navigate, refresh, routeURL, setCleanup, setRemoteHandler, setView } from './router.js';
import { activityRow, biValue, bilingual, bindForm, button, checkbox, confirmAction, content, empty, enhance, field, formActions, formValue, h, icon, linkButton, onAction, panel, problemReading, selectField, showError, statusBadge, submissionRow, textarea, titleBlock, toast } from './ui.js';
import { editorHTML, WorkEditor } from './work-editor.js';
export async function activitiesPage(kind) {
    const classroom = routeURL().searchParams.get('classroom');
    const data = await api(`/activities?kind=${kind}${classroom ? '&classroom_id=' + encodeURIComponent(classroom) : ''}`);
    setView(titleBlock(t(kind === 'assignment' ? 'nav.assignments' : kind === 'session' ? 'nav.sessions' : 'nav.competitions'), t('activity.description_' + kind), isStaff() ? linkButton(t('activity.create_' + kind), `/activities/new?kind=${kind}${classroom ? '&classroom=' + classroom : ''}`, 'plus') : '') + panel(t('common.all'), data.length ? data.map(activityRow).join('') : empty(t('activity.empty'), t('activity.empty_note'))));
}
export async function activityForm() {
    const query = routeURL().searchParams;
    const raw = query.get('kind');
    const kind = raw === 'session' || raw === 'competition' ? raw : 'assignment';
    const rooms = await api('/classrooms');
    const selected = rooms.find(c => c.id === query.get('classroom')) ?? rooms.find(c => c.active);
    if (!selected) {
        setView(empty(t('classroom.empty'), t('classroom.empty_note'), linkButton(t('classroom.create'), '/classrooms/new', 'plus')));
        return;
    }
    const [room, problems, sets] = await Promise.all([api('/classrooms/' + selected.id), api('/problems?limit=100&classroom_id=' + selected.id), api('/sets?classroom_id=' + selected.id)]);
    const preset = sets.find(s => s.id === query.get('set'));
    setView(titleBlock(t('activity.create_' + kind), plain(room.name)) + `<form id="activity-form" class="form-panel wide"><div class="notice">${icon('lock')}<p>${h(t('activity.immutable'))}</p></div>${selectField(t('common.classroom'), 'classroom_id', rooms.filter(c => c.active).map(c => ({ value: c.id, label: plain(c.name) })), room.id)}${bilingual('title', t('common.title'), preset?.title, true)}${bilingual('description', t('common.description'), preset?.description, false, 3)}<div class="form-grid">${field(t('activity.starts_at'), 'starts_at', dateInput(kind === 'competition' ? serverNow() + 86400000 : null), 'datetime-local', kind === 'competition' ? 'required' : '')}${kind === 'session' ? field(t('activity.duration'), 'duration_minutes', '60', 'number', 'required min="1" max="600"') : field(t('activity.ends_at'), 'ends_at', dateInput(serverNow() + 7 * 86400000), 'datetime-local', kind === 'competition' ? 'required' : '')}</div><p class="field-help">${h(state.settings.timezone)}</p><fieldset class="fieldset"><legend>${h(t('activity.select_problems'))}</legend>${!problems.items.length ? `<p>${h(t('activity.no_problems'))}</p>${linkButton(t('problem.create'), '/problems/new?classroom=' + room.id, 'plus')}` : problems.items.map((p, i) => `<div class="task-choice">${checkbox(plain(p.title), 'problem', preset?.problem_ids.includes(p.id) ?? false, p.id)}${field(t('common.points'), 'points_' + p.id, '7', 'number', 'min="0.1" max="1000" step="0.1"')}<details><summary>${h(t('activity.rubric'))}</summary>${textarea(t('activity.rubric_help'), 'rubric_' + p.id, '', 2)}</details></div>`).join('')}</fieldset>${kind === 'competition' ? `<fieldset class="fieldset"><legend>${h(t('activity.eligibility'))}</legend><p class="field-help">${h(t('activity.selected_members'))}</p>${room.members.filter(m => m.active !== false).map(m => checkbox(m.display_name, 'eligible', true, m.id)).join('')}</fieldset>` : ''}${formActions(t('action.create'), '/' + (kind === 'assignment' ? 'assignments' : kind === 'session' ? 'sessions' : 'competitions'))}</form>`);
    document.querySelector('[name=classroom_id]')?.addEventListener('change', event => { void navigate(`/activities/new?kind=${kind}&classroom=${event.target.value}`, true); });
    bindForm('activity-form', async (form) => {
        const selectedIds = new FormData(form).getAll('problem').map(String);
        if (!selectedIds.length)
            throw new Error(t('error.required'));
        const items = selectedIds.map(id => {
            const rubric = formValue(form, 'rubric_' + id).split('\n').filter(line => line.trim()).map(line => {
                const parts = line.split('|').map(v => v.trim());
                if (parts.length !== 3 || !Number.isFinite(Number(parts[2])))
                    throw new Error(t('error.invalid_input'));
                return { name: { ...(parts[0] ? { ru: parts[0] } : {}), ...(parts[1] ? { en: parts[1] } : {}) }, max: Number(parts[2]) };
            });
            return { problem_id: id, points: Number(formValue(form, 'points_' + id)), rubric };
        });
        const result = await api('/activities', 'POST', { classroom_id: room.id, kind, title: biValue(form, 'title'), description: biValue(form, 'description'), starts_at: parseDateInput(formValue(form, 'starts_at')), ends_at: kind === 'session' ? null : parseDateInput(formValue(form, 'ends_at')), duration_minutes: kind === 'session' ? Number(formValue(form, 'duration_minutes')) : 60, items, eligible_ids: kind === 'competition' ? new FormData(form).getAll('eligible').map(String) : null });
        toast(t('app.saved'));
        await navigate('/activities/' + result.id, true);
    });
}
function countdown(a) {
    if (a.phase === 'draft' || a.phase === 'ended')
        return t('phase.' + a.phase);
    const target = a.phase === 'upcoming' ? a.starts_at : a.ends_at;
    if (!target)
        return t('common.no_deadline');
    const seconds = Math.max(0, Math.floor((target - serverNow()) / 1000));
    return [Math.floor(seconds / 3600), Math.floor(seconds / 60) % 60, seconds % 60].map(v => String(v).padStart(2, '0')).join(':');
}
function taskNav(a, selected) { return a.items.map((item, i) => `<a class="task-link ${item.id === selected ? 'active' : ''}" href="#/activities/${a.id}?item=${item.id}" ${item.id === selected ? 'aria-current="page"' : ''}><span>${h(t('activity.problem_number', { number: i + 1 }))}</span><strong>${content(item.problem.title)}</strong><small>${h(number(item.points))} ${h(t('common.points'))}${a.kind === 'session' && isStaff() ? ' · ' + h(t(item.released_at ? 'activity.released' : 'phase.draft')) : ''}</small></a>`).join(''); }
function teacherControls(a) {
    if (!isStaff())
        return '';
    return `<div class="control-bar">${a.phase === 'draft' ? button(t(a.kind === 'session' ? 'activity.start' : a.kind === 'competition' ? 'activity.publish_competition' : 'activity.publish'), a.kind === 'session' ? 'start' : 'publish', 'live', 'primary') : ''}${a.phase === 'active' || a.phase === 'upcoming' ? button(t('activity.end'), 'end', 'clock') : ''}${a.phase === 'ended' && !a.results_published ? button(t('activity.publish_results'), 'publish_results', 'check', 'primary') : ''}${a.phase === 'draft' ? button(t('action.delete'), 'delete', 'trash', 'danger') : ''}${a.kind === 'session' ? linkButton(t('activity.presentation'), '/present/' + a.id, 'expand', 'secondary') : ''}</div>`;
}
function releaseControls(a, item) {
    if (!isStaff())
        return '';
    const allowed = a.kind !== 'competition' || a.phase === 'ended' && a.results_published;
    return `<div class="control-bar">${a.kind === 'session' && !item.released_at && a.phase === 'active' ? button(t('activity.release_problem'), 'release-problem', 'live', 'primary') : ''}${allowed && (a.kind !== 'session' || item.released_at) ? button(t(item.hints_released ? 'activity.hide_hint' : 'activity.release_hint'), 'release-hints', 'help') + button(t(item.solution_released ? 'activity.hide_solution' : 'activity.release_solution'), 'release-solution', 'eye') : ''}</div>`;
}
export async function activityPage(id) {
    let activity = await api('/activities/' + id);
    let selected = activity.items.find(i => i.id === routeURL().searchParams.get('item')) ?? activity.items[0];
    let editor = null;
    let updating = false;
    const work = selected && !isStaff() ? await api('/drafts/' + selected.id) : null;
    const options = selected && work ? { id: 'solution-editor', itemId: selected.id, work, files: work.files ?? [], format: selected.problem.format, canEdit: activity.phase === 'active', canSubmit: activity.phase === 'active', onSubmitted: () => update() } : null;
    setView(`<div id="activity-heading"></div><div id="activity-controls"></div><div id="activity-preflight"></div><div id="activity-message"></div><div class="activity-layout"><aside><div class="countdown-card"><span>${h(t('activity.countdown'))}</span><strong id="countdown" role="timer">${h(countdown(activity))}</strong><small id="deadline-label">${h(date(activity.ends_at ?? activity.starts_at))}</small><small>${h(t('activity.server_deadline'))}</small></div><nav id="task-nav" aria-label="${h(t('activity.tasks'))}"></nav><div id="session-help"></div></aside><div class="activity-main"><div id="task-reading"></div>${options ? editorHTML(options) : ''}<div id="activity-monitor"></div><div id="session-announcement"></div></div></div>`);
    if (options)
        editor = new WorkEditor(options);
    const bindControls = () => {
        onAction('clone-activity', async () => {
            if (!await confirmAction(t('activity.clone_confirm')))
                return;
            const copy = await api('/activities/' + id + '/clone', 'POST', {});
            await navigate('/activities/' + copy.id + '/edit', true);
        });
        if (isStaff() && (activity.kind === 'competition' || activity.kind === 'session')) {
            onAction('preflight-check', async (el) => {
                el.disabled = true;
                try {
                    const data = await api('/activities/' + id + '/preflight');
                    const node = document.getElementById('preflight-results');
                    if (node)
                        node.innerHTML = `<p>${h(t('activity.preflight_items'))}: <strong>${data.item_count}</strong> · ${h(t('activity.preflight_participants'))}: <strong>${data.eligible_participant_count}</strong> · ${h(t('activity.preflight_submissions'))}: <strong>${data.recorded_submission_count}</strong></p><ul>${Object.entries(data.checks).map(([k, v]) => `<li>${h(k.replaceAll('_', ' '))}: ${v ? '✓' : '⚠'}</li>`).join('')}</ul>`;
                }
                finally {
                    el.disabled = false;
                }
            });
        }
        if (state.user?.role === 'admin' && activity.ends_at && (activity.kind === 'competition' || activity.kind === 'session') && activity.phase === 'active') {
            bindForm('interruption-extension', async (form) => {
                const expectedEndsAt = activity.ends_at;
                if (!expectedEndsAt)
                    return;
                const minutes = Number(formValue(form, 'minutes'));
                if (!Number.isInteger(minutes) || minutes < 1 || minutes > 120)
                    throw new Error(t('error.invalid_input'));
                if (!await confirmAction(t('activity.extend_note')))
                    return;
                await api('/activities/' + id + '/interruption-extension', 'POST', {
                    expected_ends_at: expectedEndsAt, new_ends_at: expectedEndsAt + minutes * 60000,
                    reason: formValue(form, 'reason')
                });
                state.dirty = false;
                toast(t('app.saved'));
                await update();
            });
        }
        ['start', 'publish', 'end', 'publish_results'].forEach(action => onAction(action, async () => {
            if ((action === 'end' || action === 'publish_results') && !await confirmAction(t(action === 'end' ? 'activity.end_confirm' : 'activity.publish_results_confirm')))
                return;
            await api('/activities/' + id + '/control', 'POST', { action });
            await update();
        }));
        onAction('delete', async () => {
            if (!await confirmAction(t('activity.delete_confirm')))
                return;
            await api('/activities/' + id, 'DELETE');
            await navigate('/' + (activity.kind === 'session' ? 'sessions' : activity.kind === 'competition' ? 'competitions' : 'assignments'), true);
        });
        ['problem', 'hints', 'solution'].forEach(action => onAction('release-' + action, async () => {
            if (!selected)
                return;
            const enabled = action === 'problem' ? true : !(action === 'hints' ? selected.hints_released : selected.solution_released);
            if (action === 'solution' && enabled && !await confirmAction(t('activity.reveal_confirm')))
                return;
            await api(`/activities/${id}/items/${selected.id}/release`, 'POST', { action, enabled });
            await update();
        }));
    };
    const patch = async () => {
        document.getElementById('activity-heading').innerHTML = titleBlock(plain(activity.title), plain(activity.description), statusBadge(activity.phase) + (isStaff() ? button(t('activity.clone'), 'clone-activity', 'copy', 'secondary') + (activity.status === 'draft' ? linkButton(t('activity.edit_draft'), '/activities/' + id + '/edit', 'edit', 'secondary') : '') : ''), plain(activity.classroom_name));
        document.getElementById('activity-controls').innerHTML = teacherControls(activity);
        const preflight = document.getElementById('activity-preflight');
        const preflightStamp = [activity.kind, activity.phase, activity.ends_at ?? '', state.user?.role ?? ''].join('|');
        if (preflight.dataset.stamp !== preflightStamp) {
            preflight.innerHTML = isStaff() && (activity.kind === 'competition' || activity.kind === 'session') ?
                `<details class="panel"><summary class="panel-body">${h(t('activity.preflight'))}</summary><div class="panel-body stack"><p>${h(t('activity.preflight_note'))}</p>${button(t('activity.preflight'), 'preflight-check', 'check', 'secondary')}<div id="preflight-results" aria-live="polite"></div>` +
                    (state.user?.role === 'admin' && activity.ends_at && activity.phase === 'active' ?
                        `<form id="interruption-extension" class="form-panel"><h3>${h(t('activity.extend_window'))}</h3><p>${h(t('activity.extend_note'))}</p>${field(t('activity.extend_minutes'), 'minutes', '15', 'number', 'required min="1" max="120"')}${textarea(t('activity.extend_reason'), 'reason', '', 2, 'required minlength="20" maxlength="500"')}${formActions(t('action.confirm'))}</form>` : '') + '</div></details>' : '';
            preflight.dataset.stamp = preflightStamp;
        }
        document.getElementById('activity-message').innerHTML = (activity.kind === 'competition' ? `<div class="notice warning">${icon('lock')}<p>${h(t('activity.competition_rules'))}</p></div>` : '') + (plain(activity.announcement) ? `<div class="notice"><div><strong>${h(t('activity.teacher_message'))}</strong>${content(activity.announcement, true)}</div></div>` : '') + (activity.phase === 'ended' ? `<div class="notice"><p>${h(t('activity.closed'))} ${h(t(activity.results_published ? 'activity.results_published' : 'activity.results_private'))}</p></div>` : '');
        document.getElementById('task-nav').innerHTML = taskNav(activity, selected?.id ?? '');
        document.getElementById('task-reading').innerHTML = selected ? releaseControls(activity, selected) + problemReading(selected.problem, selected.files) : empty(t(activity.phase === 'upcoming' ? 'activity.before_start' : 'activity.waiting_problems'), '', '', 'clock');
        document.getElementById('deadline-label').textContent = date(activity.ends_at ?? activity.starts_at);
        document.getElementById('activity-monitor').innerHTML = panel(t(isStaff() ? 'activity.monitor' : 'work.history'), activity.submissions.length ? activity.submissions.map(s => submissionRow(s, isStaff())).join('') : `<p class="panel-empty">${h(t('activity.no_submissions'))}</p>`);
        const help = document.getElementById('session-help');
        if (activity.kind === 'session' && isStaff()) {
            help.innerHTML = panel(t('activity.help_requests'), activity.help_requests.filter(r => !r.resolved).map(r => `<div class="help-request"><strong>${h(r.author_name)}</strong><p>${h(r.body)}</p>${button(t('activity.resolve'), 'resolve-help', 'check', 'secondary small', `data-id="${r.id}"`)}</div>`).join('') || `<p class="panel-empty">${h(t('common.none'))}</p>`);
            onAction('resolve-help', async (el) => { await api('/help/' + el.dataset.id + '/resolve', 'POST', {}); await update(); });
        }
        else if (activity.kind === 'session' && activity.phase === 'active' && !help.querySelector('form')) {
            help.innerHTML = `<form id="help-form" class="form-panel">${textarea(t('activity.help'), 'body', '', 3, 'required maxlength="1000"')}${formActions(t('action.send'))}</form>`;
            bindForm('help-form', async (form) => { await api('/activities/' + id + '/help', 'POST', { body: formValue(form, 'body') }); toast(t('activity.help_sent')); form.reset(); });
        }
        if (activity.kind === 'session' && isStaff() && !document.getElementById('announce-form')) {
            document.getElementById('session-announcement').innerHTML = `<form id="announce-form" class="form-panel wide">${bilingual('body', t('activity.announce'), {}, true, 2)}${formActions(t('action.send'))}</form>`;
            bindForm('announce-form', async (form) => { await api('/activities/' + id + '/control', 'POST', { action: 'announce', body: biValue(form, 'body') }); form.reset(); await update(); });
        }
        if (activity.phase !== 'active' && editor)
            editor.close();
        bindControls();
        await enhance(document.getElementById('task-reading'));
    };
    async function update() {
        if (updating)
            return;
        updating = true;
        try {
            const next = await api('/activities/' + id);
            const previous = activity.phase;
            activity = next;
            if (!selected && activity.items.length || !isStaff() && previous === 'upcoming' && activity.phase === 'active') {
                await refresh();
                return;
            }
            selected = activity.items.find(item => item.id === selected?.id);
            await patch();
            if (selected && editor) {
                const incoming = await api('/drafts/' + selected.id);
                editor.receive(incoming);
            }
        }
        finally {
            updating = false;
        }
    }
    await patch();
    setRemoteHandler(() => update());
    let nextPhaseCheck = 0;
    const timer = setInterval(() => {
        const node = document.getElementById('countdown');
        if (node)
            node.textContent = countdown(activity);
        const due = activity.phase === 'upcoming' ? activity.starts_at : activity.phase === 'active' ? activity.ends_at : null;
        if (due && serverNow() >= due && Date.now() > nextPhaseCheck) {
            nextPhaseCheck = Date.now() + 5000;
            if (activity.phase === 'active')
                editor?.close();
            void update().catch(showError);
        }
    }, 1000);
    setCleanup(() => { clearInterval(timer); editor?.dispose(); });
}
export async function presentationPage(id) {
    let a = await api('/activities/' + id);
    if (!isStaff())
        throw new Error(t('error.forbidden'));
    let selected = routeURL().searchParams.get('item') ?? a.items.find(i => i.released_at)?.id ?? a.items[0]?.id;
    const render = async () => {
        const item = a.items.find(i => i.id === selected);
        setView(`<div class="presentation"><header><div class="brand"><img class="school-logo" src="/static/brand/logo-header.png" srcset="/static/brand/logo-header-2x.png 2x" alt="" width="64" height="52"><span>Adolat Olympic Club</span></div><div class="heading-actions">${button(t('action.fullscreen'), 'fullscreen', 'expand')}${linkButton(t('action.back'), '/activities/' + id, 'back', 'secondary')}</div></header><p class="eyebrow">${content(a.title)} · <span id="presentation-clock">${h(countdown(a))}</span></p><nav class="tabs">${a.items.map((i, n) => `<button class="tab ${i.id === selected ? 'active' : ''}" data-present-item="${i.id}">${h(t('activity.problem_number', { number: n + 1 }))}</button>`).join('')}</nav>${item ? problemReading({ ...item.problem, hints: {}, solution: {} }, item.files) : empty(t('activity.waiting_problems'), '')}</div>`);
        document.querySelectorAll('[data-present-item]').forEach(el => el.addEventListener('click', () => { selected = el.dataset.presentItem; void render(); }));
        onAction('fullscreen', async () => {
            if (document.fullscreenElement)
                await document.exitFullscreen();
            else
                await document.getElementById('main').requestFullscreen();
        });
        await enhance();
    };
    await render();
    setRemoteHandler(async () => { a = await api('/activities/' + id); await render(); });
    const timer = setInterval(() => {
        const node = document.getElementById('presentation-clock');
        if (node)
            node.textContent = countdown(a);
    }, 1000);
    setCleanup(() => clearInterval(timer));
}
/** Safe metadata editor: snapshots/eligibility remain frozen; CAS prevents stale draft writes. */
export async function activityDraftForm(id) {
    const a = await api('/activities/' + id);
    if (a.status !== 'draft') {
        setView(empty(t('activity.immutable'), '', linkButton(t('action.back'), '/activities/' + id, 'back')));
        return;
    }
    setView(titleBlock(t('activity.edit_draft'), plain(a.classroom_name)) + `<form id="draft-edit" class="form-panel wide">
        <div class="notice">${icon('lock')} ${h(t('activity.draft_restriction'))}</div>
        ${bilingual('title', t('common.title'), a.title, true)}${bilingual('description', t('common.description'), a.description, false, 3)}
        <div class="form-grid">${field(t('activity.starts_at'), 'starts_at', dateInput(a.starts_at), 'datetime-local')}
        ${field(t('activity.ends_at'), 'ends_at', dateInput(a.ends_at), 'datetime-local')}
        ${a.kind === 'session' ? field(t('activity.duration'), 'duration_minutes', String(a.duration_minutes), 'number', 'required min="1" max="600"') : ''}</div>
        ${formActions(t('action.save'), '/activities/' + id)}</form>`);
    bindForm('draft-edit', async (form) => {
        await api('/activities/' + id + '/draft', 'PATCH', { edit_version: a.edit_version,
            title: biValue(form, 'title'), description: biValue(form, 'description'),
            starts_at: parseDateInput(formValue(form, 'starts_at')), ends_at: parseDateInput(formValue(form, 'ends_at')),
            duration_minutes: a.kind === 'session' ? Number(formValue(form, 'duration_minutes')) : a.duration_minutes });
        state.dirty = false;
        toast(t('app.saved'));
        await navigate('/activities/' + id, true);
    });
}
//# sourceMappingURL=pages-activities.js.map