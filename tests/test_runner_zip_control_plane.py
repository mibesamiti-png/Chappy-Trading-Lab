"""Control plane fixtures; no actual market data or network."""
import ast
import hashlib
import json
import re
import sqlite3
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

SOURCE=Path(__file__).resolve().parents[1]/'operations/runner_dist/START_GUI.pyw'
tree=ast.parse(SOURCE.read_text(encoding='utf-8'))
names={'control_queue_summary','control_checkpoint','control_plane_text'}
constants={'CONTROL_IDS','CONTROL_DB'}
nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names or
       isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id in constants for t in n.targets)]
scope=dict(hashlib=hashlib,json=json,re=re,sqlite3=sqlite3,local_folder=Path)
exec(compile(ast.Module(body=nodes,type_ignores=[]),str(SOURCE),'exec'),scope)


def fixture():
    tasks=[dict(id='CTL-%03d'%i,priority=i,status='completed') for i in range(1,7)]
    tasks[0]['status']='blocked'
    tasks[4]['decision']='no_go_for_new_predictive_models_on_this_branch'
    tasks[5]['status']='approval_required'
    q=dict(schema_version=1,revision=2,holdout=dict(year=2026,status='locked'),tasks=tasks)
    lease=dict(schema_version=1,status='idle',owner=None,task_ids=[],expires_utc=None)
    return q,lease


class ControlTests(unittest.TestCase):
    def test_skip_and_lock(self):
        q,l=fixture()
        out=scope['control_queue_summary'](q,l)
        self.assertEqual((out['completed'],out['next_task'],out['research_access']),(4,'CTL-001','LOCKED'))
        self.assertEqual(out['remote'],'OBSERVED_IDLE_NOT_ACQUIRED')
        l.update(status='active',owner='fixture',task_ids=['CTL-001'],expires_utc='2000-01-01T00:00:00Z')
        self.assertEqual(scope['control_queue_summary'](q,l)['remote'],'OBSERVED_ACTIVE_STOP')
        q['holdout']['status']='unlocked'
        with self.assertRaises(ValueError):
            scope['control_queue_summary'](q,l)

    def test_scope_changes_fail_closed(self):
        q,l=fixture()
        q['tasks'][4]['decision']='go'
        with self.assertRaises(ValueError):
            scope['control_queue_summary'](q,l)
        q,l=fixture()
        q['tasks'][5]['status']='ready'
        with self.assertRaises(ValueError):
            scope['control_queue_summary'](q,l)

    def test_checkpoint_reopen_and_change(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)
            summary=scope['control_queue_summary'](*fixture())
            check=scope['control_checkpoint']
            self.assertEqual(check(p,'a'*32,'b'*64,summary),'RESTART_REQUIRED')
            self.assertEqual(check(p,'a'*32,'b'*64,summary),'RESTART_REQUIRED')
            self.assertEqual(check(p,'c'*32,'b'*64,summary),'REOPENED')
            self.assertEqual(check(p,'d'*32,'b'*64,summary),'REOPENED')
            self.assertEqual(check(p,'d'*32,'e'*64,summary),'EVIDENCE_CHANGED_STOP')
            self.assertEqual(check(p,'d'*32,'b'*64,summary),'REOPENED')
            report=scope['control_plane_text']({**summary,'continuity':'REOPENED'})
            self.assertIn('未取得',report)
            self.assertIn('未検証',report)

    def test_local_ledger_contention(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)
            summary=scope['control_queue_summary'](*fixture())
            check=scope['control_checkpoint']
            self.assertEqual(check(p,'a'*32,'b'*64,summary),'RESTART_REQUIRED')
            db=sqlite3.connect(p/scope['CONTROL_DB'],isolation_level=None)
            try:
                db.execute('BEGIN IMMEDIATE')
                with self.assertRaises(sqlite3.OperationalError):
                    check(p,'c'*32,'b'*64,summary)
                db.rollback()
            finally:
                db.close()
            self.assertEqual(check(p,'c'*32,'b'*64,summary),'REOPENED')


if __name__=='__main__':
    unittest.main()
