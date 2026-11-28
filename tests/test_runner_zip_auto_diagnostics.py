"""Artificial diagnostics with injected checks; no real data."""
import ast
import json
from pathlib import Path
import sqlite3
import subprocess
import tempfile
import time
import unittest
from unittest.mock import patch

SOURCE=Path(__file__).resolve().parents[1]/'operations/runner_dist/START_GUI.pyw'
tree=ast.parse(SOURCE.read_text(encoding='utf-8'))
names={'diagnostic_read','diagnostic_text','diagnostic_run','diagnostic_quality'}
nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names or
       isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id.startswith('DIAG_') for t in n.targets)]
scope=dict(Path=Path,json=json,time=time,sqlite3=sqlite3,subprocess=subprocess,
           atomic=lambda p,b:p.write_bytes(b),local_folder=Path,
           SYNTH_RUN_FILE='synthetic_research_run.local.json',QUALITY_RECEIPT_LIMIT=1048576,CALENDAR_RECEIPT='development_calendar.local.json')
exec(compile(ast.Module(body=nodes,type_ignores=[]),str(SOURCE),'exec'),scope)

class DiagnosticsTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.calls=[]
        def ok(*args):
            self.calls.append('check')
        self.injections=dict(synthetic_probe_checkpoint=ok,parquet_runtime=ok,synthetic_ohlcv_checkpoint=ok,
                             synthetic_aggregation=ok,synthetic_run_read=lambda _:dict(status='COMPLETE'),
                             load_market_candidates=ok,synthetic_horizon_checkpoint=ok,synthetic_session_mapping_checkpoint=ok,synthetic_calendar_probe=ok,calendar_index_checkpoint=ok,synthetic_statistics_checkpoint=ok,synthetic_integrated_checkpoint=ok,source_gate_receipt=ok,synthetic_prefix_checkpoint=ok,synthetic_batch_adapter_checkpoint=ok)
        self.patch=patch.dict(scope,self.injections)
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def test_missing_optional_and_version(self):
        r=scope['diagnostic_run'](self.root,'0.8.7')
        self.assertEqual([x['status'] for x in r['steps']],['PASS','SKIP_NOT_CONFIGURED','SKIP_NOT_CONFIGURED','PASS','SKIP_NOT_CONFIGURED','SKIP_NOT_CONFIGURED','PASS','PASS','PASS','SKIP_NOT_CONFIGURED','PASS','SKIP_NOT_CONFIGURED','SKIP_NOT_CONFIGURED','SKIP_NOT_CONFIGURED','SKIP_NOT_CONFIGURED','SKIP_NOT_CONFIGURED'])
        self.assertEqual(scope['diagnostic_read'](self.root,'0.8.7'),r)
        self.assertIsNone(scope['diagnostic_read'](self.root,'0.8.8'))

    def test_errors_redacted_and_continue(self):
        (self.root/'ctl_pyarrow_26_0_1').mkdir()
        def fail(*args):
            raise ValueError('PRIVATE_TOKEN_AND_PATH')
        with patch.dict(scope,{'parquet_runtime':fail}):
            r=scope['diagnostic_run'](self.root,'0.8.7')
        self.assertEqual(r['steps'][1]['status'],'FAIL_VALIDATION')
        self.assertEqual(r['steps'][2]['status'],'PASS')
        self.assertNotIn('PRIVATE_TOKEN_AND_PATH',scope['diagnostic_text'](r))
        self.assertNotIn('PRIVATE_TOKEN_AND_PATH',(self.root/scope['DIAG_FILE']).read_text())

    def test_quality_no_persist_and_reproduce(self):
        saved=dict(schema=1,scope='LOCAL_RETROSPECTIVE_MONTHLY_SELECTION',research_access='LOCKED',
                   market_member_reads=0,requested_count=32,seed=42,min_months=12,min_coverage_bps=9000)
        dest=self.root/'market_monthly_quality_selection.local.json'
        dest.write_text(json.dumps(saved))
        before=dest.read_bytes()
        def evaluate(parent,count,seed,months,bps,persist):
            self.assertFalse(persist)
            self.assertEqual((count,seed,months,bps),(32,42,12,9000))
            return saved
        with patch.dict(scope,{'quality_index_run':evaluate}):
            r=scope['diagnostic_run'](self.root,'0.8.7')
        self.assertEqual(r['steps'][-1]['status'],'PASS')
        self.assertEqual(dest.read_bytes(),before)

    def test_report_rejects_untrusted_status(self):
        r=scope['diagnostic_run'](self.root,'0.8.7')
        r['steps'][0]['status']='SECRET'
        (self.root/scope['DIAG_FILE']).write_text(json.dumps(r))
        with self.assertRaises(ValueError):
            scope['diagnostic_read'](self.root,'0.8.7')

if __name__=='__main__':
    unittest.main()
