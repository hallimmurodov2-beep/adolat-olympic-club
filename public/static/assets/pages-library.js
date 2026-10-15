import { api } from './api.js';
import { plain, t } from './i18n.js';
import { isStaff, state } from './state.js';
import { navigate, refresh, routeURL, setView } from './router.js';
import { biValue, bilingual, bindForm, bindUploads, button, checkbox, content, empty, enhance, field, formActions, formChecked, formValue, h, icon, linkButton, onAction, problemReading, selectField, subjectBadge, titleBlock, toast, uploadControl } from './ui.js';
export async function libraryPage() {
    const params = routeURL().searchParams;
    const rooms = await api('/classrooms');
    const query = new URLSearchParams();
    for (const key of ['q', 'subject_id', 'topic_id', 'difficulty', 'page'])
        if (params.get(key))
            query.set(key, params.get(key));
    if (params.get('classroom'))
        query.set('classroom_id', params.get('classroom'));
    const data = await api('/problems?' + query);
    const topics = state.subjects.filter(s => !params.get('subject_id') || s.id === params.get('subject_id')).flatMap(s => s.topics);
    const form = `<form id="library-filters" class="filters">${field(t('action.search'), 'q', params.get('q') ?? '', 'search', `placeholder="${h(t('common.search_placeholder'))}" maxlength="200"`)}${selectField(t('common.classroom'), 'classroom', [{ value: '', label: t('common.all') }, ...rooms.map(c => ({ value: c.id, label: plain(c.name) }))], params.get('classroom') ?? '')}${selectField(t('common.subject'), 'subject_id', [{ value: '', label: t('common.all') }, ...state.subjects.map(s => ({ value: s.id, label: plain(s.name) }))], params.get('subject_id') ?? '')}${selectField(t('common.topic'), 'topic_id', [{ value: '', label: t('common.all') }, ...topics.map(topic => ({ value: topic.id, label: plain(topic.name) }))], params.get('topic_id') ?? '')}${selectField(t('problem.difficulty'), 'difficulty', [{ value: '', label: t('common.all') }, ...[1, 2, 3, 4, 5].map(n => ({ value: String(n), label: t('problem.difficulty_level', { level: n }) }))], params.get('difficulty') ?? '')}<button class="button primary" type="submit">${icon('search')}${h(t('action.search'))}</button><a class="button ghost" href="#/problems">${h(t('action.reset'))}</a></form>`;
    const rows = data.items.map(p => `<tr>${isStaff() ? `<td class="selection-col"><input type="checkbox" name="selected_problem" value="${h(p.id)}" aria-label="${h(plain(p.title))}" data-classroom="${h(p.classroom_id)}"></td>` : ''}<td><a href="#/problems/${h(p.id)}"><strong>${content(p.title)}</strong></a><div class="muted">${content(p.topic)}${p.tags.length ? ' · ' + p.tags.map(tag => h(tag)).join(', ') : ''}</div></td><td>${subjectBadge(p.subject_id)}</td><td><span class="badge">${h(t('problem.difficulty_level', { level: p.difficulty }))}</span></td><td><span class="muted">${h(t(p.format === 'code' ? 'problem.code' : 'problem.written'))}</span>${isStaff() && !p.published ? `<div><span class="badge">${icon('lock')}${h(t('problem.private'))}</span></div>` : ''}</td><td><a class="icon-button" href="#/problems/${h(p.id)}" aria-label="${h(t('action.open'))}">${icon('arrow')}</a></td></tr>`).join('');
    const totalPages = Math.max(1, Math.ceil(data.total / data.limit));
    const pageLink = (page) => { const copy = new URLSearchParams(params); copy.set('page', String(page)); return '/problems?' + copy; };
    setView(titleBlock(t('nav.problems'), t('problem.description'), isStaff() ? linkButton(t('problem.create'), '/problems/new' + (params.get('classroom') ? '?classroom=' + params.get('classroom') : ''), 'plus') : '') + form + `<div class="toolbar"><span class="muted small">${h(t('count.problems', { count: data.total }))}</span>${isStaff() ? `<div>${button(t('set.create'), 'create-set', 'book', 'secondary small')}${linkButton(t('set.title'), '/sets', '', 'ghost small')}</div>` : ''}</div>` + (data.items.length ? `<div class="table-wrap"><table><thead><tr>${isStaff() ? '<th></th>' : ''}<th>${h(t('common.title'))}</th><th>${h(t('common.subject'))}</th><th>${h(t('problem.difficulty'))}</th><th>${h(t('problem.format'))}</th><th></th></tr></thead><tbody>${rows}</tbody></table></div>` : `<div class="panel">${empty(t('problem.empty'), t('problem.empty_note'), isStaff() ? linkButton(t('problem.create'), '/problems/new', 'plus') : '')}</div>`) + `<div class="pagination"><span>${h(t('common.page', { page: data.page, pages: totalPages }))}</span><div>${data.page > 1 ? linkButton(t('action.previous'), pageLink(data.page - 1), 'back', 'secondary small') : ''} ${data.page < totalPages ? linkButton(t('action.next'), pageLink(data.page + 1), 'arrow', 'secondary small') : ''}</div></div><div id="set-editor"></div>`);
    bindForm('library-filters', async (form) => {
        const query = new URLSearchParams();
        new FormData(form).forEach((value, key) => {
            if (String(value).trim())
                query.set(key, String(value).trim());
        });
        await navigate('/problems?' + query, true);
    });
    onAction('create-set', () => {
        const selected = [...document.querySelectorAll('input[name=selected_problem]:checked')];
        if (!selected.length) {
            toast(t('error.required'), true);
            return;
        }
        const classroom = selected[0].dataset.classroom;
        if (selected.some(el => el.dataset.classroom !== classroom)) {
            toast(t('error.invalid_problem'), true);
            return;
        }
        const target = document.getElementById('set-editor');
        target.innerHTML = `<form id="set-form" class="form-panel wide"><h2>${h(t('set.create'))}</h2><p class="field-help">${h(t('set.selected', { count: selected.length }))}</p>${bilingual('title', t('common.title'), {}, true)}${bilingual('description', t('common.description'), {}, false, 3)}${formActions(t('action.create'))}</form>`;
        target.scrollIntoView({ behavior: 'smooth' });
        bindForm('set-form', async (form) => { await api('/sets', 'POST', { classroom_id: classroom, title: biValue(form, 'title'), description: biValue(form, 'description'), problem_ids: selected.map(el => el.value) }); toast(t('app.saved')); await navigate('/sets', true); });
    });
}
export async function problemPage(id) {
    const problem = await api('/problems/' + id);
    setView(`<div class="breadcrumbs"><a href="#/problems">${h(t('nav.problems'))}</a>${icon('chevron')}${subjectBadge(problem.subject_id)}</div>${titleBlock(plain(problem.title), '', isStaff() ? linkButton(t('problem.edit'), '/problems/' + id + '/edit', 'edit') : '')}<div class="reading-panel"><div class="problem-meta">${subjectBadge(problem.subject_id)}<span>${content(problem.topic)}</span><span class="badge">${h(t('problem.difficulty_level', { level: problem.difficulty }))}</span><span>${h(t(problem.format === 'code' ? 'problem.code' : 'problem.written'))}</span>${problem.source ? `<span>${h(t('problem.source'))}: ${h(problem.source)}${problem.year ? ' · ' + h(problem.year) : ''}</span>` : ''}${problem.tags.length ? `<div class="tags">${problem.tags.map(tag => `<span class="tag">${h(tag)}</span>`).join('')}</div>` : ''}</div>${problemReading(problem, problem.files)}${isStaff() ? `<section class="problem-section"><p class="field-help">${h(t('problem.snapshot_note'))}</p>${uploadControl('problem', id)}</section>` : `<section class="problem-section"><p class="field-help">${h(t('problem.material_locked'))}</p><div class="notice">${icon('assignment')}<p>${h(t('problem.practice_note'))}</p></div>${linkButton(t('nav.assignments'), '/assignments?classroom=' + problem.classroom_id, 'assignment', 'secondary')}</section>`}</div>`);
    bindUploads(() => refresh());
}
export async function problemForm(id) {
    const [rooms, problem] = await Promise.all([api('/classrooms'), id ? api('/problems/' + id) : Promise.resolve(null)]);
    if (!rooms.length) {
        setView(empty(t('classroom.empty'), t('classroom.empty_note'), linkButton(t('classroom.create'), '/classrooms/new', 'plus')));
        return;
    }
    const classroomId = problem?.classroom_id ?? routeURL().searchParams.get('classroom') ?? rooms[0].id;
    const room = rooms.find(c => c.id === classroomId) ?? rooms[0];
    const topics = state.subjects.find(s => s.id === room.subject_id)?.topics ?? [];
    setView(titleBlock(t(id ? 'problem.edit' : 'problem.create'), t('language.help')) + `<form id="problem-form" class="form-panel wide"><div class="form-grid">${selectField(t('common.classroom'), 'classroom_id', rooms.map(c => ({ value: c.id, label: plain(c.name) })), room.id, id ? 'disabled' : 'required')}${selectField(t('common.topic'), 'topic_id', [{ value: '', label: t('common.unassigned_topic') }, ...topics.map(topic => ({ value: topic.id, label: plain(topic.name) }))], problem?.topic_id ?? '')}</div><div class="toolbar"><span class="field-help">${h(t('problem.math_help'))}</span><div>${button(t('topic.create'), 'new-topic', 'plus', 'ghost small')}${button(t('topic.edit'), 'edit-topic', 'edit', 'ghost small')}</div></div><div id="topic-editor"></div>${bilingual('title', t('common.title'), problem?.title, true)}${bilingual('statement', t('problem.statement'), problem?.statement, true, 8)}${bilingual('subtopic', t('problem.subtopic'), problem?.subtopic)}<div class="form-grid three">${selectField(t('problem.difficulty'), 'difficulty', [1, 2, 3, 4, 5].map(n => ({ value: String(n), label: t('problem.difficulty_level', { level: n }) })), String(problem?.difficulty ?? 2))}${selectField(t('problem.format'), 'format', [{ value: 'written', label: t('problem.written') }, { value: 'code', label: t('problem.code') }], problem?.format ?? (room.subject_id === 'informatics' ? 'code' : 'written'))}${field(t('problem.year'), 'year', problem?.year ? String(problem.year) : '', 'number', 'min="1900" max="2200"')}</div><div class="form-grid">${field(t('problem.source'), 'source', problem?.source ?? '', 'text', 'maxlength="300"')}${field(t('problem.tags'), 'tags', problem?.tags.join(', ') ?? '', 'text', 'maxlength="700"')}</div>${bilingual('examples', t('problem.examples'), problem?.examples, false, 4)}${bilingual('hints', t('problem.hints'), problem?.hints, false, 4)}${bilingual('solution', t('problem.solution'), problem?.solution, false, 7)}${checkbox(t('problem.published'), 'published', problem?.published ?? false)}<div class="notice">${icon('lock')}<p>${h(t('problem.snapshot_note'))}</p></div>${button(t('problem.preview'), 'preview-problem', 'eye', 'secondary')}<div id="problem-preview" style="margin-top:20px"></div>${formActions(t('action.save'), id ? '/problems/' + id : '/problems')}</form>`);
    const form = document.getElementById('problem-form');
    const selectedRoom = () => rooms.find(c => c.id === (id ? problem.classroom_id : formValue(form, 'classroom_id'))) ?? room;
    const updateTopics = (selected = '') => { const options = state.subjects.find(s => s.id === selectedRoom().subject_id)?.topics ?? []; const select = form.elements.namedItem('topic_id'); select.innerHTML = `<option value="">${h(t('common.unassigned_topic'))}</option>` + options.map(topic => `<option value="${h(topic.id)}" ${topic.id === selected ? 'selected' : ''}>${h(plain(topic.name))}</option>`).join(''); };
    form.elements.namedItem('classroom_id').addEventListener('change', () => updateTopics());
    const openTopic = (edit) => {
        const subject = selectedRoom().subject_id;
        const current = state.subjects.find(s => s.id === subject)?.topics.find(topic => topic.id === formValue(form, 'topic_id'));
        if (edit && !current) {
            toast(t('error.required'), true);
            return;
        }
        const target = document.getElementById('topic-editor');
        target.innerHTML = `<div class="notice" style="display:block">${bilingual('new_topic', t(edit ? 'topic.edit' : 'topic.create'), current?.name ?? {}, false)}${button(t('action.save'), 'save-topic', 'check', 'secondary')}</div>`;
        onAction('save-topic', async () => {
            const name = biValue(form, 'new_topic');
            if (!Object.keys(name).length) {
                toast(t('language.required'), true);
                return;
            }
            const topic = await api(edit ? '/topics/' + current.id : '/topics', edit ? 'PUT' : 'POST', { subject_id: subject, name });
            const entry = state.subjects.find(s => s.id === subject);
            entry.topics = entry.topics.filter(t => t.id !== topic.id).concat(topic);
            updateTopics(topic.id);
            target.innerHTML = '';
            toast(t('app.saved'));
        }, target);
    };
    onAction('new-topic', () => openTopic(false));
    onAction('edit-topic', () => openTopic(true));
    const readBody = () => ({ classroom_id: selectedRoom().id, topic_id: formValue(form, 'topic_id') || null, title: biValue(form, 'title'), statement: biValue(form, 'statement'), subtopic: biValue(form, 'subtopic'), hints: biValue(form, 'hints'), solution: biValue(form, 'solution'), examples: biValue(form, 'examples'), difficulty: Number(formValue(form, 'difficulty')), format: formValue(form, 'format'), year: formValue(form, 'year') ? Number(formValue(form, 'year')) : null, source: formValue(form, 'source').trim(), tags: formValue(form, 'tags').split(',').map(s => s.trim()).filter(Boolean), published: formChecked(form, 'published'), ...(problem ? { version: problem.version } : {}) });
    onAction('preview-problem', async () => { const target = document.getElementById('problem-preview'); target.innerHTML = `<div class="reading-panel"><h2>${content(biValue(form, 'title'))}</h2>${problemReading({ ...readBody(), version: problem?.version ?? 1 })}</div>`; await enhance(target); });
    bindForm('problem-form', async () => { const saved = await api(id ? '/problems/' + id : '/problems', id ? 'PUT' : 'POST', readBody()); toast(t('app.saved')); await navigate('/problems/' + saved.id, true); });
}
export async function setsPage() {
    const sets = await api('/sets');
    setView(titleBlock(t('set.title'), t('problem.description'), linkButton(t('nav.problems'), '/problems', 'book', 'secondary')) + (sets.length ? `<div class="card-grid">${sets.map(s => `<article class="classroom-card"><span class="row-icon">${icon('book')}</span><h2 style="margin-top:18px">${content(s.title)}</h2><p>${content(s.description)}</p><p>${h(t('count.problems', { count: s.problem_ids.length }))}</p>${linkButton(t('activity.create_assignment'), `/activities/new?kind=assignment&classroom=${s.classroom_id}&set=${s.id}`, 'plus', 'secondary')}${button(t('set.clone'), 'clone-set', 'copy', 'secondary small', `data-id="${h(s.id)}"`)}</article>`).join('')}</div>` : `<div class="panel">${empty(t('set.empty'), t('set.create'), linkButton(t('nav.problems'), '/problems', 'book'))}</div>`));
    onAction('clone-set', async (el) => { const result = await api('/sets/' + el.dataset.id + '/clone', 'POST', {}); toast(t('set.cloned')); await refresh(); });
}
//# sourceMappingURL=pages-library.js.map