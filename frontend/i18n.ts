import { state } from './state.js';
import type { Bi, Locale } from './types.js';
type Message = string | Record<string, string>;
const dictionaries: Partial<Record<Locale, Record<string, Message>>> = {};
export async function initializeI18n(): Promise<void> {
    await Promise.all((['ru', 'en'] as const).map(async (locale) => {
        const response = await fetch(`/locales/${locale}.json`, { credentials: 'same-origin' });
        if (!response.ok)
            throw new Error('Catalog unavailable');
        dictionaries[locale] = await response.json() as Record<string, Message>;
    }));
    applyLocale(state.locale);
}
export function applyLocale(locale: Locale): void {
    state.locale = locale;
    localStorage.setItem('olympiados.locale', locale);
    document.documentElement.lang = locale;
}
export function t(key: string, params: Record<string, string | number> = {}): string {
    let message = dictionaries[state.locale]?.[key];
    if (message === undefined) {
        console.error(`Missing translation: ${key}`);
        return key;
    }
    if (typeof message !== 'string')
        message = message[new Intl.PluralRules(state.locale).select(Number(params.count ?? 0))] ?? message.other ?? '';
    return message.replace(/\{(\w+)\}/g, (match, name: string) => name in params ? String(params[name]) : match);
}
export function plain(value: Bi | undefined | null): string { return value?.[state.locale] || value?.[state.locale === 'ru' ? 'en' : 'ru'] || ''; }
export function number(value: number, digits = 2): string { return new Intl.NumberFormat(state.locale, { maximumFractionDigits: digits }).format(value); }
export function date(value: number | null | undefined, withTime = true): string {
    if (value === null || value === undefined)
        return t('common.no_deadline');
    return new Intl.DateTimeFormat(state.locale === 'ru' ? 'ru-RU' : 'en-GB', { dateStyle: 'medium', ...(withTime ? { timeStyle: 'short' as const } : {}), timeZone: state.settings.timezone }).format(value);
}
export function dayMonth(value: number): {
    day: string;
    month: string;
} {
    return {
        day: new Intl.DateTimeFormat(state.locale, { day: '2-digit', timeZone: state.settings.timezone }).format(value),
        month: new Intl.DateTimeFormat(state.locale, { month: 'short', timeZone: state.settings.timezone }).format(value),
    };
}
function zonedParts(epoch: number): Record<string, number> {
    const result: Record<string, number> = {};
    new Intl.DateTimeFormat('en-CA', { timeZone: state.settings.timezone, year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hourCycle: 'h23' }).formatToParts(epoch).forEach(p => { if (p.type !== 'literal')
        result[p.type] = Number(p.value); });
    return result;
}
export function dateInput(epoch: number | null): string {
    if (epoch === null)
        return '';
    const p = zonedParts(epoch);
    const pad = (n: number | undefined) => String(n ?? 0).padStart(2, '0');
    return `${p.year}-${pad(p.month)}-${pad(p.day)}T${pad(p.hour)}:${pad(p.minute)}`;
}
export function parseDateInput(value: string): number | null {
    if (!value)
        return null;
    const match = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})$/.exec(value);
    if (!match)
        throw new Error(t('error.invalid_time'));
    const desired = Date.UTC(Number(match[1]), Number(match[2]) - 1, Number(match[3]), Number(match[4]), Number(match[5]));
    let epoch = desired;
    for (let i = 0; i < 3; i++) {
        const p = zonedParts(epoch);
        epoch += desired - Date.UTC(p.year!, p.month! - 1, p.day!, p.hour!, p.minute!);
    }
    if (dateInput(epoch) !== value)
        throw new Error(t('error.invalid_time'));
    return epoch;
}
