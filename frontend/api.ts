import { state, syncClock } from './state.js';
import { t } from './i18n.js';
export class ApiError extends Error {
    constructor(public code: string, message: string, public status: number, public data: Record<string, unknown> = {}) { super(message); this.name = 'ApiError'; }
}
export async function api<T>(path: string, method = 'GET', body?: unknown): Promise<T> {
    const form = body instanceof FormData;
    const headers: Record<string, string> = { 'X-Locale': state.locale };
    if (method !== 'GET')
        headers['X-CSRF-Token'] = state.csrf;
    if (body !== undefined && !form)
        headers['Content-Type'] = 'application/json';
    let response: Response;
    try {
        response = await fetch('/api' + path, { method, headers, credentials: 'same-origin', body: body === undefined ? undefined : form ? body : JSON.stringify(body) });
    }
    catch {
        throw new ApiError('network', t('error.network'), 0);
    }
    let data: unknown;
    try {
        data = await response.json();
    }
    catch {
        throw new ApiError('unexpected', t('error.unexpected'), response.status);
    }
    if (!response.ok) {
        const error = (data as {
            error?: {
                code?: string;
                message?: string;
                data?: Record<string, unknown>;
            };
        })?.error;
        if (response.status === 401 && error?.code === 'unauthenticated' && state.user)
            window.dispatchEvent(new CustomEvent('auth-expired'));
        throw new ApiError(error?.code ?? 'unexpected', error?.message ?? t('error.unexpected'), response.status, error?.data);
    }
    if (typeof data === 'object' && data !== null && 'server_now' in data && typeof data.server_now === 'number')
        syncClock(data.server_now);
    return data as T;
}
