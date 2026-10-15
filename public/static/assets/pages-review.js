import { api } from './api.js';
import { date, number, plain, t } from './i18n.js';
import { isStaff } from './state.js';
import { refresh, routeURL, setView, setRemoteHandler } from './router.js';
import { attachmentList, biValue, bilingual, bindForm, checkbox, content, empty, field, formActions, formChecked, formValue, h, linkButton, panel, problemReading, reviewBadge, rich, selectField, submissionRow, titleBlock, toast } from './ui.js';
export async function submissionsPage() {
    const params = routeURL().searchParams;
    const filter = params.get('status') ?? (isStaff() ? 'submitted' : 'all');
    if (!isStaff()) {
        const list = await api('/submissions');
        const shown = filter === 'all' ? list : list.filter(s => s.status === filter);
        setView(titleBlock(t('nav.submissions'), t('grade.description')) +
            panel(t('work.history'), shown.length ? shown.map(s => submissionRow(s, false)).join('') : empty(t('grade.empty'), t('grade.empty_note'))));
        return;
    }
    const classroom = params.get('classroom') ?? '';
    const cursor = params.get('cursor') ?? '';
    const [rooms, page] = await Promise.all([
        api('/classrooms'),
        api('/reviews/queue?status=' + encodeURIComponent(filter) +
            (classroom ? '&classroom_id=' + encodeURIComponent(classroom) : '') + (cursor ? '&cursor=' + encodeURIComponent(cursor) : ''))
    ]);
    const query = (status, nextCursor = '') => '/submissions?status=' + status + (classroom ? '&classroom=' + encodeURIComponent(classroom) : '') +
        (nextCursor ? '&cursor=' + encodeURIComponent(nextCursor) : '');
    setView(titleBlock(t('nav.submissions'), t('review.queue_explanation')) +
        `<nav class="tabs" aria-label="${h(t('review.filter'))}">${['submitted', 'revision_requested', 'reviewed', 'all'].map(status => `<a class="tab ${status === filter ? 'active' : ''}" href="#${query(status)}">${h(t(status === 'all' ? 'common.all' : 'grade.' + status))}</a>`).join('')}</nav>` +
        `<form id="review-filter" class="filter-bar">${selectField(t('common.classroom'), 'classroom', [
            { value: '', label: t('common.all') }, ...rooms.map(r => ({ value: r.id, label: plain(r.name) }))
        ], classroom)}
            ${formActions(t('action.filter'))}</form>` +
        panel(t('review.queue'), page.items.length ? page.items.map(s => submissionRow(s, true)).join('') :
            empty(t('review.no_results'), t('grade.empty_note'))) +
        (page.next_cursor ? `<div class="section-header">${linkButton(t('training.more'), query(filter, page.next_cursor), 'arrow', 'secondary')}</div>` : '') +
        `<p class="field-help">${h(t('review.page_note'))}</p>`);
    bindForm('review-filter', async (form) => {
        await import('./router.js').then(r => r.navigate('/submissions?status=' + encodeURIComponent(filter) +
            (formValue(form, 'classroom') ? '&classroom=' + encodeURIComponent(formValue(form, 'classroom')) : ''), true));
    });
}
export async function submissionPage(id) {
    // Staff reviews are explicit versioned edits. A late stream-ready or queued
    // activity update must not replace a form between focus/input/click. Saving
    // refetches the canonical state; a competing grader still receives a CAS conflict.
    if (isStaff())
        setRemoteHandler(() => { });
    const submission = await api('/submissions/' + id);
    const s = submission;
    const related = await api('/submissions?activity_id=' + s.activity_id);
    const attempts = related.filter(a => a.activity_item_id === s.activity_item_id && (isStaff() ? a.group_id === s.group_id && a.user_id === s.user_id : true));
    const review = isStaff() ? `<form id="grade-form" class="form-panel"><h2>${h(t('grade.title'))}</h2>${s.rubric.length ? s.rubric.map((r, i) => field(plain(r.name) + ' / ' + number(r.max), 'criterion_' + i, String(s.criterion_scores[i] ?? 0), 'number', `min="0" max="${r.max}" step="0.01" required`)).join('') : field(t('grade.score') + ' / ' + number(s.points), 'score', s.score === null ? '' : String(s.score), 'number', `min="0" max="${s.points}" step="0.01" required`)}${selectField(t('common.status'), 'status', [{ value: 'reviewed', label: t('grade.reviewed') }, { value: 'revision_requested', label: t('grade.revision_requested') }], s.status === 'submitted' ? 'reviewed' : s.status)}${bilingual('feedback', t('grade.feedback'), s.feedback, false, 4)}${s.kind === 'competition' ? `<div class="notice"><p>${h(t('grade.competition_gate'))} ${h(t('grade.sealed_preview'))}</p></div>` : checkbox(t('grade.release'), 'release', s.released) + `<p class="field-help">${h(t('grade.release_preview'))}</p>`}${formActions(t('grade.save'))}</form>` : panel(t('grade.title'), s.released ? `<div class="panel-body">${reviewBadge(s)}<p class="score-large">${h(number(s.score ?? 0))}<span> / ${h(number(s.points))}</span></p>${s.rubric.map((r, i) => `<p>${content(r.name)} <strong>${h(number(s.criterion_scores[i] ?? 0))} / ${h(number(r.max))}</strong></p>`).join('')}${content(s.feedback, true)}</div>` : `<p class="panel-empty">${h(t('grade.no_feedback'))}</p>`);
    setView(titleBlock(plain(s.problem_title), t('work.attempt', { number: s.attempt }) + ' · ' + date(s.created_at), linkButton(t('action.back'), '/activities/' + s.activity_id, 'back', 'secondary')) + `<div class="review-layout"><div>${s.problem ? `<details class="panel problem-context"><summary>${h(t('problem.statement'))}</summary>${problemReading(s.problem)}</details>` : ''}<section class="panel"><header class="panel-heading"><h2>${h(t('work.title'))}</h2>${reviewBadge(s)}</header><div class="panel-body"><p class="muted">${h(t('grade.author'))}: ${h(s.author_name)}</p>${s.language === 'written' ? rich(s.content ?? '') : `<p class="badge">${s.language === 'python' ? 'Python' : 'C++'}</p><pre><code class="language-${h(s.language)}">${h(s.content ?? '')}</code></pre>`}${attachmentList(s.files ?? [])}</div></section>${panel(t('work.history'), attempts.map(a => submissionRow(a, isStaff())).join(''))}${isStaff() && s.grade_history?.length ? panel(t('grade.history'), s.grade_history.map(g => `<article class="comment"><strong>${h(t('group.revision', { number: g.version }))} · ${h(number(g.score))} / ${h(number(s.points))}</strong><p class="muted">${h(g.teacher_name)} · ${h(date(g.created_at))} · ${h(t(g.released ? 'common.published' : 'grade.private'))}</p>${content(g.feedback, true)}</article>`).join('')) : ''}</div><aside>${review}</aside></div>`);
    bindForm('grade-form', async (form) => { const criteria = s.rubric.map((_, i) => Number(formValue(form, 'criterion_' + i))); await api('/submissions/' + id + '/grade', 'PUT', { score: s.rubric.length ? criteria.reduce((a, b) => a + b, 0) : Number(formValue(form, 'score')), criterion_scores: criteria, feedback: biValue(form, 'feedback'), status: formValue(form, 'status'), release: s.kind !== 'competition' && formChecked(form, 'release'), version: s.grade_version }); toast(t('grade.saved')); await refresh(); });
}
//# sourceMappingURL=pages-review.js.map