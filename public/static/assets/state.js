export const state = {
    canTrain: false, user: null, csrf: '', settings: { name: {}, timezone: 'UTC' }, subjects: [],
    locale: localStorage.getItem('olympiados.locale') === 'en' ? 'en' : 'ru',
    theme: localStorage.getItem('olympiados.theme') === 'dark' ? 'dark' : 'light',
    localeTouched: false, serverDelta: 0, route: '/', dirty: false, streamStatus: 'connecting',
};
export const isStaff = () => state.user?.role === 'admin' || state.user?.role === 'teacher';
export const serverNow = () => Date.now() + state.serverDelta;
export function syncClock(serverTime) { state.serverDelta = serverTime - Date.now(); }
//# sourceMappingURL=state.js.map