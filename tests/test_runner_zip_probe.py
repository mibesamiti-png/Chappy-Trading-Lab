"""Synthetic ZIP and period gate tests; no market inputs."""
import ast
import csv
import hashlib
import io
import json
from datetime import date
from pathlib import Path
import re
import stat
import tempfile
import unittest
import warnings
import zipfile

SOURCE = Path(__file__).resolve().parents[1] / 'operations/runner_dist/START_GUI.pyw'
tree = ast.parse(SOURCE.read_text(encoding='utf-8'))
nodes = [n for n in tree.body if
         isinstance(n, ast.FunctionDef) and (n.name.startswith('probe_') or n.name.startswith('synthetic_')) or
         isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id.startswith('PROBE_') for t in n.targets)]
def atomic(path, data):
    path.write_bytes(data)
scope = dict(zipfile=zipfile, io=io, stat=stat, csv=csv, date=date, re=re,
             hashlib=hashlib, json=json, atomic=atomic)
exec(compile(ast.Module(body=nodes, type_ignores=[]), str(SOURCE), 'exec'), scope)


def archive(entries, compression=zipfile.ZIP_STORED):
    b = io.BytesIO()
    with zipfile.ZipFile(b, 'w', compression=compression) as z:
        for name, raw in entries:
            z.writestr(name, raw)
    return b.getvalue()


class ProbeTests(unittest.TestCase):
    def test_roundtrip(self):
        result = scope['synthetic_zip_probe']()
        self.assertEqual((result['entries'], result['rows'], result['sum']), (2, 3, 10))
        self.assertEqual(result['period_gate'], 'PASS')

    def test_checkpoint(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'receipt.json'
            self.assertEqual(scope['synthetic_probe_checkpoint'](p), json.loads(p.read_text()))

    def test_selected_only(self):
        a = archive([('a.csv', b'one'), ('b.csv', b'two')])
        self.assertEqual(scope['probe_read_member'](a, 'b.csv'), b'two')
        with self.assertRaises(ValueError):
            scope['probe_read_member'](a, 'missing.csv')

    def test_path_rejections(self):
        for name in ('../x', '/x', 'a/../x', 'C:/x', 'a\\x', 'a//b'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                scope['probe_zip_catalog'](archive([(name, b'x')]))

    def test_duplicate(self):
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            for names in (('a', 'a'), ('A', 'a')):
                with self.assertRaises(ValueError):
                    scope['probe_zip_catalog'](archive([(n, b'x') for n in names]))

    def test_symlink(self):
        info = zipfile.ZipInfo('link')
        info.create_system = 3
        info.external_attr = (stat.S_IFLNK | 0o777) << 16
        with self.assertRaises(ValueError):
            scope['probe_zip_catalog'](archive([(info, b'x')]))

    def test_ratio_and_member_limit(self):
        with self.assertRaises(ValueError):
            scope['probe_zip_catalog'](archive([('a', b'0' * 200000)], zipfile.ZIP_DEFLATED))
        with self.assertRaises(ValueError):
            scope['probe_zip_catalog'](archive([('a', b'0' * (512 * 1024 + 1))]))

    def test_count_limit(self):
        with self.assertRaises(ValueError):
            scope['probe_zip_catalog'](archive([(str(n), b'x') for n in range(129)]))

    def test_corrupt_zip(self):
        with self.assertRaises(zipfile.BadZipFile):
            scope['probe_zip_catalog'](b'not a ZIP')

    def test_period_boundary(self):
        self.assertEqual(scope['probe_period_rows'](b'date,value\n2025-12-31,7\n'), {'rows': 1, 'sum': 7})
        for row in ('2026-01-01,1', '2027-01-01,1', '2025-02-30,1', '20250101,1'):
            with self.subTest(row=row), self.assertRaises(ValueError):
                scope['probe_period_rows'](('date,value\n' + row + '\n').encode())

    def test_mixed_period_refusal(self):
        with self.assertRaises(ValueError):
            scope['probe_period_rows'](b'date,value\n2025-12-31,2\n2026-01-01,3\n')


if __name__ == '__main__':
    unittest.main()
