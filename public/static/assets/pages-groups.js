import { api } from './api.js';
import { date, plain, t } from './i18n.js';
import { isStaff } from './state.js';
import { navigate, refresh, routeURL, setCleanup, setRemoteHandler, setView } from './router.js';
import { bindForm, button, checkbox, confirmAction, content, empty, enhance, field, formActions, formValue, h, linkButton, onAction, panel, problemReading, rich, selectField, titleBlock, toast } from './ui.js';
import { editorHTML, WorkEditor } from './work-editor.js';
export async function groupsPage() { const groups = await api('/groups'); setView(titleBlock(t('nav.groups'), t('group.description'), isStaff() ? linkButton(t('group.create'), '/groups/new', 'plus') : '') + (groups.length ? `<div class="card-grid">${groups.map(g => `<a class="classroom-card panel" href="#/groups/${g.id}"><span class="badge">${h(t(g.shared ? 'group.shared' : 'group.private'))}</span><h2>${h(g.name)}</h2><p>${content(g.problem_title)}</p><p class="muted">${g.members.map(m => h(m.display_name)).join(' · ')}</p><div class="card-footer">${h(t('group.revision', { number: g.revision }))} · ${h(date(g.updated_at))}</div></a>`).join('')}</div>` : empty(t('group.empty'), t('group.empty_note')))); }
export async function groupForm() {
    const rooms = await api('/classrooms');
    const roomId = routeURL().searchParams.get('classroom') ?? rooms[0]?.id;
    if (!roomId) {
        setView(empty(t('classroom.empty'), t('classroom.empty_note')));
        return;
    }
    const [room, activities] = await Promise.all([api('/classrooms/' + roomId), api('/activities?classroom_id=' + roomId)]);
    const eligible = activities.filter(a => a.kind !== 'competition' && a.phase !== 'ended');
    const details = await Promise.all(eligible.map(a => api('/activities/' + a.id)));
    const items = details.flatMap(a => a.items.map(item => ({ value: item.id, label: plain(a.title) + ' — ' + plain(item.problem.title) })));
    setView(titleBlock(t('group.create'), t('group.description')) + `<form id="group-form" class="form-panel">${selectField(t('common.classroom'), 'classroom_id', rooms.filter(r => r.active).map(r => ({ value: r.id, label: plain(r.name) })), roomId)}${field(t('group.name'), 'name', '', 'text', 'required maxlength="100"')}${selectField(t('group.select_task'), 'activity_item_id', items, '', 'required')}<fieldset class="fieldset"><legend>${h(t('group.members'))}</legend>${room.members.filter(m => m.active !== false).map(m => checkbox(m.display_name, 'member', false, m.id)).join('')}</fieldset>${checkbox(t('group.share_label'), 'shared')}${formActions(t('action.create'), '/groups')}</form>`);
    document.querySelector('[name=classroom_id]')?.addEventListener('change', e => { void navigate('/groups/new?classroom=' + e.target.value, true); });
    bindForm('group-form', async (form) => { const result = await api('/groups', 'POST', { classroom_id: roomId, activity_item_id: formValue(form, 'activity_item_id'), name: formValue(form, 'name'), user_ids: new FormData(form).getAll('member').map(String), shared: new FormData(form).has('shared') }); await navigate('/groups/' + result.id, true); });
}
export async function groupPage(id) {
    let group = await api('/groups/' + id);
    const options = { id: 'group-editor', itemId: group.activity_item_id, groupId: id, work: group.document, files: group.files, format: group.item.problem.format, canEdit: group.can_edit && (isStaff() || group.phase === 'active'), canSubmit: !isStaff() && group.can_edit && group.phase === 'active', title: t('group.document') };
    setView(titleBlock(group.name, group.members.map(m => m.display_name).join(' · '), isStaff() ? button(t(group.shared ? 'group.shared' : 'group.private'), 'share', 'eye') : '') + `<p class="field-help">${h(t('group.autosave_note'))}</p>${!group.can_edit ? `<div class="notice">${h(t('group.view_only'))}</div>` : ''}<div class="group-layout"><div>${problemReading(group.item.problem, group.item.files)}${editorHTML(options)}<p class="field-help">${h(t('group.submit_note'))}</p></div><aside><div id="group-discussion"></div>${options.canEdit ? `<form id="comment-form" class="form-panel"><label class="field"><span>${h(t('group.comment'))}</span><textarea name="body" rows="4" required maxlength="5000" placeholder="${h(t('group.comment_placeholder'))}"></textarea></label>${formActions(t('action.send'))}</form>` : ''}<div id="group-revisions"></div></aside></div>`);
    const editor = new WorkEditor(options);
    const patch = async () => {
        document.getElementById('group-discussion').innerHTML = panel(t('group.discussion'), group.comments.length ? (group.comments_next_cursor ? button(t('group.older_comments'), 'older-comments', '', 'secondary small') : '') + group.comments.map(c => `<article class="comment"><header><strong>${h(c.author_name)}</strong><small>${h(date(c.created_at))}</small></header>${rich(c.body)}</article>`).join('') : `<p class="panel-empty">${h(t('group.no_comments'))}</p>`);
        document.getElementById('group-revisions').innerHTML = panel(t('group.revisions'), group.revisions.length ? group.revisions.map(r => `<details class="revision"><summary>${h(t('group.revision', { number: r.revision }))} · ${h(r.author_name)}<small>${h(date(r.created_at))}</small></summary><pre>${h(r.content)}</pre>${options.canEdit ? button(t('action.restore'), 'restore', '', 'secondary small', `data-revision="${r.revision}"`) : ''}</details>`).join('') : `<p class="panel-empty">${h(t('group.no_revisions'))}</p>`);
        onAction('restore', async (el) => {
            const r = group.revisions.find(r => r.revision === Number(el.dataset.revision));
            if (r && await confirmAction(t('work.restore_confirm')))
                editor.setText(r.content, r.language);
        });
        onAction('older-comments', async () => {
            if (!group.comments_next_cursor)
                return;
            const page = await api('/groups/' + id + '/comments?cursor=' + encodeURIComponent(group.comments_next_cursor));
            const known = new Set(group.comments.map(c => c.id));
            group.comments = [...page.items.filter(c => !known.has(c.id)), ...group.comments];
            group.comments_next_cursor = page.next_cursor;
            await patch();
        });
        await enhance(document.getElementById('group-discussion'));
    };
    const update = async () => {
        group = await api('/groups/' + id);
        editor.receive(group.document);
        editor.updateFiles(group.files);
        if (!isStaff() && group.phase !== 'active')
            editor.close();
        await patch();
    };
    bindForm('comment-form', async (form) => { await api('/groups/' + id + '/comments', 'POST', { body: formValue(form, 'body') }); form.reset(); await update(); });
    onAction('share', async () => {
        if (!await confirmAction(t('group.share_confirm')))
            return;
        await api('/groups/' + id, 'PATCH', { shared: !group.shared });
        toast(t('app.saved'));
        await refresh();
    });
    await patch();
    setRemoteHandler(() => update());
    setCleanup(() => editor.dispose());
}
//# sourceMappingURL=pages-groups.js.map