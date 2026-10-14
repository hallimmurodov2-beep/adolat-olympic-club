"""M1 DOM workflows. Native by default; inherited bridge is explicitly supplementary."""
from pathlib import Path
import os
from uuid import uuid4
from sqlalchemy import select
from playwright.sync_api import expect
import pytest
# Share exactly the V1 browser harness; these tests do not bypass app authorization.
from tests.test_browser import goto, confirm
from tests.test_v2_codeforces import OfficialFixture, reset_reservations, link, approve, opt
from tests.test_v2_training import make_circle, make_cycle, join
from server.models import TrainingPlan, TrainingItem, Submission, Activity, now_ms



def capture(page, name):
    folder = os.getenv('V2_SCREENSHOTS')
    if folder:
        destination = Path(folder); destination.mkdir(exist_ok=True, parents=True)
        page.screenshot(path=str(destination / name), full_page=True)

@pytest.fixture
def api_fixture(env):
    f=OfficialFixture();env.app.state.codeforces=f
    f.contests=[{'id':987654,'name':'Synthetic practice contest — TEST DATA','phase':'BEFORE','startTimeSeconds':now_ms()//1000+7200,'durationSeconds':7200}]
    return f


@pytest.mark.parametrize('locale',['ru','en'])
def test_private_training_ui_end_to_end_bilingual(tabs,env,api_fixture,locale):
    if os.getenv('V2_SCREENSHOTS') and locale == 'en':
        guest = tabs(locale='en')
        guest.page.wait_for_selector('#auth-form')
        guest.page.click('[data-locale=en]')
        guest.page.wait_for_function("[...document.querySelectorAll('.school-logo')].every(img=>img.complete && img.naturalWidth>0)")
        capture(guest.page, 'login-en.png')
    tab=tabs('student',locale);p=tab.page
    goto(tab,'/training/new','#cycle-form')
    p.fill('[name=title_en]','BFS practice week');p.fill('[name=title_ru]','Неделя обхода в ширину')
    p.fill('#cycle-form [name=goal]','Explain the queue invariant / Объяснить инвариант очереди')
    p.click('#cycle-form button[type=submit]');p.wait_for_selector('#plan-goal')
    p.locator('details').filter(has=p.locator('#add-link')).locator('summary').click()
    p.fill('#add-link [name=title]','Synthetic external practice link');p.fill('#add-link [name=url]','https://codeforces.com/problemset/problem/4/A')
    p.click('#add-link button[type=submit]');p.wait_for_selector('#practice-entry')
    p.select_option('#practice-entry [name=outcome]','revisit');p.select_option('#practice-entry [name=assistance]','editorial')
    p.fill('#practice-entry [name=reflection]','I need to check a boundary / Проверить границы')
    p.fill('#practice-entry [name=next_step]','Try again without the editorial')
    p.click('#practice-entry button[type=submit]')
    expect(p.locator('.practice-note')).to_contain_text('Try again without the editorial')
    capture(p, 'my-training-'+locale+'.png')
    assert p.title()=='Adolat Olympic Club'
    with env.app.state.sessions() as db:
        item=db.scalar(select(TrainingItem).join(TrainingPlan,TrainingPlan.id==TrainingItem.plan_id).where(TrainingPlan.user_id==env.users['student']))
        assert item.status=='revisit'
    # Subject context, outcome labels and private view remain translated after switching.
    p.click('[data-locale='+('en' if locale=='ru' else 'ru')+']')
    p.wait_for_selector('.practice-note')
    assert p.evaluate('document.documentElement.scrollWidth <= innerWidth')


@pytest.mark.parametrize('locale',['ru','en'])
def test_handle_opt_in_approval_and_leaderboard_ui(tabs,env,api_fixture,locale):
    student=tabs('student',locale);p=student.page
    goto(student,'/informatics/account','#cf-link')
    p.fill('#cf-link [name=handle]','FixtureStudent');p.check('#cf-link [name=consent]');p.click('#cf-link button[type=submit]')
    p.wait_for_selector('#cf-consent')
    expect(p.locator('#cf-consent [name=opt_in]')).not_to_be_checked()
    p.check('#cf-consent [name=opt_in]');p.click('#cf-consent button[type=submit]')
    p.wait_for_timeout(250)
    assert env.client().get('/api/informatics/leaderboard').json()['items']==[]
    admin=tabs('admin',locale);goto(admin,'/cf-approvals','.approval-card')
    admin.page.select_option('.approval-card [name=action]','approve')
    admin.page.click('.approval-card button[type=submit]');confirm(admin.page)
    expect(admin.page.locator('.approval-card [name=action] option[value=approve]')).to_have_count(0)
    goto(student,'/informatics/leaderboard','.cf-table')
    expect(p.locator('.cf-table')).to_contain_text('fixturestudent')
    expect(p.locator('.rating-value')).to_have_text('1,400' if locale=='en' else '1\u00a0400')
    capture(p, 'leaderboard-'+locale+'.png')
    goto(student,'/informatics/account','#cf-consent');p.uncheck('[name=opt_in]');p.click('#cf-consent button[type=submit]')
    p.wait_for_timeout(200);goto(student,'/informatics/leaderboard','#main h1')
    expect(p.locator('.cf-table')).to_have_count(0)


@pytest.mark.parametrize('locale',['ru','en'])
def test_circle_post_gate_and_open_debrief_ui(tabs,env,api_fixture,locale):
    cid=make_circle(env)['id'];join(env,cid)
    cycle,_=make_cycle(env,circle=cid)
    student=tabs('student',locale);path='/training/cycles/'+cycle['id']
    goto(student,path,'#debrief-panel')
    assert student.page.locator('#peer-form').count()==0
    opened,_=make_cycle(env,circle=cid,opened=True)
    goto(student,'/training/cycles/'+opened['id'],'#peer-form')
    student.page.fill('#peer-form [name=body]','After-practice explanation / Разбор после практики')
    student.page.click('#peer-form button[type=submit]')
    expect(student.page.locator('#peer-posts')).to_contain_text('After-practice explanation')


@pytest.mark.parametrize('locale',['ru','en'])
def test_hub_phone_countdown_no_provider_polling_and_branding(tabs,env,api_fixture,locale,tmp_path):
    tab=tabs('student',locale,{'width':360,'height':820});p=tab.page
    goto(tab,'/informatics','.contest-card');expect(p.locator('.contest-card')).to_contain_text('TEST DATA')
    before=len(api_fixture.calls);p.wait_for_timeout(2200)
    assert len(api_fixture.calls)==before
    assert p.locator('.contest-countdown').get_attribute('aria-live')=='off'
    assert p.evaluate('document.documentElement.scrollWidth <= innerWidth')
    expect(p.locator('.brand')).to_contain_text('Adolat')
    p.click('[data-menu-toggle]');p.click('[data-theme-toggle]');p.click('[data-menu-close]');p.wait_for_timeout(450)
    assert p.evaluate('document.documentElement.scrollWidth <= innerWidth')
    output=Path(os.environ.get('V2_SCREENSHOTS',str(tmp_path)));output.mkdir(exist_ok=True,parents=True)
    p.screenshot(path=str(output/f'informatics-mobile-{locale}-dark.png'),full_page=True)
    if os.getenv('V2_SCREENSHOTS'):
        p.set_viewport_size({'width':1440,'height':1100});p.wait_for_timeout(450)
        capture(p, 'informatics-hub-'+locale+'-dark.png')


def test_submission_lost_response_recovered_on_editor_reentry(tabs,env):
    tab=tabs('student','en');p=tab.page;goto(tab,'/activities/'+env.assignment,'[data-work-input]')
    # Forward POST to the real server, then lose its success response exactly once.
    p.evaluate("""()=>{window.__originalFetch=window.fetch;window.__lost=false;window.fetch=async(url,options)=>{const result=await window.__originalFetch(url,options);if(!window.__lost&&String(url)==='/api/submissions'&&options?.method==='POST'&&result.ok){window.__lost=true;throw new TypeError('synthetic lost response after real commit');}return result;};}""")
    p.fill('[data-work-input]','A real accepted synthetic proof')
    expect(p.locator('[data-save-status]')).to_have_text('Saved')
    p.click('[data-action=work-submit]');confirm(p)
    p.wait_for_selector('[data-action=receipt-check]')
    p.wait_for_function('window.__lost===true')
    goto(tab,'/profile','#profile-form')
    goto(tab,'/activities/'+env.assignment,'[data-submission-confirmation] a')
    assert p.locator('[data-pending-submission] button').count()==0
    with env.app.state.sessions() as db:
        rows=list(db.scalars(select(Submission).where(Submission.user_id==env.users['student'],Submission.content=='A real accepted synthetic proof')))
        assert len(rows)==1


@pytest.mark.parametrize('locale',['ru','en'])
def test_training_hub_breakpoints_stay_contained(tabs,env,api_fixture,locale):
    student=tabs('student',locale,{'width':320,'height':740});p=student.page
    goto(student,'/informatics','.contest-card')
    for width in [320,360,390,768,1024,1440]:
        p.set_viewport_size({'width':width,'height':850})
        p.wait_for_timeout(75)
        assert p.evaluate('document.documentElement.scrollWidth <= innerWidth'), f'overflow at {width}px'
        assert p.locator('#hub-contests').is_visible()
        assert p.locator('.contest-card').bounding_box()['width'] <= width
    # Opt-in board is only a preview: the empty state should not be a full page.
    p.set_viewport_size({'width':360,'height':800})
    assert p.locator('.hub-leaderboard-panel').bounding_box()['height'] < 290


def test_admin_reschedule_uses_preflight_and_server_time(tabs,env):
    competition=env.create_activity('competition',eligible_ids=[env.users['student']])
    env.publish(competition)
    teacher=tabs('teacher','en')
    goto(teacher,'/activities/'+competition,'#activity-preflight details')
    teacher.page.locator('#activity-preflight summary').click()
    teacher.page.click('[data-action=preflight-check]')
    teacher.page.wait_for_selector('#preflight-results strong')
    assert teacher.page.locator('#interruption-extension').count()==0
    admin=tabs('admin','en')
    goto(admin,'/activities/'+competition,'#activity-preflight details')
    admin.page.locator('#activity-preflight summary').click()
    admin.page.fill('#interruption-extension [name=minutes]','15')
    admin.page.fill('#interruption-extension [name=reason]','School-authorized interruption: the school network was temporarily unavailable.')
    old=env.client('admin').get('/api/activities/'+competition).json()['ends_at']
    admin.page.click('#interruption-extension button[type=submit]')
    confirm(admin.page)
    admin.page.wait_for_timeout(350)
    assert env.client('admin').get('/api/activities/'+competition).json()['ends_at']==old+900000
