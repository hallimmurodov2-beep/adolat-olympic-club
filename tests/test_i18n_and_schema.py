import json
import re
from pathlib import Path
import pytest
from alembic import command
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.autogenerate import compare_metadata
from sqlalchemy import create_engine
from server.models import Base
from server.i18n import translate

ROOT=Path(__file__).resolve().parents[1]

def test_dictionaries_match_and_have_no_empty_values():
    en=json.loads((ROOT/'locales/en.json').read_text());ru=json.loads((ROOT/'locales/ru.json').read_text())
    assert set(en)==set(ru)
    assert all(en.values()) and all(ru.values())
    for key,value in en.items():
        assert isinstance(value,type(ru[key]))
        if isinstance(value,str):assert set(re.findall(r'\{(\w+)\}',value))==set(re.findall(r'\{(\w+)\}',ru[key]))

def test_all_literal_translation_keys_exist():
    keys=set(json.loads((ROOT/'locales/en.json').read_text()))
    missing=[]
    for file in (ROOT/'frontend').glob('*.ts'):
        for match in re.finditer(r"\bt\(['\"]([^'\"]+)['\"]\s*([,)])",file.read_text()):
            if match[1] not in keys:missing.append((file.name,match[1]))
    assert not missing,missing

@pytest.mark.parametrize('locale',['ru','en'])
def test_validation_errors_localized(env,locale):
    client=env.client(locale=locale);response=client.patch('/api/profile',json={'role':'admin'})
    assert response.status_code==422
    expected=json.loads((ROOT/'locales'/f'{locale}.json').read_text())['error.invalid_input']
    assert response.json()['error']['message']==expected

@pytest.mark.parametrize('count,category',[(1,'one'),(2,'few'),(5,'many'),(21,'one'),(22,'few'),(25,'many'),(0,'many'),(1.5,'other')])
def test_russian_plural_rules(count,category):
    from babel import Locale
    assert Locale('ru').plural_form(count)==category

def test_migrations_roundtrip_and_model_parity(tmp_path):
    db=tmp_path/'migration.db';config=Config(str(ROOT/'alembic.ini'));config.attributes['explicit_url']=True;config.set_main_option('sqlalchemy.url','sqlite:///'+str(db));config.set_main_option('script_location',str(ROOT/'migrations'))
    command.upgrade(config,'head');engine=create_engine('sqlite:///'+str(db))
    with engine.connect() as connection:
        assert compare_metadata(MigrationContext.configure(connection),Base.metadata)==[]
    engine.dispose();command.downgrade(config,'base');command.upgrade(config,'head')
