import { api, ApiError } from './api.js';
import { date, t } from './i18n.js';
import { state } from './state.js';
import { attachmentList, bindUploads, button, confirmAction, enhance, h, icon, rich, showError, toast, uploadControl } from './ui.js';
export function editorHTML(options) {
    const code = options.format === 'code';
    return `<section id="${h(options.id)}" class="work-editor"><header class="editor-heading"><h2>${h(options.title ?? t('work.title'))}</h2><span class="save-state" data-save-status>${icon('check')}${h(t('app.saved'))}</span></header><div data-recovery></div><div data-retry hidden></div><div data-conflict></div><div class="editor-tools"><label>${h(t('work.language'))} <select data-work-language ${!options.canEdit ? 'disabled' : ''}>${code ? `<option value="python" ${options.work.language === 'python' ? 'selected' : ''}>Python</option><option value="cpp" ${options.work.language === 'cpp' ? 'selected' : ''}>C++</option>` : `<option value="written">${h(t('problem.written'))}</option>`}</select></label>${button(t('work.preview'), 'work-preview', 'eye', 'ghost small')}${button(t('action.export_text'), 'work-export', 'download', 'ghost small')}</div><div class="editor-area ${code ? 'code-surface' : ''}">${code ? '<pre class="code-highlight" aria-hidden="true"><code></code></pre>' : ''}<textarea class="solution-input ${code ? 'code' : ''}" data-work-input aria-label="${h(options.title ?? t('work.title'))}" spellcheck="${code ? 'false' : 'true'}" maxlength="50000" ${!options.canEdit ? 'readonly' : ''} ${code ? 'wrap="off"' : ''}>${h(options.work.content)}</textarea></div><div class="work-preview" data-work-preview hidden><h3>${h(t('work.preview'))}</h3><div data-preview-content></div></div><div class="editor-bottom"><div class="attachments-area" data-attachments>${attachmentList(options.files, options.canEdit)}</div><div data-upload>${options.canEdit ? uploadControl(options.groupId ? 'group' : 'draft', options.groupId ?? options.itemId) : ''}</div><div class="editor-footer"><small>${h(t(code ? 'work.code_help' : 'work.editor_help'))}</small>${options.canSubmit ? button(t(options.groupId ? 'group.submit' : 'work.submit'), 'work-submit', 'check', 'primary') : ''}</div><div data-pending-submission aria-live="polite"></div><div data-submission-confirmation aria-live="polite"></div></div></section>`;
}
export class WorkEditor {
    options;
    root;
    input;
    language;
    revision;
    saved;
    dirty = false;
    stopped = false;
    timer = null;
    saving = null;
    inFlight = null;
    conflict = null;
    files;
    recoveryKey;
    pending = null;
    resolving = false;
    retryCount = 0;
    online = () => {
        this.retryCount = 0;
        if (this.dirty && !this.stopped && !this.conflict && this.options.canEdit)
            void this.save();
    };
    constructor(options) {
        this.options = options;
        this.root = document.getElementById(options.id);
        this.input = this.root.querySelector('[data-work-input]');
        this.language = this.root.querySelector('[data-work-language]');
        this.revision = options.work.revision;
        this.saved = { ...options.work };
        this.files = [...options.files];
        this.recoveryKey = `olympiados.work:${state.user.id}:${options.groupId ? 'group:' + options.groupId : 'task:' + options.itemId}`;
        this.input.addEventListener('input', () => this.changed());
        this.language.addEventListener('change', () => this.changed());
        this.input.addEventListener('scroll', () => {
            const mirror = this.root.querySelector('.code-highlight');
            if (mirror) {
                mirror.scrollTop = this.input.scrollTop;
                mirror.scrollLeft = this.input.scrollLeft;
            }
        });
        this.root.querySelector('[data-action=work-preview]')?.addEventListener('click', () => this.preview());
        this.root.querySelector('[data-action=work-export]')?.addEventListener('click', () => this.exportText());
        this.root.querySelector('[data-action=work-submit]')?.addEventListener('click', () => { void this.submit().catch(showError); });
        this.bindFiles();
        this.highlight();
        this.restoreRecovery();
        this.restorePending();
        window.addEventListener('online', this.online);
    }
    current() { return { content: this.input.value, language: this.language.value }; }
    setStatus(key, cls = '') {
        if (this.stopped)
            return;
        const status = this.root.querySelector('[data-save-status]');
        status.className = 'save-state ' + cls;
        status.innerHTML = icon(key === 'app.saved' ? 'check' : key === 'app.saving' ? 'clock' : 'help') + h(t(key));
    }
    remember() {
        const value = { ...this.current(), revision: this.revision, updated_at: Date.now() };
        try {
            sessionStorage.setItem(this.recoveryKey, JSON.stringify(value));
        }
        catch {
            this.setStatus('app.save_failed', 'error');
        }
    }
    forget() { sessionStorage.removeItem(this.recoveryKey); }
    markDirty(value) {
        this.dirty = value;
        if (!this.stopped)
            state.dirty = value;
    }
    changed() {
        this.retryCount = 0;
        this.markDirty(true);
        this.remember();
        this.highlight();
        this.setStatus('app.saving', 'dirty');
        if (this.timer)
            clearTimeout(this.timer);
        if (this.options.canEdit && !this.conflict)
            this.timer = setTimeout(() => { void this.save(); }, 900);
        if (!this.root.querySelector('[data-work-preview]').hidden)
            void this.renderPreview();
    }
    restoreRecovery() {
        let copy = null;
        try {
            const raw = sessionStorage.getItem(this.recoveryKey);
            if (raw)
                copy = JSON.parse(raw);
        }
        catch {
            return;
        }
        if (!copy || typeof copy.content !== 'string' || copy.content === this.saved.content && copy.language === this.saved.language)
            return;
        if (!['written', 'python', 'cpp'].includes(copy.language))
            return;
        this.input.value = copy.content;
        this.language.value = copy.language;
        this.markDirty(true);
        this.highlight();
        if (copy.revision !== this.revision) {
            this.showConflict(this.saved);
            return;
        }
        const note = this.root.querySelector('[data-recovery]');
        note.innerHTML = `<div class="notice warning" style="margin:15px"><div><p>${h(t('work.recovery'))}</p><div class="notice-actions">${button(t('work.discard_recovery'), 'discard-recovery', '', 'secondary small')}</div></div></div>`;
        note.querySelector('button')?.addEventListener('click', () => { this.input.value = this.saved.content; this.language.value = this.saved.language; this.markDirty(false); this.forget(); note.innerHTML = ''; this.highlight(); this.setStatus('app.saved'); });
        if (this.options.canEdit)
            this.timer = setTimeout(() => { void this.save(); }, 1200);
        else
            this.setStatus('work.deadline_save', 'error');
    }
    highlight() {
        if (this.options.format !== 'code')
            return;
        const mirror = this.root.querySelector('.code-highlight code');
        if (!mirror)
            return;
        mirror.className = 'language-' + this.language.value;
        mirror.textContent = this.input.value + '\n';
        if (window.Prism) {
            window.Prism.highlightElement(mirror);
            this.root.querySelector('.editor-area')?.classList.add('highlight-enabled');
        }
    }
    async renderPreview() { const target = this.root.querySelector('[data-preview-content]'); target.innerHTML = this.options.format === 'code' ? `<pre><code class="language-${h(this.language.value)}">${h(this.input.value)}</code></pre>` : rich(this.input.value); await enhance(target); }
    async preview() {
        const target = this.root.querySelector('[data-work-preview]');
        target.hidden = !target.hidden;
        if (!target.hidden)
            await this.renderPreview();
    }
    exportText() { const blob = new Blob([this.input.value], { type: 'text/plain;charset=utf-8' }); const url = URL.createObjectURL(blob); const link = document.createElement('a'); link.href = url; link.download = 'olympiados-solution.' + (this.language.value === 'python' ? 'py' : this.language.value === 'cpp' ? 'cpp' : 'txt'); link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000); }
    async save() {
        if (this.stopped || !this.options.canEdit)
            return !this.dirty;
        if (this.conflict)
            return false;
        if (this.saving) {
            await this.saving;
            return this.dirty && !this.conflict ? this.save() : !this.dirty;
        }
        if (!this.dirty)
            return true;
        if (this.timer)
            clearTimeout(this.timer);
        const sent = this.current();
        const expected = this.revision;
        this.inFlight = sent;
        this.setStatus('app.saving', 'dirty');
        this.saving = (async () => {
            try {
                const saved = await api(this.options.groupId ? `/groups/${this.options.groupId}/document` : `/drafts/${this.options.itemId}`, 'PUT', { ...sent, revision: expected });
                this.revision = saved.revision;
                this.saved = { ...saved };
                this.retryCount = 0;
                if (!this.stopped)
                    this.root.querySelector('[data-retry]').hidden = true;
                const current = this.current();
                if (current.content === sent.content && current.language === sent.language) {
                    this.markDirty(false);
                    this.forget();
                    this.setStatus('app.saved');
                    if (!this.stopped)
                        this.root.querySelector('[data-recovery]').innerHTML = '';
                }
                else {
                    this.remember();
                    if (!this.stopped)
                        this.timer = setTimeout(() => { void this.save(); }, 500);
                }
                return true;
            }
            catch (error) {
                this.remember();
                if (error instanceof ApiError && error.code === 'conflict' && typeof error.data.revision === 'number' && typeof error.data.content === 'string')
                    this.showConflict(error.data);
                else {
                    this.setStatus('app.save_failed', 'error');
                    if (error instanceof ApiError && error.code === 'deadline_closed')
                        this.close();
                    else if (!this.stopped) {
                        if (this.retryCount === 0)
                            showError(error);
                        const notice = this.root.querySelector('[data-retry]');
                        notice.hidden = false;
                        notice.innerHTML = `<div class="notice warning" style="margin:15px"><div><p>${h(t('work.retry_note'))}</p>${button(t('action.retry'), 'retry-save', '', 'secondary small')}</div></div>`;
                        notice.querySelector('button')?.addEventListener('click', () => { this.retryCount = 0; void this.save(); });
                        if (error instanceof ApiError && error.code === 'network' && this.retryCount < 3) {
                            const delay = [2000, 5000, 10000][this.retryCount++];
                            this.timer = setTimeout(() => { void this.save(); }, delay);
                        }
                    }
                }
                return false;
            }
            finally {
                this.inFlight = null;
                this.saving = null;
            }
        })();
        return this.saving;
    }
    receive(work) {
        if (work.revision <= this.revision || this.stopped)
            return;
        if (this.inFlight && this.inFlight.content === work.content && this.inFlight.language === work.language)
            return;
        const current = this.current();
        if (this.dirty && (current.content !== work.content || current.language !== work.language)) {
            this.showConflict(work);
            return;
        }
        this.revision = work.revision;
        this.saved = { ...work };
        this.input.value = work.content;
        this.language.value = work.language;
        this.markDirty(false);
        this.forget();
        this.highlight();
        this.setStatus('app.saved');
    }
    showConflict(work) {
        if (this.stopped)
            return;
        this.conflict = work;
        if (this.timer)
            clearTimeout(this.timer);
        this.markDirty(true);
        this.remember();
        this.setStatus('app.save_failed', 'error');
        const target = this.root.querySelector('[data-conflict]');
        target.innerHTML = `<div class="conflict-box"><h3>${h(t('work.conflict'))}</h3><details open><summary>${h(t('work.server_copy'))} · ${h(t('group.revision', { number: work.revision }))}</summary><pre>${h(work.content)}</pre></details><p class="small">${h(t('work.local_copy'))}: ${h(t('work.compare_note'))}</p><div class="notice-actions">${button(t('work.use_server'), 'use-server', '', 'secondary small')}${this.options.canEdit ? button(t('work.keep_mine'), 'keep-mine', '', 'secondary small') : ''}${button(t('action.export_text'), 'export-conflict', 'download', 'secondary small')}</div></div>`;
        target.querySelector('[data-action=use-server]')?.addEventListener('click', () => { const latest = this.conflict; this.conflict = null; target.innerHTML = ''; this.revision = latest.revision; this.saved = { ...latest }; this.input.value = latest.content; this.language.value = latest.language; this.markDirty(false); this.forget(); this.highlight(); this.setStatus('app.saved'); });
        target.querySelector('[data-action=keep-mine]')?.addEventListener('click', () => {
            void (async () => {
                if (!await confirmAction(t('work.keep_mine_confirm')))
                    return;
                this.revision = this.conflict.revision;
                this.conflict = null;
                target.innerHTML = '';
                this.markDirty(true);
                await this.save();
            })();
        });
        target.querySelector('[data-action=export-conflict]')?.addEventListener('click', () => this.exportText());
    }
    setText(content, language) { this.input.value = content; this.language.value = language; this.changed(); this.input.focus(); }
    bindFiles() { bindUploads(async () => { await this.refreshFiles(); }, this.root); }
    updateFiles(files) {
        this.files = [...files];
        if (this.stopped)
            return;
        const target = this.root.querySelector('[data-attachments]');
        target.innerHTML = attachmentList(this.files, this.options.canEdit);
        bindUploads(async () => { await this.refreshFiles(); }, target);
    }
    async refreshFiles() {
        if (this.options.groupId) {
            const group = await api('/groups/' + this.options.groupId);
            this.files = group.files;
            this.receive(group.document);
        }
        else {
            const draft = await api('/drafts/' + this.options.itemId);
            this.files = draft.files ?? [];
        }
        if (this.stopped)
            return;
        const target = this.root.querySelector('[data-attachments]');
        target.innerHTML = attachmentList(this.files, this.options.canEdit);
        bindUploads(async () => { await this.refreshFiles(); }, target);
    }
    pendingKey() { return this.recoveryKey + ':submission'; }
    restorePending() {
        try {
            const raw = sessionStorage.getItem(this.pendingKey());
            if (!raw)
                return;
            const value = JSON.parse(raw);
            const body = value.body;
            if (value.user_id !== state.user?.id || !body || body.activity_item_id !== this.options.itemId || body.group_id !== (this.options.groupId ?? null) || typeof body.client_id !== 'string' || !/^[0-9a-f-]{36}$/i.test(body.client_id) || typeof body.content !== 'string' || body.content.length > 50000 || !Array.isArray(body.file_ids) || body.file_ids.length > 12 || !['written', 'python', 'cpp'].includes(body.language)) {
                sessionStorage.removeItem(this.pendingKey());
                return;
            }
            this.pending = body;
            this.pendingNotice();
            void this.reconcilePending().catch(showError);
        }
        catch {
            this.setStatus('app.save_failed', 'error');
        }
    }
    pendingNotice() {
        if (this.stopped)
            return;
        const target = this.root.querySelector('[data-pending-submission]');
        target.innerHTML = this.pending ? `<div class="notice warning"><div><p>${h(t('work.pending_receipt'))}</p><div class="button-row">${button(t('work.check_receipt'), 'receipt-check', '', 'secondary small')}${button(t('work.retry_exact'), 'receipt-retry', '', 'secondary small')}${button(t('work.discard_pending'), 'receipt-discard', '', 'ghost small')}</div></div></div>` : '';
        target.querySelector('[data-action=receipt-check]')?.addEventListener('click', () => { void this.reconcilePending().catch(showError); });
        target.querySelector('[data-action=receipt-retry]')?.addEventListener('click', () => {
            void (async () => {
                if (await this.reconcilePending() || !this.pending)
                    return;
                if (!await confirmAction(t('work.retry_exact_confirm')))
                    return;
                await this.sendPending();
            })().catch(showError);
        });
        target.querySelector('[data-action=receipt-discard]')?.addEventListener('click', () => {
            void (async () => {
                if (await this.reconcilePending() || !this.pending)
                    return;
                if (await confirmAction(t('work.discard_pending_confirm')))
                    this.clearPending();
            })().catch(showError);
        });
    }
    clearPending() {
        this.pending = null;
        sessionStorage.removeItem(this.pendingKey());
        this.pendingNotice();
    }
    showReceipt(receipt) {
        if (this.stopped)
            return;
        this.root.querySelector('[data-submission-confirmation]').innerHTML = `<div class="notice success" style="margin-top:18px;margin-bottom:0">${icon('check')}<div><a href="#/submissions/${h(receipt.id)}"><strong>${h(t('work.confirmation', { id: receipt.id.slice(0, 8) }))}</strong></a><br><small>${h(date(receipt.created_at))} · ${h(t('work.attempt', { number: receipt.attempt }))}</small></div></div>`;
    }
    async reconcilePending() {
        if (!this.pending || this.resolving)
            return false;
        this.resolving = true;
        try {
            const receipt = await api('/submissions/by-client-id/' + encodeURIComponent(this.pending.client_id));
            this.showReceipt(receipt);
            this.clearPending();
            return true;
        }
        catch (error) {
            if (error instanceof ApiError && error.status === 404)
                return false;
            throw error; // An outage is never proof that an attempt was not accepted.
        }
        finally {
            this.resolving = false;
        }
    }
    async sendPending() {
        if (!this.pending || this.resolving)
            return;
        this.resolving = true;
        try {
            const result = await api('/submissions', 'POST', this.pending);
            this.showReceipt(result);
            this.clearPending();
            toast(t('work.submitted'));
            await this.options.onSubmitted?.(result);
        }
        finally {
            this.resolving = false;
        }
    }
    async submit() {
        if (!this.options.canSubmit)
            return;
        const submit = this.root.querySelector('[data-action=work-submit]');
        submit.disabled = true;
        try {
            if (!await this.save() || this.dirty || this.conflict)
                return;
            if (!this.input.value.trim() && !this.files.length) {
                toast(t('error.empty_submission'), true);
                return;
            }
            if (!await confirmAction(t('work.submit_confirm')))
                return;
            if (this.pending) {
                await this.reconcilePending();
                if (this.pending)
                    this.pendingNotice();
                return; // Resolve the old intent before allocating another attempt identity.
            }
            const candidate = { activity_item_id: this.options.itemId, content: this.options.groupId ? '' : this.input.value, language: this.language.value, group_id: this.options.groupId ?? null, group_revision: this.options.groupId ? this.revision : null, file_ids: this.files.map(file => file.id), client_id: crypto.randomUUID() };
            // Persist the exact original request before sending any bytes. If storage is
            // unavailable, fail visibly instead of silently losing retry identity.
            sessionStorage.setItem(this.pendingKey(), JSON.stringify({ user_id: state.user.id, body: candidate }));
            this.pending = candidate;
            this.pendingNotice();
            await this.sendPending();
        }
        finally {
            if (!this.stopped)
                submit.disabled = !this.options.canSubmit;
        }
    }
    close() {
        this.options.canEdit = false;
        this.options.canSubmit = false;
        if (this.timer)
            clearTimeout(this.timer);
        if (this.stopped)
            return;
        this.root.querySelector('[data-action=work-submit]')?.setAttribute('disabled', '');
        this.root.querySelector('[data-retry]').hidden = true;
        this.root.querySelectorAll('input[type=file]').forEach(input => input.disabled = true);
        this.root.querySelector('[data-recovery]').innerHTML = `<div class="notice warning" style="margin:15px">${icon('clock')}<p>${h(t('work.deadline_save'))}</p></div>`;
        if (this.dirty)
            this.remember();
    }
    dispose() {
        if (this.dirty)
            this.remember();
        this.stopped = true;
        window.removeEventListener('online', this.online);
        if (this.timer)
            clearTimeout(this.timer);
    }
}
//# sourceMappingURL=work-editor.js.map