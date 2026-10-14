import { api } from './api.js';
import { date, plain, t } from './i18n.js';
import { isStaff, state } from './state.js';
import { navigate, refresh, routeURL, setView } from './router.js';
import { activityRow, attachmentList, biValue, bilingual, bindForm, bindUploads, button, checkbox, confirmAction, content, empty, field, formActions, formChecked, formValue, h, icon, linkButton, onAction, panel, selectField, subjectBadge, titleBlock, toast, uploadControl } from './ui.js';
function roomCard(c) { return `<a class="classroom-card ${h(c.subject_id)}" href="#/classrooms/${h(c.id)}"><div class="toolbar">${subjectBadge(c.subject_id)}${!c.active ? `<span class="badge">${h(t('classroom.archived'))}</span>` : ''}</div><h2>${content(c.name)}</h2><p>${content(c.description)}</p><footer><span>${h(c.teacher_name)}</span><span>${h(t('count.students', { count: c.member_count }))}</span>${icon('arrow')}</footer></a>`; }
export async function classroomsPage() {
    const classrooms = await api('/classrooms');
    const subject = routeURL().searchParams.get('subject');
    const visible = subject ? classrooms.filter(c => c.subject_id === subject) : classrooms;
    setView(titleBlock(t('nav.classrooms'), t('classroom.description'), isStaff() ? linkButton(t('classroom.create'), '/classrooms/new', 'plus') : '') + `<nav class="tabs"><a class="${!subject ? 'active' : ''}" href="#/classrooms">${h(t('common.all'))}</a>${state.subjects.map(s => `<a href="#/classrooms?subject=${h(s.id)}" class="${subject === s.id ? 'active' : ''}">${content(s.name)}</a>`).join('')}</nav>` + (visible.length ? `<div class="card-grid">${visible.map(roomCard).join('')}</div>` : `<div class="panel">${empty(t('classroom.empty'), t('classroom.empty_note'), isStaff() ? linkButton(t('classroom.create'), '/classrooms/new', 'plus') : '', 'classroom')}</div>`));
}
export async function classroomForm(id) {
    const room = id ? await api('/classrooms/' + id) : null;
    const users = state.user?.role === 'admin' && !id ? await api('/admin/users') : [];
    setView(titleBlock(t(id ? 'classroom.edit' : 'classroom.create'), t('classroom.description')) + `<form id="classroom-form" class="form-panel"><p class="field-help">${h(t('language.help'))}</p>${bilingual('name', t('common.title'), room?.name, true)}${bilingual('description', t('common.description'), room?.description, false, 3)}${!id ? `<div class="form-grid">${selectField(t('common.subject'), 'subject_id', state.subjects.map(s => ({ value: s.id, label: plain(s.name) })), routeURL().searchParams.get('subject') ?? state.subjects[0]?.id ?? '', 'required')}${state.user?.role === 'admin' ? selectField(t('common.teacher'), 'teacher_id', users.filter(u => u.active && u.role !== 'student').map(u => ({ value: u.id, label: u.display_name })), state.user.id, 'required') : ''}</div>` : checkbox(t('classroom.archive_label'), 'active', room?.active)}${formActions(id ? t('action.save') : t('action.create'), id ? '/classrooms/' + id : '/classrooms')}</form>`);
    bindForm('classroom-form', async (form) => { const body = { name: biValue(form, 'name'), description: biValue(form, 'description'), ...(id ? { active: formChecked(form, 'active') } : { subject_id: formValue(form, 'subject_id'), teacher_id: formValue(form, 'teacher_id') || null }) }; const result = await api(id ? '/classrooms/' + id : '/classrooms', id ? 'PATCH' : 'POST', body); toast(t('app.saved')); await navigate('/classrooms/' + result.id, true); });
}
export async function classroomPage(id) {
    const room = await api('/classrooms/' + id);
    const tab = routeURL().searchParams.get('tab') ?? 'overview';
    let actions = isStaff() ? linkButton(t('classroom.edit'), '/classrooms/' + id + '/edit', 'settings', 'secondary') : '';
    if (isStaff())
        actions += linkButton(t('classroom.invite'), '/invitations/new?classroom=' + id, 'plus');
    const tabs = [['overview', 'classroom.overview'], ['resources', 'classroom.resources'], ['members', 'classroom.members'], ['history', 'work.history']];
    let body = '';
    if (tab === 'members') {
        const users = state.user?.role === 'admin' ? await api('/admin/users') : [];
        body = panel(t('classroom.members'), room.members.length ? `<div class="table-wrap" style="border:0;border-radius:0"><table><thead><tr><th>${h(t('common.name'))}</th><th>${h(t('common.status'))}</th>${isStaff() ? `<th>${h(t('common.actions'))}</th>` : ''}</tr></thead><tbody>${room.members.map(m => `<tr><td><strong>${h(m.display_name)}</strong></td><td><span class="badge ${m.active ? 'phase-active' : ''}">${h(t(m.active ? 'common.active' : 'common.inactive'))}</span></td>${isStaff() ? `<td>${button(t('action.remove'), 'remove-member', 'trash', 'ghost small', `data-id="${h(m.id)}"`)}</td>` : ''}</tr>`).join('')}</tbody></table></div>` : `<p class="compact-empty">${h(t('classroom.no_members'))}</p>`);
        if (state.user?.role === 'admin')
            body += `<form id="enroll-form" class="form-panel" style="margin-top:22px"><h2>${h(t('classroom.enroll'))}</h2>${selectField(t('common.name'), 'user_id', users.filter(u => u.role === 'student' && u.active && !room.members.some(m => m.id === u.id)).map(u => ({ value: u.id, label: u.display_name })), '', 'required')}${formActions(t('classroom.enroll'))}</form>`;
    }
    else if (tab === 'resources') {
        body = panel(t('classroom.resources'), room.resources.length ? room.resources.map(r => `<article class="resource-card"><div class="toolbar"><h3>${content(r.title)}</h3>${isStaff() ? linkButton(t('action.edit'), `/classrooms/${id}/resource/${r.id}`, 'edit', 'ghost small') : ''}</div>${content(r.body, true)}${r.url ? `<p><a class="link" href="${h(r.url)}" target="_blank" rel="noopener noreferrer">${h(t('action.open'))}${icon('arrow')}</a></p>` : ''}<div>${attachmentList(r.files, isStaff())}</div>${isStaff() ? uploadControl('resource', r.id) : ''}</article>`).join('') : `<p class="compact-empty">${h(t('classroom.no_resources'))}</p>`, isStaff() ? linkButton(t('classroom.add_resource'), `/classrooms/${id}/resource/new`, 'plus', 'secondary small') : '');
    }
    else if (tab === 'history') {
        const { submissionRow } = await import('./ui.js');
        const submissions = await api('/submissions?classroom_id=' + id);
        body = panel(t('work.history'), submissions.length ? submissions.map(s => submissionRow(s, isStaff())).join('') : empty(t('grade.empty'), t('grade.empty_note')));
    }
    else {
        body = `<div class="two-col"><div class="stack">${panel(t('classroom.announcements'), room.announcements.length ? room.announcements.map(a => `<article class="resource-card"><div class="meta-line"><strong>${h(a.author_name)}</strong><span>${h(date(a.created_at))}</span></div>${content(a.body, true)}</article>`).join('') : `<p class="compact-empty">${h(t('classroom.no_announcements'))}</p>`, isStaff() ? button(t('classroom.add_announcement'), 'announcement', 'plus', 'secondary small') : '')}${panel(t('nav.assignments'), room.activities.length ? room.activities.map(activityRow).join('') : empty(t('activity.empty'), t('activity.empty_note')))}</div><aside class="stack">${panel(t('common.classroom'), `<div class="panel-body"><p class="muted small">${content(room.description)}</p><div class="meta-line">${icon('user')}${h(room.teacher_name)}</div><div class="meta-line">${icon('group')}${h(t('count.students', { count: room.member_count }))}</div>${isStaff() ? `<div class="stack" style="gap:10px;margin-top:20px">${linkButton(t('problem.create'), '/problems/new?classroom=' + id, 'plus', 'secondary')}${linkButton(t('activity.create_assignment'), '/activities/new?kind=assignment&classroom=' + id, 'assignment', 'secondary')}${linkButton(t('activity.create_session'), '/activities/new?kind=session&classroom=' + id, 'live', 'secondary')}</div>` : linkButton(t('nav.problems'), '/problems?classroom=' + id, 'book', 'secondary')}</div>`)}${panel(t('classroom.resources'), room.resources.slice(0, 4).map(r => `<a class="list-row" href="#/classrooms/${id}?tab=resources"><span class="row-icon">${icon('file')}</span><div class="row-content"><strong>${content(r.title)}</strong></div>${icon('chevron')}</a>`).join('') || `<p class="compact-empty">${h(t('classroom.no_resources'))}</p>`)}</aside></div><div id="announcement-editor" hidden></div>`;
    }
    setView(`<div class="breadcrumbs"><a href="#/classrooms">${h(t('nav.classrooms'))}</a>${icon('chevron')}${subjectBadge(room.subject_id)}</div>${titleBlock(plain(room.name), plain(room.description), actions)}${!room.active ? `<div class="notice warning">${icon('lock')}${h(t('classroom.archived'))}</div>` : ''}<nav class="tabs">${tabs.map(([key, label]) => `<a class="${tab === key ? 'active' : ''}" href="#/classrooms/${id}?tab=${key}">${h(t(label))}</a>`).join('')}</nav>${body}`);
    bindForm('enroll-form', async (form) => { await api(`/classrooms/${id}/members`, 'POST', { user_id: formValue(form, 'user_id') }); toast(t('app.saved')); await refresh(); });
    onAction('remove-member', async (element) => {
        if (!await confirmAction(t('classroom.remove_confirm')))
            return;
        await api(`/classrooms/${id}/members/${element.dataset.id}`, 'DELETE');
        await refresh();
    });
    onAction('announcement', () => { const container = document.getElementById('announcement-editor'); container.hidden = false; container.innerHTML = `<form id="announcement-form" class="form-panel wide" style="margin-top:22px"><h2>${h(t('classroom.add_announcement'))}</h2>${bilingual('body', t('classroom.body'), {}, true, 4)}${formActions(t('classroom.add_announcement'))}</form>`; container.scrollIntoView({ behavior: 'smooth' }); bindForm('announcement-form', async (form) => { await api(`/classrooms/${id}/announcements`, 'POST', { body: biValue(form, 'body') }); toast(t('app.saved')); await refresh(); }); });
    bindUploads(() => refresh());
}
export async function resourceForm(classroomId, id) {
    const room = await api('/classrooms/' + classroomId);
    const resource = room.resources.find(r => r.id === id);
    const topics = state.subjects.find(s => s.id === room.subject_id)?.topics ?? [];
    setView(titleBlock(t(resource ? 'action.edit' : 'classroom.add_resource'), plain(room.name)) + `<form id="resource-form" class="form-panel"><p class="field-help">${h(t('language.help'))}</p>${bilingual('title', t('common.title'), resource?.title, true)}${bilingual('body', t('classroom.body'), resource?.body, false, 7)}<div class="form-grid">${selectField(t('common.topic'), 'topic_id', [{ value: '', label: t('common.unassigned_topic') }, ...topics.map(topic => ({ value: topic.id, label: plain(topic.name) }))], resource?.topic_id ?? '')}${field(t('classroom.url'), 'url', resource?.url ?? '', 'url', 'maxlength="2000"')}</div><p class="field-help">${h(t('problem.math_help'))}</p>${formActions(t('action.save'), `/classrooms/${classroomId}?tab=resources`)}</form>`);
    bindForm('resource-form', async (form) => { await api(resource ? '/resources/' + id : `/classrooms/${classroomId}/resources`, resource ? 'PUT' : 'POST', { title: biValue(form, 'title'), body: biValue(form, 'body'), url: formValue(form, 'url') || null, topic_id: formValue(form, 'topic_id') || null }); toast(t('app.saved')); await navigate(`/classrooms/${classroomId}?tab=resources`, true); });
}
//# sourceMappingURL=pages-classrooms.js.map