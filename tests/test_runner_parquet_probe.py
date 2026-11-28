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

SOURCE = Path(__file__).resolve().parents[1] / 'operations/runner_dist/START_GUI.pyw'
tree = ast.parse(SOURCE.read_text(encoding='utf-8'))
names = {'drive_allowed', 'local_folder', 'parquet_env', 'parquet_command', 'parquet_runtime', 'session_day_base', 'map_session_rows', 'aggregate_session_rows',
         'describe_session_horizon', 'integrated_pipeline_expected', 'integrated_pipeline_analyze',
         'synthetic_integrated_checkpoint'}
nodes = [n for n in tree.body if
         isinstance(n, ast.FunctionDef) and n.name in names or
         isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id in
                                         {'PARQUET_VERSION', 'PARQUET_WORKER', 'RESEARCH_HORIZONS', 'SESSION_EPOCH',
                                          'SESSION_FIRST', 'SESSION_LIMIT', 'PIPELINE_RECEIPT', 'PIPELINE_WORKER'} for t in n.targets)]
scope = dict(date=date, math=math, Path=Path, os=os, re=re, stat=stat, sys=sys, json=json,
             subprocess=subprocess, atomic=lambda p, b: p.write_bytes(b))
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


if __name__ == '__main__':
    import unittest.mock
    unittest.main()
