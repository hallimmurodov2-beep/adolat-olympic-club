import { trainingPage, cycleForm, cyclePage, planPage, circlesPage, circleForm, circlePage, moderationPage, subjectParticipationPage } from './pages-training.js';
import { informaticsPage, leaderboardPage, cfAccountPage, cfApprovalsPage } from './pages-codeforces.js';
import { api } from './api.js';
import { applyLocale, date, initializeI18n, t } from './i18n.js';
import { isStaff, state, syncClock } from './state.js';
import { captureForms, currentPath, disposePage, handleRemote, navigate, refresh, restoreForms, routeURL, setRenderer, setView } from './router.js';
import { bindForm, confirmAction, content, empty, field, formActions, formValue, h, icon, linkButton, showError, toast } from './ui.js';
import { dashboardPage, guidePage } from './pages-home.js';
import { classroomForm, classroomPage, classroomsPage, resourceForm } from './pages-classrooms.js';
import { libraryPage, problemForm, problemPage, setsPage } from './pages-library.js';
import { activitiesPage, activityForm, activityDraftForm, activityPage, presentationPage } from './pages-activities.js';
import { groupForm, groupPage, groupsPage } from './pages-groups.js';
import { submissionPage, submissionsPage } from './pages-review.js';
import { adminPage, enrollmentPage, invitationForm, invitationsPage, notificationsPage, profilePage, progressPage } from './pages-operations.js';
let events = null;
let lastHash = '/';
let polling = null;
let connectionMode = '';
let reconnectTimer = null;
let reconnectAttempt = 0;
let eventCursor = '';
let backgroundPollActive = false;
let remoteTimer = null;
const brand = (large = false) => `<a class="brand" href="#/"><img class="school-logo" src="/static/brand/${large ? 'logo-login.png' : 'logo-header.png'}" ${large ? '' : 'srcset="/static/brand/logo-header-2x.png 2x"'} alt="" width="${large ? 181 : 64}" height="${large ? 148 : 52}"><span>Adolat<br><span>Olympic Club</span></span></a>`;
function localeControl() { return `<div class="locale-control" role="group" aria-label="${h(t('language.switch'))}"><button type="button" data-locale="ru" aria-pressed="${state.locale === 'ru'}" lang="ru">РУ</button><button type="button" data-locale="en" aria-pressed="${state.locale === 'en'}" lang="en">EN</button></div>`; }
function themeButton() { return `<button class="icon-button" type="button" data-theme-toggle aria-label="${h(t(state.theme === 'dark' ? 'profile.light' : 'profile.dark'))}">${icon(state.theme === 'dark' ? 'sun' : 'moon')}</button>`; }
function applyTheme() { document.documentElement.dataset.theme = state.theme; localStorage.setItem('olympiados.theme', state.theme); document.querySelectorAll('[data-theme-toggle]').forEach(el => { el.innerHTML = icon(state.theme === 'dark' ? 'sun' : 'moon'); el.setAttribute('aria-label', t(state.theme === 'dark' ? 'profile.light' : 'profile.dark')); }); }
function shell(force = false) {
    if (!force && document.getElementById('main')?.dataset.shell === 'authenticated')
        return;
    const path = routeURL().pathname;
    const entries = [['/', 'nav.dashboard', 'home'], ['/classrooms', 'nav.classrooms', 'classroom'], ['/problems', 'nav.problems', 'book'], ['/assignments', 'nav.assignments', 'assignment'], ['/sessions', 'nav.sessions', 'live'], ['/groups', 'nav.groups', 'group'], ['/competitions', 'nav.competitions', 'trophy'], ['/submissions', 'nav.submissions', 'review'], ['/progress', 'nav.progress', 'chart']];
    if (state.canTrain || state.user?.role === 'admin')
        entries.splice(1, 0, ['/training', 'nav.training', 'assignment'], ['/circles', 'nav.circles', 'group'], ['/informatics', 'nav.informatics', 'code']);
    if (isStaff())
        entries.push(['/sets', 'set.title', 'book'], ['/invitations', 'admin.invitations', 'user']);
    if (state.user?.role === 'admin')
        entries.push(['/admin', 'nav.admin', 'settings'], ['/moderation', 'nav.moderation', 'lock'], ['/cf-approvals', 'nav.cf_approvals', 'check'], ['/subject-participation', 'nav.subjects', 'user']);
    const user = state.user;
    document.getElementById('app').innerHTML = `<a class="skip-link" href="#main">${h(t('nav.skip'))}</a><div class="nav-backdrop" data-menu-dismiss></div><aside class="sidebar"><div class="sidebar-brand">${brand()}<button type="button" class="icon-button mobile-menu" data-menu-close aria-label="${h(t('nav.close'))}">${icon('close')}</button></div><p class="workspace-label">${content(state.settings.name) || h(t('app.workspace'))}</p><nav class="nav" aria-label="${h(t('nav.workspace'))}"><p class="nav-section-title">${h(t('nav.learn'))}</p>${entries.map(([url, key, symbol], i) => `${i === 7 ? `<p class="nav-section-title">${h(t('nav.workspace'))}</p>` : ''}<a href="#${url}" class="nav-link ${path === url || url !== '/' && path.startsWith(url + '/') ? 'active' : ''}">${icon(symbol)}<span>${h(t(key))}</span></a>`).join('')}<p class="nav-section-title">${h(t('nav.manage'))}</p><a class="nav-link" href="#/guide">${icon('help')}${h(t('nav.guide'))}</a></nav><footer class="sidebar-footer"><a href="#/profile" class="profile-link"><span class="avatar">${h(user.display_name.split(' ').map(v => v[0]).slice(0, 2).join(''))}</span><span><strong>${h(user.display_name)}</strong><small>${h(t('role.' + user.role))}</small></span></a><div class="footer-tools">${localeControl()}${themeButton()}<button type="button" class="icon-button" data-logout aria-label="${h(t('auth.logout'))}">${icon('logout')}</button></div></footer></aside><div class="main-shell"><header class="topbar"><div class="topbar-start"><button type="button" class="icon-button mobile-menu" data-menu-toggle aria-expanded="false" aria-label="${h(t('nav.open'))}">${icon('menu')}</button><span class="topbar-title">${h(t('app.workspace'))}</span><span id="connection-status" class="connection"></span></div><div class="topbar-tools"><form id="global-search" class="topbar-search">${icon('search')}<input name="q" type="search" aria-label="${h(t('action.search'))}" placeholder="${h(t('common.search_placeholder'))}"></form><span class="topbar-date">${h(date(Date.now(), false))}</span><a class="icon-button notification-button" href="#/notifications" aria-label="${h(t('nav.notifications'))}">${icon('bell')}<span id="notification-dot" class="notification-dot" hidden></span></a></div></header><main id="main" class="content" data-shell="authenticated" tabindex="-1"></main></div>`;
    bindGlobalControls();
    bindForm('global-search', form => navigate('/problems?q=' + encodeURIComponent(formValue(form, 'q'))));
    connection(state.streamStatus);
}
function connection(status) {
    state.streamStatus = status;
    const el = document.getElementById('connection-status');
    if (el) {
        el.dataset.status = status;
        el.textContent = t('app.' + (status === 'offline' ? 'offline' : status));
    }
}
function desiredConnection() {
    if (!state.user || document.hidden)
        return 'paused';
    return /^\/(activities|groups|submissions|present)\/[^/]+/.test(routeURL().pathname) ? 'stream' : 'foreground';
}
function clearConnection() {
    events?.close();
    events = null;
    if (polling)
        clearInterval(polling);
    if (remoteTimer)
        clearTimeout(remoteTimer);
    if (reconnectTimer)
        clearTimeout(reconnectTimer);
    polling = null;
    remoteTimer = null;
    reconnectTimer = null;
}
function connect(force = false) {
    const mode = desiredConnection();
    if (!force && connectionMode === mode)
        return;
    clearConnection();
    connectionMode = mode;
    if (mode === 'paused')
        return;
    if (mode === 'foreground') {
        connection(navigator.onLine ? 'polling' : 'offline');
        polling = setInterval(() => {
            if (state.user && !document.hidden && !backgroundPollActive) {
                backgroundPollActive = true;
                void handleRemote().finally(() => { backgroundPollActive = false; });
            }
        }, 30000);
        return;
    }
    events = new EventSource('/api/events' + (eventCursor ? '?cursor=' + encodeURIComponent(eventCursor) : ''));
    connection('connecting');
    const alive = (event) => {
        if (event.lastEventId)
            eventCursor = event.lastEventId;
        try {
            syncClock(JSON.parse(String(event.data)).server_now);
        }
        catch { }
        reconnectAttempt = 0;
        connection('live');
    };
    events.addEventListener('ready', event => { alive(event); void handleRemote(); });
    events.addEventListener('heartbeat', event => alive(event));
    events.addEventListener('change', event => { alive(event); const change = JSON.parse(String(event.data)); if (remoteTimer)
        clearTimeout(remoteTimer); remoteTimer = setTimeout(() => { void handleRemote(change); }, 180); });
    events.addEventListener('reset', event => { eventCursor = event.lastEventId; void handleRemote(); });
    events.addEventListener('expired', () => expired());
    const retry = () => {
        events?.close();
        events = null;
        connection(navigator.onLine ? 'polling' : 'offline');
        if (reconnectTimer)
            clearTimeout(reconnectTimer);
        const delay = Math.min(30000, 2000 * 2 ** Math.min(reconnectAttempt++, 4)) + Math.random() * 1000;
        reconnectTimer = setTimeout(() => { if (!document.hidden && state.user)
            connect(true); }, delay);
    };
    events.addEventListener('unavailable', retry);
    events.onerror = retry;
    polling = setInterval(() => {
        if (state.user && !document.hidden && state.streamStatus !== 'live' && !backgroundPollActive) {
            backgroundPollActive = true;
            void handleRemote().finally(() => { backgroundPollActive = false; });
        }
    }, 15000);
}
function stopConnection() { clearConnection(); connectionMode = ''; eventCursor = ''; }
function expired() {
    if (!state.user)
        return;
    stopConnection();
    state.user = null;
    state.csrf = '';
    toast(t('auth.session_expired'), true);
    void refresh();
}
// Recovery belongs to one authenticated student, even after an expired session.
// Keep this student's unresolved receipt; never leave another account's draft in a shared tab.
function clearOtherRecovery(userId) {
    try {
        const prefix = 'olympiados.work:';
        Array.from({ length: sessionStorage.length }, (_, i) => sessionStorage.key(i))
            .filter((key) => !!key && key.startsWith(prefix) && !key.startsWith(prefix + userId + ':'))
            .forEach(key => sessionStorage.removeItem(key));
    }
    catch { /* A storage-disabled browser still authenticates; the editor reports recovery limits. */ }
}
async function acceptAuth(auth) { clearOtherRecovery(auth.user.id); state.user = auth.user; state.csrf = auth.csrf; state.settings = auth.settings; syncClock(auth.server_now); applyLocale(auth.user.locale); state.subjects = await api('/subjects'); state.canTrain = (await api('/subjects/mine')).can_train; state.dirty = false; await navigate(routeURL().pathname.startsWith('/enroll/') ? currentPath() : '/', true); await refresh(); connect(); }
async function authPage() {
    const token = routeURL().pathname.startsWith('/register/') ? routeURL().pathname.slice('/register/'.length) : null;
    let preview = null;
    let inviteError = '';
    if (token) {
        try {
            preview = await api('/auth/invitation', 'POST', { token });
        }
        catch (error) {
            inviteError = error instanceof Error ? error.message : t('error.invalid_invitation');
        }
    }
    document.getElementById('app').innerHTML = `<main id="main" class="auth-layout"><section class="auth-story">${brand()}<div class="auth-story-content"><p class="eyebrow">${h(t('auth.eyebrow'))}</p><h1>${h(t('auth.welcome'))}</h1><p>${h(t('auth.description'))}</p><div class="auth-subjects"><div>${icon('math')}${h(t('auth.math'))}</div><div>${icon('atom')}${h(t('auth.physics'))}</div><div>${icon('code')}${h(t('auth.code'))}</div></div></div><footer>${h(t('app.no_ai'))}</footer></section><section class="auth-form-area"><div class="auth-top-tools">${localeControl()}${themeButton()}</div><div class="auth-card">${brand(true)}<h2>${h(t(token ? 'auth.register' : 'auth.signin'))}</h2><p>${h(t(token ? 'auth.register_note' : 'auth.signin_note'))}</p>${inviteError ? `<div class="notice warning">${h(inviteError)}</div>${linkButton(t('auth.back'), '/')}` : `<form id="auth-form" novalidate>${preview ? `<p class="notice">${h(preview.email)} · ${h(t('role.' + preview.role))}<br>${content(preview.classroom_name)}</p>${field(t('auth.name'), 'display_name', '', 'text', 'required minlength="2" maxlength="100" autocomplete="name"')}` : field(t('auth.email'), 'email', '', 'email', 'required maxlength="254" autocomplete="username"')}${field(t('auth.password'), 'password', '', 'password', `required ${preview ? 'minlength="12"' : ''} maxlength="256" autocomplete="${preview ? 'new-password' : 'current-password'}"`, preview ? t('auth.password_help') : '')}<button type="button" class="button ghost small" data-show-password>${icon('eye')}<span>${h(t('auth.show_password'))}</span></button>${formActions(t(preview ? 'auth.create' : 'auth.submit'))}<div id="auth-error" role="alert"></div></form><p class="auth-note">${icon('lock')}${h(t('auth.invite_only'))}</p>${preview ? linkButton(t('auth.back'), '/', 'back', 'ghost') : ''}`}</div></section></main>`;
    bindGlobalControls();
    document.querySelector('[data-show-password]')?.addEventListener('click', () => { const input = document.querySelector('[name=password]'); input.type = input.type === 'password' ? 'text' : 'password'; document.querySelector('[data-show-password] span').textContent = t(input.type === 'password' ? 'auth.show_password' : 'auth.hide_password'); });
    bindForm('auth-form', async (form) => {
        const target = document.getElementById('auth-error');
        target.textContent = '';
        try {
            const auth = await api(preview ? '/auth/register' : '/auth/login', 'POST', preview ? { token, display_name: formValue(form, 'display_name'), password: formValue(form, 'password'), locale: state.locale } : { email: formValue(form, 'email'), password: formValue(form, 'password'), ...(state.localeTouched ? { locale: state.locale } : {}) });
            await acceptAuth(auth);
        }
        catch (error) {
            target.textContent = error instanceof Error ? error.message : t('error.unexpected');
            throw error;
        }
    });
}
function bindGlobalControls() {
    document.querySelectorAll('[data-locale]').forEach(el => el.addEventListener('click', () => {
        void (async () => {
            const locale = el.dataset.locale;
            state.localeTouched = true;
            if (locale === state.locale)
                return;
            const forms = captureForms();
            state.localeTouched = true;
            if (state.user)
                state.user = await api('/profile', 'PATCH', { locale });
            applyLocale(locale);
            const dirty = state.dirty;
            if (state.user) {
                await refreshWithShell();
            }
            else
                await refresh();
            restoreForms(forms);
            state.dirty = dirty;
        })().catch(showError);
    }));
    document.querySelectorAll('[data-theme-toggle]').forEach(el => el.addEventListener('click', () => { state.theme = state.theme === 'dark' ? 'light' : 'dark'; applyTheme(); }));
    document.querySelector('[data-logout]')?.addEventListener('click', () => {
        void (async () => {
            if (!await confirmAction(t('auth.logout_confirm')))
                return;
            await api('/auth/logout', 'POST', {});
            stopConnection();
            disposePage();
            Array.from({ length: sessionStorage.length }, (_, i) => sessionStorage.key(i)).filter((k) => !!k && k.startsWith('olympiados.work:')).forEach(k => sessionStorage.removeItem(k));
            state.user = null;
            state.csrf = '';
            state.dirty = false;
            await navigate('/', true);
            await refresh();
        })().catch(showError);
    });
    document.querySelector('[data-menu-toggle]')?.addEventListener('click', () => setMenu(!document.body.classList.contains('nav-open')));
    document.querySelectorAll('[data-menu-close],[data-menu-dismiss]').forEach(el => el.addEventListener('click', () => setMenu(false)));
    syncMenu();
}
function syncMenu() { const open = document.body.classList.contains('nav-open') && matchMedia('(max-width:760px)').matches; document.querySelector('.main-shell')?.toggleAttribute('inert', open); document.querySelector('[data-menu-toggle]')?.setAttribute('aria-expanded', String(open)); }
function setMenu(open) { document.body.classList.toggle('nav-open', open); syncMenu(); document.querySelector(open ? '[data-menu-close]' : '[data-menu-toggle]')?.focus(); }
window.addEventListener('resize', syncMenu);
document.addEventListener('keydown', event => {
    if (!document.body.classList.contains('nav-open'))
        return;
    if (event.key === 'Escape') {
        event.preventDefault();
        setMenu(false);
    }
    if (event.key === 'Tab' && matchMedia('(max-width:760px)').matches) {
        const nodes = [...document.querySelectorAll('.sidebar a,.sidebar button')].filter(el => el.getClientRects().length > 0);
        const first = nodes[0], last = nodes[nodes.length - 1];
        if (event.shiftKey && document.activeElement === first) {
            event.preventDefault();
            last?.focus();
        }
        else if (!event.shiftKey && document.activeElement === last) {
            event.preventDefault();
            first?.focus();
        }
    }
});
let rebuildShell = false;
async function refreshWithShell() { rebuildShell = true; await refresh(); }
async function render() {
    document.title = 'Adolat Olympic Club';
    if (!state.user) {
        await authPage();
        return;
    }
    shell(rebuildShell);
    rebuildShell = false;
    const path = routeURL().pathname;
    state.route = path;
    connect();
    document.title = 'Adolat Olympic Club';
    document.querySelectorAll('.nav-link').forEach(a => {
        const url = a.hash.slice(1);
        const active = path === url || url !== '/' && path.startsWith(url + '/');
        a.classList.toggle('active', active);
        if (active)
            a.setAttribute('aria-current', 'page');
        else
            a.removeAttribute('aria-current');
    });
    const parts = path.split('/').filter(Boolean);
    const section = parts[0] ?? '';
    const id = parts[1];
    const child = parts[2];
    if (!section)
        return dashboardPage();
    if (section === 'training') {
        if (!id)
            return trainingPage();
        if (id === 'new')
            return cycleForm();
        if (id === 'cycles' && child === 'new')
            return cycleForm();
        if (id === 'cycles' && child)
            return parts[3] === 'edit' ? cycleForm(child) : cyclePage(child);
        if (id === 'plans' && child)
            return planPage(child);
    }
    if (section === 'circles') {
        if (!id)
            return circlesPage();
        if (id === 'new')
            return circleForm();
        return child === 'edit' ? circleForm(id) : circlePage(id);
    }
    if (section === 'informatics') {
        if (id === 'account')
            return cfAccountPage();
        if (id === 'leaderboard')
            return leaderboardPage();
        return informaticsPage();
    }
    if (section === 'moderation')
        return moderationPage();
    if (section === 'cf-approvals')
        return cfApprovalsPage();
    if (section === 'subject-participation')
        return subjectParticipationPage();
    if (section === 'guide')
        return guidePage();
    if (section === 'classrooms') {
        if (!id)
            return classroomsPage();
        if (id === 'new')
            return classroomForm();
        if (child === 'edit')
            return classroomForm(id);
        if (child === 'resources')
            return resourceForm(id, parts[3] === 'new' ? undefined : parts[3]);
        return classroomPage(id);
    }
    if (section === 'problems') {
        if (!id)
            return libraryPage();
        if (id === 'new')
            return problemForm();
        if (child === 'edit')
            return problemForm(id);
        return problemPage(id);
    }
    if (section === 'sets')
        return setsPage();
    if (section === 'assignments')
        return activitiesPage('assignment');
    if (section === 'sessions')
        return activitiesPage('session');
    if (section === 'competitions')
        return activitiesPage('competition');
    if (section === 'activities' && id) {
        if (id === 'new')
            return activityForm();
        if (child === 'edit')
            return activityDraftForm(id);
        return activityPage(id);
    }
    if (section === 'present' && id)
        return presentationPage(id);
    if (section === 'groups') {
        if (!id)
            return groupsPage();
        if (id === 'new')
            return groupForm();
        return groupPage(id);
    }
    if (section === 'submissions') {
        if (id)
            return submissionPage(id);
        return submissionsPage();
    }
    if (section === 'progress')
        return progressPage();
    if (section === 'notifications')
        return notificationsPage();
    if (section === 'admin')
        return adminPage();
    if (section === 'enroll' && id)
        return enrollmentPage(id);
    if (section === 'invitations')
        return id === 'new' ? invitationForm() : invitationsPage();
    if (section === 'profile')
        return profilePage();
    setView(empty(t('error.not_found'), '', linkButton(t('nav.dashboard'), '/', 'home')));
}
document.addEventListener('click', event => {
    const anchor = event.target.closest('a[href^="#/"]');
    if (!anchor || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey)
        return;
    event.preventDefault();
    document.body.classList.remove('nav-open');
    syncMenu();
    void navigate(anchor.hash.slice(1)).catch(showError);
});
window.addEventListener('hashchange', () => {
    const next = currentPath();
    if (state.dirty && next !== lastHash) {
        void (async () => {
            if (!await confirmAction(t('work.unsaved_leave'))) {
                history.replaceState(null, '', '#' + lastHash);
                return;
            }
            state.dirty = false;
            lastHash = next;
            await refresh();
        })();
    }
    else {
        lastHash = next;
        void refresh();
    }
});
window.addEventListener('beforeunload', event => {
    if (state.dirty) {
        event.preventDefault();
    }
});
window.addEventListener('auth-expired', expired);
window.addEventListener('offline', () => connection('offline'));
window.addEventListener('online', () => {
    if (state.user) {
        connect(true);
        void handleRemote();
    }
});
document.addEventListener('toggle-theme', () => { state.theme = state.theme === 'dark' ? 'light' : 'dark'; applyTheme(); });
document.addEventListener('session-rotated', () => { if (state.user)
    connect(true); });
document.addEventListener('visibilitychange', () => { connect(); if (!document.hidden && state.user)
    void handleRemote(); });
document.addEventListener('shell-update', () => { rebuildShell = true; });
document.addEventListener('input', event => {
    const target = event.target;
    if (target.closest('#main form') && !target.closest('.work-editor') && !target.closest('#auth-form') && !target.closest('.filter-bar'))
        state.dirty = true;
});
async function start() {
    await initializeI18n();
    applyTheme();
    try {
        const auth = await api('/auth/me');
        clearOtherRecovery(auth.user.id);
        state.user = auth.user;
        state.csrf = auth.csrf;
        state.settings = auth.settings;
        applyLocale(auth.user.locale);
        state.subjects = await api('/subjects');
        state.canTrain = (await api('/subjects/mine')).can_train;
    }
    catch { }
    setRenderer(render);
    lastHash = currentPath();
    await refresh();
    if (state.user)
        connect();
}
void start().catch(error => { document.getElementById('app').textContent = error instanceof Error ? error.message : 'Не удалось загрузить приложение / Application could not load'; });
//# sourceMappingURL=app.js.map