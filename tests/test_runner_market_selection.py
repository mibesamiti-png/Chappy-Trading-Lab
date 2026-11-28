"""Artificial selection/checkpoint tests. No registered real data."""
import ast
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import struct
import subprocess
import sys
import tempfile
import unittest
import zipfile

SOURCE=Path(__file__).resolve().parents[1]/'operations/runner_dist/START_GUI.pyw'
tree=ast.parse(SOURCE.read_text(encoding='utf-8'))
names={'drive_allowed','local_folder','local_zip','zip_paths','read_folders','catalog_bounds','CatalogView','catalog_file','catalog_registered','load_market_candidates','save_market_selection','auto_market_batch','save_auto_market_batch','parquet_env','parquet_command','parquet_runtime','synthetic_ohlcv_checkpoint'}
nodes=[n for n in tree.body if isinstance(n,(ast.FunctionDef,ast.ClassDef)) and n.name in names or isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and (t.id.startswith('CATALOG_') or t.id in {'ROLES','ZIP_LIMIT','SETTINGS_LIMIT','SELECTION_MAX','PARQUET_VERSION','PARQUET_WORKER','OHLCV_WORKER'}) for t in n.targets)]
scope=dict(Path=Path,os=os,re=re,stat=stat,struct=struct,json=json,zipfile=zipfile,hashlib=hashlib,sys=sys,subprocess=subprocess,atomic=lambda p,b:p.write_bytes(b))
exec(compile(ast.Module(body=nodes,type_ignores=[]),str(SOURCE),'exec'),scope)

class SelectionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.z=self.root/'test.zip'
        with zipfile.ZipFile(self.z,'w') as z:
            z.writestr('AAA.parquet',b'not opened')
            z.writestr('BBB.parquet',b'not opened')
        (self.root/'research_folders.local.json').write_text(json.dumps({'market_zips':[str(self.z)]}))
        scope['catalog_registered'](self.root)

    def test_select_roundtrip(self):
        digest,rows=scope['load_market_candidates'](self.root)
        self.assertEqual(len(rows),2)
        self.assertEqual(scope['save_market_selection'](self.root,digest,[rows[1]]),1)
        receipt=json.loads((self.root/'market_selection.local.json').read_text())
        self.assertEqual(receipt['selected'],[rows[1]])
        self.assertEqual(receipt['research_access'],'LOCKED')
        self.assertEqual(receipt['member_reads'],0)

    def test_stale(self):
        with self.z.open('ab') as f:
            f.write(b'x')
        with self.assertRaisesRegex(ValueError,'SELECTION_CATALOG_STALE'):
            scope['load_market_candidates'](self.root)

    def test_tampered_selection(self):
        digest,rows=scope['load_market_candidates'](self.root)
        for selection in ([],[rows[0],rows[0]],[{'archive_index':0,'member':'unknown.parquet'}]):
            with self.assertRaises(ValueError):
                scope['save_market_selection'](self.root,digest,selection)
        with self.assertRaisesRegex(ValueError,'SELECTION_CATALOG_STALE'):
            scope['save_market_selection'](self.root,'bad',rows)

    def test_auto_reproducible_and_full_coverage(self):
        rows=[{'archive_index':0,'member':f'{i:04}.parquet','size':100} for i in range(1253)]
        for mode in ('seeded','sequential'):
            seen=[]
            for b in range(40):
                chosen,plan=scope['auto_market_batch'](rows,mode,32,11,b)
                other,_=scope['auto_market_batch'](list(reversed(rows)),mode,32,11,b)
                self.assertEqual(chosen,other)
                seen.extend(r['member'] for r in chosen)
            self.assertEqual(len(seen),1253)
            self.assertEqual(len(set(seen)),1253)
            self.assertIsNone(plan['next_batch'])
            with self.assertRaisesRegex(ValueError,'AUTO_SELECTION_END'):
                scope['auto_market_batch'](rows,mode,32,11,40)

    def test_auto_receipt_separate_and_locked(self):
        digest,rows=scope['load_market_candidates'](self.root)
        scope['save_market_selection'](self.root,digest,[rows[0]])
        manual=(self.root/'market_selection.local.json').read_bytes()
        plan=scope['save_auto_market_batch'](self.root,digest,'seeded',1,42,0)
        receipt=json.loads((self.root/'market_auto_selection.local.json').read_text())
        self.assertEqual(receipt['selection_plan'],plan)
        self.assertEqual(receipt['research_access'],'LOCKED')
        self.assertEqual(receipt['member_reads'],0)
        self.assertEqual((self.root/'market_selection.local.json').read_bytes(),manual)
        with self.assertRaisesRegex(ValueError,'SELECTION_CATALOG_STALE'):
            scope['save_auto_market_batch'](self.root,'wrong','seeded',1,42,0)

    def test_auto_bad_policy(self):
        _,rows=scope['load_market_candidates'](self.root)
        for args in [('unknown',1,0,0),('seeded',0,0,0),('seeded',129,0,0),('seeded',1,-1,0),('seeded',1,0,-1)]:
            with self.assertRaises(ValueError):
                scope['auto_market_batch'](rows,*args)

    def test_real_venv_synthetic_ohlcv(self):
        scope['parquet_runtime'](self.root,True)
        report=scope['synthetic_ohlcv_checkpoint'](self.root)
        self.assertEqual(report['period_gate'],'PASS')
        self.assertEqual(report['audit']['duplicates'],1)
        self.assertGreaterEqual(report['elapsed_ms'],0)
        self.assertEqual(report,json.loads((self.root/'synthetic_ohlcv_probe.local.json').read_text()))

if __name__=='__main__':
    unittest.main()
