"""Real multi-user workflows. Set BROWSER_BRIDGE=1 only for navigation-restricted sandboxes."""
from __future__ import annotations
import os
import socket
import subprocess
import threading
import time
from pathlib import Path
import pytest
import uvicorn
from playwright.sync_api import expect
from tests.browser_harness import BrowserTab, ROOT
from tests.conftest import PASSWORD

def goto(tab,path,selector):
    tab.goto(path);tab.page.wait_for_selector(selector)

def confirm(page):
    page.locator('#confirm-dialog[open] button[value=confirm]').click()

@pytest.mark.parametrize('locale',['ru','en'])
def test_teacher_student_assignment_grading_and_autosave(tabs,env,locale):
    teacher=tabs('teacher',locale);student=tabs('student',locale)
    goto(student,'/activities/'+env.assignment,'[data-work-input]')
    page=student.page;proof='Обоснование: $(n+1)(n+2)$ чётно.\nProof: consider residues modulo three.'
    page.fill('[data-work-input]',proof)
    expect(page.locator('[data-save-status]')).to_have_text('Сохранено' if locale=='ru' else 'Saved')
    page.click('[data-action=work-submit]');confirm(page)
    page.wait_for_selector('[data-submission-confirmation] a')
    submission_path=page.locator('[data-submission-confirmation] a').get_attribute('href')[1:]
    goto(teacher,submission_path,'#grade-form')
    tpage=teacher.page
    tpage.fill('[name=criterion_0]','2');tpage.fill('[name=criterion_1]','4');tpage.fill('[name=criterion_2]','1')
    tpage.fill('[name=feedback_ru]','Хорошее доказательство.');tpage.fill('[name=feedback_en]','A well-justified proof.')
    assert not tpage.locator('[name=release]').is_checked()
    tpage.check('[name=release]');tpage.click('#grade-form button[type=submit]')
    expect(tpage.locator('.toast').last).to_have_text('Проверка сохранена' if locale=='ru' else 'Review saved')
    goto(student,submission_path,'.score-large')
    expect(page.locator('.score-large')).to_contain_text('7')
    expect(page.locator('#main')).to_contain_text('Хорошее доказательство.' if locale=='ru' else 'A well-justified proof.')
    assert page.locator('mjx-container').count()>0

@pytest.mark.parametrize('locale',['ru','en'])
def test_teacher_creates_problem_activity_and_invitation(tabs,env,locale):
    teacher=tabs('teacher',locale);page=teacher.page
    goto(teacher,'/problems/new?classroom='+env.rooms['math'],'#problem-form')
    page.fill('[name=title_ru]','Новая задача о чётности');page.fill('[name=title_en]','A new parity problem')
    page.fill('[name=statement_ru]','Докажите, что $2n$ чётно.');page.fill('[name=statement_en]','Prove that $2n$ is even.')
    page.fill('[name=hints_ru]','Вспомните определение чётности.');page.fill('[name=solution_en]','It is divisible by two.')
    page.click('#problem-form button[type=submit]');page.wait_for_selector('[data-upload-kind=problem]')
    page.locator('[data-upload-kind=problem]').set_input_files({'name':'statement.txt','mimeType':'text/plain','buffer':b'Teacher-authored statement supplement.'})
    expect(page.locator('#main')).to_contain_text('statement.txt')
    goto(teacher,'/activities/new?kind=assignment&classroom='+env.rooms['math'],'#activity-form')
    page.fill('[name=title_ru]','Проверка чётности');page.fill('[name=title_en]','Parity practice')
    page.locator('label.checkbox').filter(has_text='Новая задача' if locale=='ru' else 'A new parity').locator('input').check()
    page.click('#activity-form button[type=submit]');page.wait_for_selector('[data-action=publish]');page.click('[data-action=publish]')
    page.wait_for_selector('[data-action=end]');assert page.locator('#main').get_by_text('Parity practice' if locale=='en' else 'Проверка чётности').count()>0
    goto(teacher,'/invitations/new?classroom='+env.rooms['math'],'#invite-form')
    page.fill('[name=email]',f'new-{locale}@example.school.test');page.click('#invite-form button[type=submit]');page.wait_for_selector('#private-invite-link')
    token=page.locator('#private-invite-link').input_value().split('/')[-1]
    invitee=tabs(locale=locale);invitee.goto('/register/'+token)
    invitee.page.wait_for_selector('[name=display_name]')
    if locale=='en':invitee.page.click('[data-locale=en]')
    invitee.page.fill('[name=display_name]','Новый участник' if locale=='ru' else 'New member')
    invitee.page.fill('[name=password]',PASSWORD);invitee.page.click('#auth-form button[type=submit]');invitee.page.wait_for_selector('.sidebar')
    expect(invitee.page.locator('.profile-link small')).to_have_text('Ученик' if locale=='ru' else 'Student')

@pytest.mark.parametrize('locale',['ru','en'])
def test_live_session_sse_release_and_assistance(tabs,env,locale):
    teacher=tabs('teacher',locale);student=tabs('student',locale);sid=env.session
    goto(teacher,'/activities/'+sid,'[data-action=start]');teacher.page.click('[data-action=start]');teacher.page.wait_for_selector('[data-action=release-problem]')
    goto(student,'/activities/'+sid,'#task-reading .empty-state')
    teacher.page.click('[data-action=release-problem]')
    # No student navigation or manual refresh after the teacher release; real SSE drives this change.
    student.page.wait_for_selector('[data-work-input]')
    student.page.fill('#help-form [name=body]','Нужна помощь' if locale=='ru' else 'Please help with the idea')
    student.page.click('#help-form button[type=submit]')
    teacher.page.wait_for_selector('[data-action=resolve-help]');teacher.page.click('[data-action=resolve-help]')
    expect(teacher.page.locator('[data-action=resolve-help]')).to_have_count(0)
    teacher.page.click('[data-action=end]');confirm(teacher.page)
    expect(student.page.locator('[data-action=work-submit]')).to_be_disabled()

@pytest.mark.parametrize('locale',['ru','en'])
def test_group_conflict_protection_and_shared_submission(tabs,env,locale):
    first=tabs('student',locale);second=tabs('teammate',locale)
    goto(first,'/groups/'+env.group,'[data-work-input]');goto(second,'/groups/'+env.group,'[data-work-input]')
    # Both edits occur before either debounce expires; the server must reject one stale revision.
    first.page.fill('[data-work-input]','First contribution — первое решение.')
    second.page.fill('[data-work-input]','Second contribution — второе решение.')
    first.page.wait_for_timeout(2200)
    conflicted=first if first.page.locator('.conflict-box').count() else second
    conflicted.page.wait_for_selector('.conflict-box')
    assert conflicted.page.locator('[data-work-input]').input_value() in ('First contribution — первое решение.','Second contribution — второе решение.')
    conflicted.page.click('[data-action=use-server]')
    expect(conflicted.page.locator('.conflict-box')).to_have_count(0)
    conflicted.page.fill('#comment-form [name=body]','Обсудим оба подхода. / Let us discuss both approaches.')
    conflicted.page.click('#comment-form button[type=submit]')
    expect(first.page.locator('#group-discussion')).to_contain_text('Let us discuss')
    conflicted.page.click('[data-action=work-submit]');confirm(conflicted.page)
    conflicted.page.wait_for_selector('[data-submission-confirmation] a')

@pytest.mark.parametrize('locale',['ru','en'])
def test_mobile_locale_and_dark_theme_without_page_reload(tabs,env,locale,tmp_path):
    tab=tabs('student',locale,{'width':390,'height':844});page=tab.page
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    page.click('[data-menu-toggle]');page.click('[data-theme-toggle]')
    expect(page.locator('html')).to_have_attribute('data-theme','dark')
    page.click('[data-locale='+('en' if locale=='ru' else 'ru')+']')
    expect(page.locator('html')).to_have_attribute('lang','en' if locale=='ru' else 'ru')
    expect(page.locator('.sidebar')).to_be_visible()
    page.click('[data-menu-close]');page.screenshot(path=str(tmp_path/f'mobile-{locale}.png'),full_page=True)
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')

@pytest.mark.parametrize('locale',['ru','en'])
def test_all_essential_routes_have_no_runtime_or_translation_errors(tabs,env,locale):
    teacher=tabs('teacher',locale);student=tabs('student',locale)
    for tab in (teacher,student):
        for path in ['/classrooms','/problems','/assignments','/sessions','/competitions','/groups','/submissions','/progress','/profile','/notifications','/guide']:
            goto(tab,path,'#main h1');tab.page.wait_for_timeout(80)
        for path in ['/classrooms/'+env.rooms['math'],'/activities/'+env.assignment,'/groups/'+env.group]:
            goto(tab,path,'#main h1');tab.page.wait_for_timeout(120)
    for path,selector in [('/classrooms/new','#classroom-form'),('/groups/new','#group-form'),('/activities/new?kind=competition','#activity-form'),('/sets','#main h1'),('/invitations','#main h1')]:
        goto(teacher,path,selector)
    admin=tabs('admin',locale);goto(admin,'/admin','#settings-form')

@pytest.mark.parametrize('locale',['ru','en'])
def test_competition_interface_drafts_cutoff_and_sealed_results(tabs,env,locale):
    from server.models import Activity, now_ms
    aid=env.create_activity('competition',eligible_ids=[env.users['student']])
    env.publish(aid)
    student=tabs('student',locale);teacher=tabs('teacher',locale)
    goto(student,'/activities/'+aid,'[data-work-input]')
    page=student.page
    expect(page.locator('#countdown')).not_to_have_text('')
    page.fill('[data-work-input]','Competition proof / Доказательство на соревновании.')
    expect(page.locator('[data-save-status]')).to_have_text('Сохранено' if locale=='ru' else 'Saved')
    page.click('[data-action=work-submit]');confirm(page)
    page.wait_for_selector('[data-submission-confirmation] a')
    path=page.locator('[data-submission-confirmation] a').get_attribute('href')[1:]
    # Move the real server deadline; the UI learns it from actual HTTP polling/SSE.
    # No browser-clock monkeypatching or fabricated submission response is involved.
    with env.app.state.sessions() as db:
        db.get(Activity,aid).ends_at=now_ms()-1
        from server.services.events import emit
        emit(db,'activity',aid,classroom_id=env.rooms['math'])
        db.commit()
    expect(page.locator('[data-action=work-submit]')).to_be_disabled(timeout=12000)
    goto(teacher,path,'#grade-form')
    teacher.page.fill('[name=score]','7');teacher.page.fill('[name=feedback_en]','Correct competition proof.')
    teacher.page.fill('[name=feedback_ru]','Верное решение на соревновании.')
    assert teacher.page.locator('[name=release]').count()==0
    teacher.page.click('#grade-form button[type=submit]')
    expect(teacher.page.locator('.toast').last).to_have_text('Проверка сохранена' if locale=='ru' else 'Review saved')
    goto(student,path,'.review-layout')
    assert student.page.locator('.score-large').count()==0
    goto(teacher,'/activities/'+aid,'[data-action=publish_results]')
    teacher.page.click('[data-action=publish_results]');confirm(teacher.page)
    expect(student.page.locator('.score-large')).to_contain_text('7',timeout=12000)

@pytest.mark.parametrize('locale',['ru','en'])
def test_autosave_network_recovery_preserves_text(tabs,env,locale):
    student=tabs('student',locale);goto(student,'/activities/'+env.assignment,'[data-work-input]')
    # A deterministic transport fault, not a fake API result: the following retry
    # is forwarded to the real backend and checked through an independent client.
    student.page.evaluate("""()=>{window.__originalFetch=window.fetch;window.__failWork=true;window.fetch=(url,options)=>{if(window.__failWork&&String(url).includes('/api/drafts/')&&options?.method==='PUT')return Promise.reject(new TypeError('offline'));return window.__originalFetch(url,options);};}""")
    text='Recovered after reconnect / Восстановлено после соединения.'
    student.page.fill('[data-work-input]',text)
    student.page.wait_for_selector('[data-action=retry-save]')
    assert student.page.locator('[data-work-input]').input_value()==text
    student.page.evaluate("()=>{window.__failWork=false;window.dispatchEvent(new Event('online'));}")
    expect(student.page.locator('[data-save-status]')).to_have_text('Сохранено' if locale=='ru' else 'Saved')
    assert env.client().get('/api/drafts/'+env.item).json()['content']==text
