import { ApiError } from './api.js';
import { state } from './state.js';
import { confirmAction, empty, enhance, h, linkButton, showError } from './ui.js';
import { t } from './i18n.js';
import type { ChangeEvent } from './types.js';
let renderer: (() => Promise<void>) | null = null;
let cleanup: (() => void)[] = [];
let remote: ((event?: ChangeEvent) => Promise<void> | void) | null = null;
let rendering = false;
let queuedRender = false;
let generation = 0;
export function setRenderer(callback: () => Promise<void>): void { renderer = callback; }
export function setCleanup(callback: () => void): void { cleanup.push(callback); }
export function setRemoteHandler(callback: (event?: ChangeEvent) => Promise<void> | void): void { remote = callback; }
export function currentPath(): string { return location.hash.slice(1) || '/'; }
export function routeURL(): URL { return new URL(currentPath(), 'http://olympiados.local'); }
export function setView(html: string): void { const main = document.getElementById('main'); if (!main)
    return; window.MathJax?.typesetClear?.([main]); main.innerHTML = html; }
export function disposePage(): void { cleanup.forEach(fn => fn()); cleanup = []; remote = null; }
export async function navigate(path: string, force = false): Promise<void> {
    if (state.dirty && !force && !await confirmAction(t('work.unsaved_leave')))
        return;
    state.dirty = false;
    if (currentPath() === path)
        await refresh();
    else
        location.hash = path;
}
export async function refresh(): Promise<void> {
    if (!renderer)
        return;
    if (rendering) {
        queuedRender = true;
        return;
    }
    rendering = true;
    const ticket = ++generation;
    disposePage();
    try {
        await renderer();
        if (ticket === generation)
            await enhance();
    }
    catch (error) {
        showError(error);
        setView(empty(t(error instanceof ApiError && error.status === 404 ? 'error.not_found' : 'error.cannot_load'), error instanceof Error ? error.message : t('error.unexpected'), linkButton(t('nav.dashboard'), '/', 'home')));
    }
    finally {
        rendering = false;
        if (queuedRender) {
            queuedRender = false;
            await refresh();
        }
    }
}
export async function handleRemote(event?: ChangeEvent): Promise<void> {
    if (rendering)
        return;
    if (remote) {
        try {
            await remote(event);
        }
        catch (error) {
            console.warn('Remote refresh failed', error instanceof Error ? error.name : '');
        }
        return;
    }
    const editing = document.activeElement instanceof HTMLInputElement || document.activeElement instanceof HTMLTextAreaElement || document.activeElement instanceof HTMLSelectElement;
    if (!state.dirty && !editing)
        await refresh();
}
export interface FormSnapshot {
    name: string;
    index: number;
    value: string;
    checked?: boolean;
}
export function captureForms(): FormSnapshot[] {
    const counts: Record<string, number> = {};
    const result: FormSnapshot[] = [];
    document.querySelectorAll<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>('#main input,#main textarea,#main select').forEach(el => {
        if (el.closest('.work-editor') || (el instanceof HTMLInputElement && el.type === 'file') || !el.name)
            return;
        const index = counts[el.name] ?? 0;
        counts[el.name] = index + 1;
        result.push({ name: el.name, index, value: el.value, checked: el instanceof HTMLInputElement ? el.checked : undefined });
    });
    return result;
}
export function restoreForms(snapshots: FormSnapshot[]): void {
    for (const snapshot of snapshots) {
        const matches = [...document.querySelectorAll<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>('#main input,#main textarea,#main select')].filter(el => el.name === snapshot.name && !el.closest('.work-editor'));
        const el = matches[snapshot.index];
        if (!el)
            continue;
        el.value = snapshot.value;
        if (el instanceof HTMLInputElement && snapshot.checked !== undefined)
            el.checked = snapshot.checked;
    }
}
