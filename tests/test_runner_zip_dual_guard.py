"""Operational guard fixtures; no network or market data."""
import ast
import base64
import hashlib
import json
import os
import re
import sqlite3
import tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path
import unittest
SOURCE=Path(__file__).resolve().parents[1]/'operations/runner_dist/START_GUI.pyw'
tree=ast.parse(SOURCE.read_text(encoding='utf-8'))
names={'control_queue_summary','dual_contents','dual_local_guard','dual_remote_lease','dual_remote_write','dual_owned','dual_run'}
constants={'CONTROL_IDS','DUAL_PR','DUAL_HEAD','DUAL_BASE','DUAL_LEASE','DUAL_LEASE_GET','DUAL_QUEUE','DUAL_JOURNAL','DUAL_STATUS_TEXT'}
nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names or isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id in constants for t in n.targets)]
scope=dict(base64=base64,hashlib=hashlib,json=json,os=os,re=re,sqlite3=sqlite3,Path=Path,
           datetime=datetime,timezone=timezone,timedelta=timedelta,local_folder=Path,CONTROL_LAUNCH='a'*32,
           control_evidence=lambda _: 'b'*64,control_checkpoint=lambda *args:'REOPENED',atomic=lambda p,b:p.write_bytes(b))
exec(compile(ast.Module(body=nodes,type_ignores=[]),str(SOURCE),'exec'),scope)

def fixture_db(p):
    with sqlite3.connect(p) as db:
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
        if endpoint==scope['DUAL_BASE']+'/pulls/41':
            return dict(state='open',draft=True,head=dict(sha=scope['DUAL_HEAD'],repo=dict(full_name='mibesamiti-png/Chappy-Trading-Lab')),base=dict(ref='main'))
        if endpoint==scope['DUAL_BASE']+'/pulls?state=open&per_page=100':
            return []
        if endpoint==scope['DUAL_LEASE'] and method=='PUT':
            if self.race or body['sha']!=self.contents(self.lease)['sha']:
                raise ValueError('CAS_CONFLICT')
            self.lease=json.loads(base64.b64decode(body['content']))
            self.writes+=1
            return dict(content=dict(sha=self.contents(self.lease)['sha']))
        if endpoint==scope['DUAL_BASE']+'/issues/41/comments':
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
        with sqlite3.connect(self.db) as c:
            self.assertEqual(c.execute('SELECT status,checkpoint FROM guard').fetchone(),('released','private-checkpoint'))
            self.assertEqual(c.execute('SELECT task FROM completed').fetchone(),('CTL-004',))
        self.assertEqual(self.run_pilot(),'PASS')
        self.assertEqual(self.api.writes,2)
    def test_active_remote_stops_without_write(self):
        self.api.lease.update(status='active',owner='foreign',task_ids=['CTL-001'],expires_utc='2000-01-01T00:00:00Z')
        with self.assertRaises(ValueError):
            self.run_pilot()
        self.assertEqual(self.api.writes,0)
    def test_active_local_stops_without_write(self):
        with sqlite3.connect(self.db) as c:
            c.execute("UPDATE guard SET owner='foreign',status='active'")
        with self.assertRaises(ValueError):
            self.run_pilot()
        self.assertEqual(self.api.writes,0)
        with sqlite3.connect(self.db) as c:
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
