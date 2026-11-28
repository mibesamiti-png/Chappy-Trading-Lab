"""Exercise real dedicated venv and fixed artificial Parquet data only."""
import ast
import math
from datetime import date
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile
import unittest
import unittest.mock
import zipfile

SOURCE = Path(__file__).resolve().parents[1] / 'operations/runner_dist/START_GUI.pyw'
tree = ast.parse(SOURCE.read_text(encoding='utf-8'))
names = {'drive_allowed', 'local_folder', 'parquet_env', 'parquet_command', 'parquet_runtime', 'session_day_base', 'map_session_rows', 'aggregate_session_rows',
         'describe_session_horizon', 'integrated_pipeline_expected', 'integrated_pipeline_analyze',
         'synthetic_integrated_checkpoint', 'synthetic_prefix_checkpoint', 'footer_result', 'footer_member_bytes', 'synthetic_batch_adapter_checkpoint', 'batch_adapter_result', 'session_connection_result', 'session_connection_check'}
nodes = [n for n in tree.body if
         isinstance(n, ast.FunctionDef) and n.name in names or
         isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id in
                                         {'PARQUET_VERSION', 'PARQUET_WORKER', 'RESEARCH_HORIZONS', 'SESSION_EPOCH',
                                          'SESSION_FIRST', 'SESSION_LIMIT', 'PIPELINE_RECEIPT', 'PIPELINE_WORKER', 'PREFIX_WORKER', 'FOOTER_WORKER', 'FOOTER_LIMIT', 'BATCH_ADAPTER_WORKER'} for t in n.targets)]
scope = dict(date=date, math=math, Path=Path, os=os, re=re, stat=stat, sys=sys, json=json,
             subprocess=subprocess, zipfile=zipfile, atomic=lambda p, b: p.write_bytes(b))
exec(compile(ast.Module(body=nodes, type_ignores=[]), str(SOURCE), 'exec'), scope)


class ParquetTests(unittest.TestCase):
    def test_env_no_token(self):
        with unittest.mock.patch.dict(os.environ, {'GITHUB_TOKEN': 'invented', 'PIP_INDEX_URL': 'bad'}):
            result = scope['parquet_env']()
        self.assertNotIn('GITHUB_TOKEN', result)
        self.assertNotIn('PIP_INDEX_URL', result)

    def test_no_install_missing(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(ValueError, 'PARQUET_NOT_INSTALLED'):
                scope['parquet_runtime'](Path(d), False)
            self.assertEqual(list(Path(d).iterdir()), [])

    def test_unowned_directory(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'ctl_pyarrow_26_0_1'
            p.mkdir()
            with self.assertRaisesRegex(ValueError, 'PARQUET_UNOWNED_ENV'):
                scope['parquet_runtime'](Path(d), True)

    def test_actual_install_and_reuse(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)
            result = scope['parquet_runtime'](p, True)
            self.assertEqual(result['sum'], 10)
            self.assertEqual(result, scope['parquet_runtime'](p, False))
            self.assertEqual(result, json.loads((p / 'synthetic_parquet_probe.local.json').read_text()))
            integrated = scope['synthetic_integrated_checkpoint'](p)
            self.assertEqual(integrated['rows'],108)
            self.assertEqual(integrated['results']['1']['observed_pairs'],101)
            self.assertEqual(integrated['results']['30']['mean_return'],None)
            self.assertEqual(integrated,scope['synthetic_integrated_checkpoint'](p))
            self.assertEqual(integrated,json.loads((p/'synthetic_integrated_pipeline.local.json').read_text()))
            prefix=scope['synthetic_prefix_checkpoint'](p)
            self.assertEqual(prefix['report']['groups_read'],[0])
            self.assertEqual(prefix['physical_isolation'],'UNVERIFIED')
            python=p/'ctl_pyarrow_26_0_1'/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
            footer=scope['footer_result'](scope['parquet_command'](python,['-c',scope['FOOTER_WORKER'],'--fixture'],p,120,capture=True))
            self.assertEqual(footer['groups'],dict(before=1,crossing=1,reserved=1,unverified=0))
            self.assertEqual(footer['fields'][2]['name'],'OTHER')
            self.assertEqual(footer['row_decodes'],0)
            self.assertEqual(scope['synthetic_batch_adapter_checkpoint'](p),dict(scope='SYNTHETIC_ONLY',status='PASS'))
            self.assertEqual(scope['synthetic_batch_adapter_checkpoint'](p),dict(scope='SYNTHETIC_ONLY',status='PASS'))

    def test_session_connection(self):
        start=scope['session_day_base']('2025-07-07')+570
        schedule=[['2025-07-07',-240,65]]
        rows=[[start+i,100.125+i,100.375+i,99.875+i,100.25+i,i+1] for i in range(65) if i!=32]
        sample=dict(status='PASS',session=schedule[0],rows=rows)
        check=scope['session_connection_check']
        result=check(sample,schedule)
        self.assertEqual(result['status'],'PASS')
        self.assertEqual(result['horizons'],[1,5,15,30])
        self.assertEqual(scope['session_connection_result'](json.dumps(result).encode()),result)
        self.assertEqual(check(dict(status='NO_REGULAR_SAMPLE'),schedule)['status'],'NO_REGULAR_SAMPLE')
        self.assertEqual(check(dict(status='PASS',session=schedule[0],rows=rows[:2]),schedule)['status'],'INCOMPLETE_WINDOWS')
        with self.assertRaises(ValueError):
            check(dict(status='PASS',session=schedule[0],rows=[[start+65,*rows[0][1:]]]),schedule)
        with self.assertRaises(ValueError):
            check(sample,[['2025-07-08',-240,65]])

    def test_single_member_bytes(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'fixture.zip'
            data=b'invented data bytes'
            with zipfile.ZipFile(p,'w',compression=zipfile.ZIP_DEFLATED) as z:
                z.writestr('chosen.parquet',data)
                z.writestr('unused.parquet',b'not chosen')
            with zipfile.ZipFile(p) as z:
                crc=z.getinfo('chosen.parquet').CRC
            self.assertEqual(scope['footer_member_bytes'](p,'chosen.parquet',len(data),crc),data)
            with self.assertRaises(ValueError):
                scope['footer_member_bytes'](p,'chosen.parquet',len(data),crc^1)
            with self.assertRaises(ValueError):
                scope['footer_member_bytes'](p,'chosen.parquet',scope['FOOTER_LIMIT']+1,crc)


if __name__ == '__main__':
    import unittest.mock
    unittest.main()
