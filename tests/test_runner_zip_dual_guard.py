"""Operational guard fixtures; no network or market data."""
import ast
import base64
import hashlib
import json
import os
import re
import sqlite3
import stat
import tempfile
from contextlib import closing
from datetime import datetime, timezone, timedelta
from pathlib import Path
import unittest
SOURCE=Path(__file__).resolve().parents[1]/'operations/runner_dist/START_GUI.pyw'
tree=ast.parse(SOURCE.read_text(encoding='utf-8'))
names={'control_queue_summary','dual_contents','dual_local_guard','dual_remote_lease','dual_auth_check','dual_remote_write','dual_owned','dual_run','resume_file','resume_read','resume_db_identity','resume_expected_bars','resume_checkpoint_read','resume_next','resume_do_stage','aggregate_session_rows'}
constants={'CONTROL_IDS','DUAL_PR','DUAL_HEAD','DUAL_BASE','DUAL_LEASE','DUAL_LEASE_GET','DUAL_QUEUE','DUAL_JOURNAL','DUAL_STATUS_TEXT','RESUME_PR','RESUME_HEAD','RESUME_PROTOCOL','RESEARCH_HORIZONS'}
nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names or isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id in constants for t in n.targets)]
scope=dict(base64=base64,hashlib=hashlib,json=json,os=os,re=re,sqlite3=sqlite3,stat=stat,Path=Path,
           datetime=datetime,timezone=timezone,timedelta=timedelta,local_folder=Path,CONTROL_LAUNCH='a'*32,
           control_evidence=lambda _: 'b'*64,control_checkpoint=lambda *args:'REOPENED',atomic=lambda p,b:p.write_bytes(b))
exec(compile(ast.Module(body=nodes,type_ignores=[]),str(SOURCE),'exec'),scope)

def fixture_db(p):
    with closing(sqlite3.connect(p)) as db, db:
        db.execute('CREATE TABLE guard (id INTEGER PRIMARY KEY,owner TEXT,status TEXT,deadline TEXT,checkpoint TEXT)')
        db.execute('CREATE TABLE completed (task TEXT,revision TEXT,owner TEXT,finished TEXT,PRIMARY KEY(task,revision))')
        db.execute("INSERT INTO guard VALUES(1,'previous','released','old','private-checkpoint')")
        db.execute("INSERT INTO completed VALUES('CTL-004','r1','previous','old')")

class Service:
    def __init__(self):
        self.lease=dict(schema_version=1,status='idle',owner=None,task_ids=[],expires_utc=None)
        tasks=[dict(id='CTL-%03d'%i,priority=i,status='completed') for i in range(1,7)]
        tasks[0]['status']='blocked'
        tasks[4]['decision']='no_go_for_new_predictive_models_on_this_branch'
        tasks[5]['status']='approval_required'
        self.q=dict(schema_version=1,revision=2,holdout=dict(year=2026,status='locked'),tasks=tasks)
        self.comments=0
        self.writes=0
        self.race=False
    def contents(self,obj):
        raw=json.dumps(obj,sort_keys=True).encode()
        return dict(type='file',encoding='base64',sha=hashlib.sha1(raw).hexdigest(),content=base64.b64encode(raw).decode())
    def __call__(self,endpoint,method='GET',body=None):
        if endpoint==scope['DUAL_QUEUE']:
            return self.contents(self.q)
        if endpoint==scope['DUAL_LEASE_GET']:
            return self.contents(self.lease)
        if endpoint in (scope['DUAL_BASE']+'/pulls/41',scope['DUAL_BASE']+'/pulls/43'):
            return dict(state='open',draft=True,head=dict(sha=scope['RESUME_HEAD'] if endpoint.endswith('/43') else scope['DUAL_HEAD'],repo=dict(full_name='mibesamiti-png/Chappy-Trading-Lab')),base=dict(ref='main'))
        if endpoint==scope['DUAL_BASE']+'/pulls?state=open&per_page=100':
            return []
        if endpoint==scope['DUAL_LEASE'] and method=='PUT':
            if self.race or body['sha']!=self.contents(self.lease)['sha']:
                raise ValueError('CAS_CONFLICT')
            self.lease=json.loads(base64.b64decode(body['content']))
            self.writes+=1
            return dict(content=dict(sha=self.contents(self.lease)['sha']))
        if endpoint in (scope['DUAL_BASE']+'/issues/41/comments',scope['DUAL_BASE']+'/issues/43/comments'):
            self.comments+=1
            return dict(id=1)
        raise AssertionError(endpoint)

class DualGuardTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.p=Path(self.tmp.name)
        self.db=self.p/'run_guard.sqlite'
        fixture_db(self.db)
        self.api=Service()
    def run_pilot(self):
        return scope['dual_run'](self.p,self.db,self.api)
    def test_roundtrip_preserves_checkpoint_and_completion(self):
        self.assertEqual(self.run_pilot(),'PASS')
        self.assertEqual((self.api.writes,self.api.comments,self.api.lease['status']),(2,1,'idle'))
        with closing(sqlite3.connect(self.db)) as c, c:
            self.assertEqual(c.execute('SELECT status,checkpoint FROM guard').fetchone(),('released','private-checkpoint'))
            self.assertEqual(c.execute('SELECT task FROM completed').fetchone(),('CTL-004',))
        self.assertEqual(self.run_pilot(),'PASS')
        self.assertEqual(self.api.writes,2)
    def test_two_stage_guarded_resume(self):
        self.assertEqual(self.run_pilot(),'PASS')
        self.assertEqual(scope['resume_next'](self.p),1)
        self.assertEqual(scope['dual_run'](self.p,self.db,self.api,resume_stage=1),'PASS')
        self.assertEqual(scope['resume_next'](self.p),2)
        original=scope['resume_file'](self.p,1,'checkpoint').read_bytes()
        with self.assertRaises(ValueError):
            scope['dual_run'](self.p,self.db,self.api,resume_stage=1)
        self.assertEqual(scope['dual_run'](self.p,self.db,self.api,resume_stage=2),'PASS')
        self.assertEqual(scope['resume_next'](self.p),0)
        self.assertEqual(scope['resume_file'](self.p,1,'checkpoint').read_bytes(),original)
        self.assertEqual((self.api.writes,self.api.comments,self.api.lease['status']),(6,3,'idle'))
    def test_resume_refuses_changed_checkpoint(self):
        self.run_pilot()
        scope['dual_run'](self.p,self.db,self.api,resume_stage=1)
        p=scope['resume_file'](self.p,1,'checkpoint')
        obj=json.loads(p.read_bytes())
        obj['bars'][0][4]+=1
        p.write_text(json.dumps(obj))
        with self.assertRaises(ValueError):
            scope['resume_next'](self.p)
        self.assertEqual(self.api.writes,4)
    def test_resume_refuses_missing_release(self):
        self.run_pilot()
        scope['dual_run'](self.p,self.db,self.api,resume_stage=1)
        p=scope['resume_file'](self.p,1,'journal')
        obj=json.loads(p.read_bytes())
        obj['phase']='CHECKPOINT_SAVED'
        p.write_text(json.dumps(obj))
        with self.assertRaises(ValueError):
            scope['resume_next'](self.p)
        self.assertEqual(self.api.writes,4)
    def test_auth_check_is_read_only(self):
        self.assertEqual(scope['dual_auth_check'](self.api),'PASS')
        self.assertEqual((self.api.writes,self.api.comments),(0,0))
    def test_main_ui_auth_contract(self):
        desktop=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='DataDesktop')
        method=next(n for n in desktop.body if isinstance(n,ast.FunctionDef) and n.name=='run_dual_guard')
        calls=[n for n in ast.walk(method) if isinstance(n,ast.Call)]
        get_calls=[n for n in calls if isinstance(n.func,ast.Attribute) and n.func.attr=='get_token']
        self.assertEqual(len(get_calls),1)
        self.assertEqual(get_calls[0].func.value.id,'self')
        self.assertFalse(any(isinstance(n.func,ast.Attribute) and n.func.attr in ('askstring','load','save') for n in calls))
        self.assertTrue(any(isinstance(n.func,ast.Name) and n.func.id=='dual_auth_check' for n in calls))
        self.assertTrue(any(isinstance(n.func,ast.Name) and n.func.id=='dual_api' and any(k.arg=='token' and isinstance(k.value,ast.Name) and k.value.id=='token' for k in n.keywords) for n in calls))
    def test_active_remote_stops_without_write(self):
        self.api.lease.update(status='active',owner='foreign',task_ids=['CTL-001'],expires_utc='2000-01-01T00:00:00Z')
        with self.assertRaises(ValueError):
            self.run_pilot()
        self.assertEqual(self.api.writes,0)
    def test_active_local_stops_without_write(self):
        with closing(sqlite3.connect(self.db)) as c, c:
            c.execute("UPDATE guard SET owner='foreign',status='active'")
        with self.assertRaises(ValueError):
            self.run_pilot()
        self.assertEqual(self.api.writes,0)
        with closing(sqlite3.connect(self.db)) as c, c:
            self.assertEqual(c.execute('SELECT owner,status,checkpoint FROM guard').fetchone(),('foreign','active','private-checkpoint'))
    def test_cas_conflict_no_retry(self):
        self.api.race=True
        with self.assertRaises(ValueError):
            self.run_pilot()
        self.assertEqual(self.api.writes,0)
        with self.assertRaisesRegex(ValueError,'RECONCILE'):
            self.run_pilot()

if __name__=='__main__':
    unittest.main()
