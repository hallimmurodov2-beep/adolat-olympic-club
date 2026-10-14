import { state } from './state.js';
import { date, number, plain, t } from './i18n.js';
import { api } from './api.js';
import type { Activity, Attachment, Bi, Phase, ProblemContent, Submission } from './types.js';
export const h = (value: unknown): string => String(value ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c] ?? c));
const paths: Record<string, string> = {
    home: '<path d="m3 10 9-7 9 7v10a1 1 0 0 1-1 1h-5v-8H9v8H4a1 1 0 0 1-1-1z"/>',
    classroom: '<rect x="3" y="3" width="18" height="14" rx="2"/><path d="M7 21h10M12 17v4M7 8h10M7 12h6"/>',
    book: '<path d="M12 5c-3-2-6-2-10-1v15c4-1 7-1 10 1 3-2 6-2 10-1V4c-4-1-7-1-10 1zM12 5v15"/>',
    assignment: '<rect x="5" y="4" width="14" height="17" rx="2"/><path d="M9 4V2h6v2M9 10h6M9 14h6M9 18h3"/>',
    live: '<circle cx="12" cy="12" r="2"/><path d="M7.8 7.8a6 6 0 0 0 0 8.4m8.4-8.4a6 6 0 0 1 0 8.4M4.9 4.9a10 10 0 0 0 0 14.2m14.2-14.2a10 10 0 0 1 0 14.2"/>',
    group: '<circle cx="9" cy="8" r="3"/><path d="M3 21v-3a6 6 0 0 1 12 0v3M16 5a3 3 0 0 1 0 6m2 3a5 5 0 0 1 3 4v3"/>',
    trophy: '<path d="M7 3h10v5a5 5 0 0 1-10 0zM7 5H3v2a4 4 0 0 0 4 4m10-6h4v2a4 4 0 0 1-4 4M12 13v6m-5 2h10"/>',
    check: '<path d="m5 12 4 4L19 6"/>',
    review: '<path d="M21 11v9a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h9m2 0 6 6m-9 5 8-8 3 3-8 8-4 1z"/>',
    chart: '<path d="M3 3v18h18M7 16v-5m5 5V7m5 9V4"/>',
    bell: '<path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M10 21h4"/>',
    settings: '<path d="m9 3-1 3-3 1-2 3 2 2-1 3 3 2 3-1 2 3 3-1 1-3 3-1 1-3-2-2 1-3-3-2-3 1-2-3z"/><circle cx="12" cy="11" r="3"/>',
    user: '<circle cx="12" cy="8" r="4"/><path d="M4 21v-2a8 8 0 0 1 16 0v2"/>',
    help: '<circle cx="12" cy="12" r="9"/><path d="M9 9a3 3 0 1 1 5 2c-2 1-2 2-2 3m0 3h.01"/>',
    plus: '<path d="M12 5v14M5 12h14"/>',
    arrow: '<path d="M4 12h16m-6-6 6 6-6 6"/>',
    back: '<path d="M20 12H4m6-6-6 6 6 6"/>',
    search: '<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/>',
    close: '<path d="m6 6 12 12M6 18 18 6"/>',
    menu: '<path d="M4 6h16M4 12h16M4 18h16"/>',
    sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M2 12h2m16 0h2M5 5l1 1m12 12 1 1M5 19l1-1M18 6l1-1"/>',
    moon: '<path d="M20.9 13a9 9 0 1 1-9.9-9.9A7 7 0 0 0 20.9 13Z"/>',
    logout: '<path d="M9 4H4v16h5m6-16 6 8-6 8M8 12h13"/>',
    lock: '<rect x="5" y="10" width="14" height="11" rx="2"/><path d="M8 10V6a4 4 0 0 1 8 0v4M12 14v3"/>',
    clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    calendar: '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M7 2v6m10-6v6M3 11h18"/>',
    file: '<path d="M14 2H5v20h14V7zM14 2v5h5M8 12h8m-8 4h6"/>',
    upload: '<path d="M12 16V3m-5 5 5-5 5 5M4 16v5h16v-5"/>',
    download: '<path d="M12 3v13m-5-5 5 5 5-5M4 17v4h16v-4"/>',
    edit: '<path d="m16 3 5 5-12 12-6 1 1-6zM13 6l5 5"/>',
    trash: '<path d="M3 6h18M8 6V3h8v3M5 6l1 15h12l1-15M9 10v7m6-7v7"/>',
    eye: '<path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/>',
    expand: '<path d="M8 3H3v5m13-5h5v5M3 16v5h5m13-5v5h-5"/>',
    code: '<path d="m8 6-6 6 6 6m8-12 6 6-6 6M14 3l-4 18"/>',
    atom: '<ellipse cx="12" cy="12" rx="10" ry="4" transform="rotate(30 12 12)"/><ellipse cx="12" cy="12" rx="10" ry="4" transform="rotate(-30 12 12)"/><circle cx="12" cy="12" r="1"/>',
    math: '<path d="M18 4H6l8 8-8 8h12"/>',
    copy: '<rect x="8" y="8" width="12" height="13" rx="2"/><path d="M16 8V3H3v13h5"/>',
    chevron: '<path d="m9 5 7 7-7 7"/>',
};
export function icon(name: string, cls = ''): string { return `<svg class="icon ${h(cls)}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${paths[name] ?? paths.book}</svg>`; }
export function content(value: Bi | undefined | null, richText = false): string {
    const text = plain(value);
    if (!text)
        return '';
    const fallback = !value?.[state.locale];
    const source = state.locale === 'ru' ? 'en' : 'ru';
    return `${richText ? rich(text) : h(text)}${fallback ? ` <span class="language-badge" title="${h(t('language.original', { language: t('language.' + source) }))}">${h(t('language.original', { language: t('language.' + source) }))}</span>` : ''}`;
}
export function rich(text: string): string {
    // Escape first; never accept HTML from users. TeX is handled separately by restricted MathJax.
    const segments = text.split(/```/);
    return segments.map((part, index) => {
        if (index % 2) {
            const lines = part.split('\n');
            const language = (lines.shift() ?? '').trim();
            return `<pre><code class="language-${['python', 'cpp'].includes(language) ? language : 'none'}">${h(lines.join('\n'))}</code></pre>`;
        }
        return `<div class="prose">${h(part).replace(/\*\*([^*\n]+)\*\*/g, '<strong>$1</strong>')}</div>`;
    }).join('');
}
export function titleBlock(title: string, description = '', actions = '', eyebrow = ''): string { return `<header class="page-heading"><div>${eyebrow ? `<p class="eyebrow">${h(eyebrow)}</p>` : ''}<h1>${h(title)}</h1>${description ? `<p class="page-description">${h(description)}</p>` : ''}</div>${actions ? `<div class="heading-actions">${actions}</div>` : ''}</header>`; }
export const linkButton = (label: string, path: string, iconName = '', cls = 'primary'): string => `<a class="button ${h(cls)}" href="#${h(path)}">${iconName ? icon(iconName) : ''}<span>${h(label)}</span></a>`;
export function button(label: string, action: string, iconName = '', cls = 'secondary', extra = ''): string { return `<button type="button" class="button ${h(cls)}" data-action="${h(action)}" ${extra}>${iconName ? icon(iconName) : ''}<span>${h(label)}</span></button>`; }
export function statusBadge(phase: Phase): string { return `<span class="badge phase-${phase}">${phase === 'active' ? '<span class="status-dot"></span>' : ''}${h(t('phase.' + phase))}</span>`; }
export function reviewBadge(submission: Submission): string { return `<span class="badge review-${submission.status}">${h(t('grade.' + submission.status))}</span>`; }
export function subjectBadge(subject: string): string { const value = state.subjects.find(s => s.id === subject); return `<span class="subject-label ${h(subject)}">${icon(subject === 'math' ? 'math' : subject === 'physics' ? 'atom' : 'code')}${content(value?.name)}</span>`; }
export function empty(title: string, note: string, action = '', iconName = 'book'): string { return `<div class="empty-state"><span class="empty-icon">${icon(iconName)}</span><h3>${h(title)}</h3><p>${h(note)}</p>${action}</div>`; }
export function panel(title: string, body: string, action = '', cls = ''): string { return `<section class="panel ${h(cls)}"><div class="panel-heading"><h2>${h(title)}</h2>${action}</div>${body}</section>`; }
export function activityRow(a: Activity): string { return `<a class="list-row activity-row" href="#/activities/${h(a.id)}"><span class="row-icon ${h(a.subject_id)}">${icon(a.kind === 'assignment' ? 'assignment' : a.kind === 'session' ? 'live' : 'trophy')}</span><div class="row-content"><strong>${content(a.title)}</strong><span class="muted">${content(a.classroom_name)} · ${h(t('activity.' + a.kind))}</span></div><div class="row-meta">${statusBadge(a.phase)}<span>${h(date(a.ends_at ?? a.starts_at))}</span></div>${icon('chevron')}</a>`; }
export function submissionRow(s: Submission, showAuthor = false): string { return `<a class="list-row" href="#/submissions/${h(s.id)}"><span class="row-icon">${icon(s.language === 'written' ? 'file' : 'code')}</span><div class="row-content"><strong>${content(s.problem_title)}</strong><span class="muted">${showAuthor ? h(s.author_name) + ' · ' : ''}${h(t('work.attempt', { number: s.attempt }))} · ${h(date(s.created_at))}</span></div><div class="row-meta">${reviewBadge(s)}${s.score !== null ? `<strong>${h(number(s.score))} / ${h(number(s.points))}</strong>` : ''}</div>${icon('chevron')}</a>`; }
export function attachmentList(files: Attachment[], removable = false): string { if (!files.length)
    return `<p class="muted small">${h(t('file.none'))}</p>`; return `<div class="attachment-list">${files.map(f => `<div class="attachment"><a href="/api/files/${h(f.id)}" target="_blank" rel="noopener">${icon('file')}<span>${h(f.filename)}<small>${h(number(f.size / 1024, 1))} ${h(t('file.kib'))}</small></span>${icon('download')}</a>${removable ? `<button type="button" class="icon-button" data-delete-file="${h(f.id)}" aria-label="${h(t('action.delete'))}">${icon('trash')}</button>` : ''}</div>`).join('')}</div>`; }
export function uploadControl(kind: string, target: string): string {
    return `<div class="upload-widget"><label class="button secondary upload-label">${icon('upload')}<span>${h(t('action.upload'))}</span><input type="file" data-upload-kind="${h(kind)}" data-upload-target="${h(target)}" accept=".png,.jpg,.jpeg,.webp,.pdf,.txt,.py,.cpp" aria-label="${h(t('action.upload'))}"></label><p class="field-help">${h(t('file.help'))}</p><p class="field-help" data-upload-quota></p><div role="status" aria-live="polite" data-upload-status></div></div>`;
}
export function field(label: string, name: string, value = '', type = 'text', attrs = '', help = ''): string { return `<label class="field"><span>${h(label)}</span><input name="${h(name)}" id="field-${h(name)}" type="${h(type)}" value="${h(value)}" ${attrs}>${help ? `<small>${h(help)}</small>` : ''}</label>`; }
export function textarea(label: string, name: string, value = '', rows = 4, attrs = ''): string { return `<label class="field"><span>${h(label)}</span><textarea name="${h(name)}" id="field-${h(name)}" rows="${rows}" ${attrs}>${h(value)}</textarea></label>`; }
export function selectField(label: string, name: string, options: {
    value: string;
    label: string;
}[], selected = '', attrs = ''): string { return `<label class="field"><span>${h(label)}</span><select name="${h(name)}" id="field-${h(name)}" ${attrs}>${options.map(o => `<option value="${h(o.value)}" ${o.value === selected ? 'selected' : ''}>${h(o.label)}</option>`).join('')}</select></label>`; }
export function checkbox(label: string, name: string, checked = false, value = 'on'): string { return `<label class="checkbox"><input type="checkbox" name="${h(name)}" value="${h(value)}" ${checked ? 'checked' : ''}><span>${h(label)}</span></label>`; }
export function bilingual(name: string, label: string, value: Bi = {}, required = false, rows = 1): string { return `<fieldset class="bilingual" ${required ? 'data-bi-required="' + h(name) + '"' : ''}><legend>${h(label)}${required ? ' <span class="required-dot">*</span>' : ''}</legend><div class="form-grid">${(['ru', 'en'] as const).map(locale => rows === 1 ? field(t('language.' + locale), name + '_' + locale, value[locale] ?? '', 'text', 'maxlength="500"') : textarea(t('language.' + locale), name + '_' + locale, value[locale] ?? '', rows, 'maxlength="50000"')).join('')}</div></fieldset>`; }
export function biValue(form: HTMLFormElement, name: string): Bi { const result: Bi = {}; for (const locale of ['ru', 'en'] as const) {
    const value = formValue(form, name + '_' + locale).trim();
    if (value)
        result[locale] = value;
} return result; }
export function formValue(form: HTMLFormElement, name: string): string { return String(new FormData(form).get(name) ?? ''); }
export function formChecked(form: HTMLFormElement, name: string): boolean { return new FormData(form).has(name); }
export function formActions(label = t('action.save'), back = ''): string { return `<div class="form-actions"><button type="submit" class="button primary">${icon('check')}<span>${h(label)}</span></button>${back ? linkButton(t('action.cancel'), back, '', 'ghost') : ''}</div>`; }
export function toast(message: string, error = false): void { const region = document.getElementById('toast-region')!; const node = document.createElement('div'); node.className = 'toast ' + (error ? 'toast-error' : ''); node.setAttribute('role', error ? 'alert' : 'status'); node.textContent = message; region.append(node); setTimeout(() => node.remove(), error ? 10000 : 4500); }
export function showError(error: unknown): void { toast(error instanceof Error ? error.message : t('error.unexpected'), true); }
export function onAction(action: string, callback: (element: HTMLButtonElement) => void | Promise<void>, root: ParentNode = document): void { root.querySelectorAll<HTMLButtonElement>(`[data-action="${action}"]`).forEach(el => el.addEventListener('click', () => { Promise.resolve(callback(el)).catch(showError); })); }
export function validateForm(form: HTMLFormElement): boolean {
    const inputs = form.querySelectorAll<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>('input,textarea,select');
    for (const input of inputs) {
        input.setCustomValidity('');
        if (input.disabled)
            continue;
        if (input.required && !input.value.trim()) {
            input.setCustomValidity(t('error.required'));
            input.reportValidity();
            return false;
        }
        if (input instanceof HTMLInputElement && input.type === 'email' && input.validity.typeMismatch) {
            input.setCustomValidity(t('error.invalid_email'));
            input.reportValidity();
            return false;
        }
        if ((input instanceof HTMLInputElement || input instanceof HTMLTextAreaElement) && input.minLength > 0 && input.value.length < input.minLength) {
            input.setCustomValidity(t(input instanceof HTMLInputElement && input.type === 'password' ? 'error.password_length' : 'error.invalid_input'));
            input.reportValidity();
            return false;
        }
        if (input.validity.rangeOverflow || input.validity.rangeUnderflow || input.validity.badInput) {
            input.setCustomValidity(t('error.invalid_input'));
            input.reportValidity();
            return false;
        }
    }
    for (const fieldset of form.querySelectorAll<HTMLElement>('[data-bi-required]')) {
        const name = fieldset.dataset.biRequired!;
        if (!Object.keys(biValue(form, name)).length) {
            toast(t('language.required'), true);
            fieldset.querySelector<HTMLInputElement | HTMLTextAreaElement>('input,textarea')?.focus();
            return false;
        }
    }
    return true;
}
export function bindForm(id: string, callback: (form: HTMLFormElement) => Promise<void>): void { const form = document.getElementById(id) as HTMLFormElement | null; if (!form)
    return; form.noValidate = true; form.addEventListener('submit', async (event) => { event.preventDefault(); if (!validateForm(form))
    return; const buttons = [...form.querySelectorAll<HTMLButtonElement>('button[type=submit]')]; buttons.forEach(b => b.disabled = true); try {
    await callback(form);
    if (!document.querySelector('.save-state.dirty,.conflict-box'))
        state.dirty = false;
}
catch (error) {
    showError(error);
}
finally {
    buttons.forEach(b => b.disabled = false);
} }); }
export function confirmAction(message: string, title = t('action.confirm')): Promise<boolean> {
    const dialog = document.getElementById('confirm-dialog') as HTMLDialogElement;
    dialog.innerHTML = `<form method="dialog"><div class="dialog-icon">${icon('help')}</div><h2>${h(title)}</h2><p>${h(message)}</p><div class="form-actions"><button class="button secondary" value="cancel" autofocus>${h(t('action.cancel'))}</button><button class="button primary" value="confirm">${h(t('action.confirm'))}</button></div></form>`;
    return new Promise(resolve => { dialog.addEventListener('close', () => resolve(dialog.returnValue === 'confirm'), { once: true }); dialog.returnValue = ''; dialog.showModal(); });
}
export async function enhance(root: Element = document.getElementById('main')!): Promise<void> {
    if (!root)
        return;
    window.Prism?.highlightAllUnder(root);
    try {
        await window.MathJax?.startup?.promise;
        await window.MathJax?.typesetPromise?.([root]);
    }
    catch (error) {
        console.warn('Mathematical typesetting failed', error instanceof Error ? error.name : '');
    }
}
async function previewUpload(file: File): Promise<{accept: boolean; photo: boolean}> {
    const url = URL.createObjectURL(file);
    const dialog = document.createElement('dialog');
    dialog.className = 'upload-preview';
    dialog.innerHTML = `<form method="dialog"><h2>${h(t('file.preview'))}</h2><p>${h(file.name)} · ${h(number(file.size / 1024, 1))} ${h(t('file.kib'))}</p><img src="${h(url)}" alt="${h(t('file.preview'))}"><label class="checkbox"><input type="checkbox" name="photo"><span>${h(t('file.photo_option'))}</span></label><p class="field-help">${h(t('file.photo_help'))}</p><div class="form-actions"><button class="button secondary" value="cancel" autofocus>${h(t('action.cancel'))}</button><button class="button primary" value="upload">${h(t('action.upload'))}</button></div></form>`;
    document.body.append(dialog);
    return new Promise(resolve => {
        dialog.addEventListener('close', () => {
            const result = {accept: dialog.returnValue === 'upload', photo: !!dialog.querySelector<HTMLInputElement>('[name=photo]')?.checked};
            dialog.remove(); URL.revokeObjectURL(url); resolve(result);
        }, {once: true});
        dialog.showModal();
    });
}

export function bindUploads(onChanged: (file?: Attachment) => void | Promise<void>, root: ParentNode = document): void {
    type Quota = {used_bytes: number; reserved_bytes: number; limit_bytes: number; school_near_limit: boolean};
    if (root.querySelector('[data-upload-quota]')) {
        void api<Quota>('/files/quota').then(q => root.querySelectorAll('[data-upload-quota]').forEach(el => {
            el.textContent = t('file.quota_summary', {used: number((q.used_bytes + q.reserved_bytes) / 1048576, 1), limit: number(q.limit_bytes / 1048576, 1)}) + (q.school_near_limit ? ' · ' + t('file.school_near_limit') : '');
        })).catch(() => {}); // File validation remains authoritative when quota lookup fails.
    }
    root.querySelectorAll<HTMLInputElement>('input[data-upload-kind]').forEach(input => {
        const status = input.closest('.upload-widget')?.querySelector<HTMLElement>('[data-upload-status]');
        let pending: {file: File; key: string; photo: boolean} | null = null;
        const send = async (): Promise<void> => {
            if (!pending) return;
            input.disabled = true;
            if (status) status.textContent = t('file.uploading');
            try {
                const data = new FormData(); data.set('file', pending.file);
                const stored = await api<Attachment>(`/files?target_kind=${encodeURIComponent(input.dataset.uploadKind!)}&target_id=${encodeURIComponent(input.dataset.uploadTarget!)}&client_id=${encodeURIComponent(pending.key)}&photo=${pending.photo}`, 'POST', data);
                pending = null; input.value = '';
                if (status) status.textContent = t('file.uploaded');
                toast(t('file.uploaded')); await onChanged(stored);
            } catch (error) {
                showError(error);
                if (status) {
                    status.innerHTML = `<p>${h(t('file.retry_kept'))}</p><button type="button" class="button secondary" data-upload-retry>${h(t('action.retry'))}</button>`;
                    status.querySelector('button')?.addEventListener('click', () => {void send();}, {once: true});
                }
            } finally {input.disabled = false;}
        };
        input.addEventListener('change', async () => {
            const file = input.files?.[0]; if (!file) return;
            if (file.size > 8 * 1024 * 1024) {toast(t('error.file_too_large'), true); input.value = ''; return;}
            let photo = false;
            if (/\.(png|jpg|jpeg|webp)$/i.test(file.name)) {
                const selection = await previewUpload(file);
                if (!selection.accept) {input.value = ''; return;}
                photo = selection.photo;
            }
            pending = {file, key: crypto.randomUUID(), photo};
            await send();
        });
    });
    root.querySelectorAll<HTMLButtonElement>('[data-delete-file]').forEach(btn => btn.addEventListener('click', async () => {
        if (!await confirmAction(t('file.remove_confirm'))) return;
        try {await api(`/files/${btn.dataset.deleteFile}`, 'DELETE'); await onChanged();}
        catch (error) {showError(error);}
    }));
}
export function problemReading(problem: ProblemContent, files: Attachment[] = []): string { return `<div class="problem-reading">${problem.subtopic && plain(problem.subtopic) ? `<p class="muted">${content(problem.subtopic)}</p>` : ''}<div class="statement">${content(problem.statement, true)}</div>${plain(problem.examples) ? `<section class="problem-section"><h3>${h(t('problem.examples'))}</h3><pre class="examples">${content(problem.examples)}</pre></section>` : ''}${files.length ? `<section class="problem-section"><h3>${h(t('file.attachments'))}</h3>${attachmentList(files)}</section>` : ''}${plain(problem.hints) ? `<details class="reveal-section"><summary>${icon('help')}${h(t('problem.hints'))}</summary>${content(problem.hints, true)}</details>` : ''}${plain(problem.solution) ? `<details class="reveal-section"><summary>${icon('book')}${h(t('problem.solution'))}</summary>${content(problem.solution, true)}</details>` : ''}</div>`; }
