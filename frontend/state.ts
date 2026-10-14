import type { ClubSettings, Locale, Subject, User } from './types.js';
export const state: {
    user: User | null;
    canTrain: boolean;
    csrf: string;
    settings: ClubSettings;
    subjects: Subject[];
    locale: Locale;
    theme: 'light' | 'dark';
    localeTouched: boolean;
    serverDelta: number;
    route: string;
    dirty: boolean;
    streamStatus: 'connecting' | 'live' | 'polling' | 'offline';
} = {
    canTrain: false, user: null, csrf: '', settings: { name: {}, timezone: 'UTC' }, subjects: [],
    locale: localStorage.getItem('olympiados.locale') === 'en' ? 'en' : 'ru',
    theme: localStorage.getItem('olympiados.theme') === 'dark' ? 'dark' : 'light',
    localeTouched: false, serverDelta: 0, route: '/', dirty: false, streamStatus: 'connecting',
};
export const isStaff = (): boolean => state.user?.role === 'admin' || state.user?.role === 'teacher';
export const serverNow = (): number => Date.now() + state.serverDelta;
export function syncClock(serverTime: number): void { state.serverDelta = serverTime - Date.now(); }
