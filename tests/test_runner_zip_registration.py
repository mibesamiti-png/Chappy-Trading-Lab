"""Synthetic tests for local metadata registration; no market files."""
import ast
import json
import os
from pathlib import Path
import re
import stat
import tempfile
import unittest

SOURCE = Path(__file__).resolve().parents[1] / 'operations/runner_dist/START_GUI.pyw'
NAMES = {'ROLES', 'FORMATS', 'LIMIT', 'ZIP_LIMIT', 'SETTINGS_LIMIT'}
FUNCTIONS = {'local_folder', 'local_zip', 'zip_paths', 'inventory', 'read_folders'}
tree = ast.parse(SOURCE.read_text(encoding='utf-8'))
nodes = [n for n in tree.body if
         isinstance(n, ast.FunctionDef) and n.name in FUNCTIONS or
         isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id in NAMES for t in n.targets)]
scope = dict(Path=Path, os=os, re=re, stat=stat, json=json)
exec(compile(ast.Module(body=nodes, type_ignores=[]), str(SOURCE), 'exec'), scope)


class RegistrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.a = self.root / 'clean_A.zip'
        self.b = self.root / 'clean_B.ZIP'
        for p in (self.a, self.b):
            p.write_bytes(b'not an archive: registration must not read contents')

    def test_multiple_and_duplicates(self):
        self.assertEqual(scope['zip_paths']([str(self.a), str(self.b), str(self.a)]),
                         [str(self.a), str(self.b)])

    def test_bad_paths(self):
        folder = self.root / 'folder.zip'
        folder.mkdir()
        for p in ('relative.zip', str(folder), str(self.root / 'fake.csv'),
                  str(self.root / '2026_holdout.zip')):
            with self.subTest(p=p), self.assertRaises((ValueError, OSError)):
                scope['local_zip'](p)

    def test_missing_file(self):
        with self.assertRaises(OSError):
            scope['local_zip'](str(self.root / 'missing.zip'))

    def test_symlink(self):
        link = self.root / 'link.zip'
        try:
            link.symlink_to(self.a)
        except OSError:
            self.skipTest('symlinks not permitted')
        with self.assertRaises(ValueError):
            scope['local_zip'](str(link))

    def test_cap(self):
        with self.assertRaises(ValueError):
            scope['zip_paths']([str(self.a)] * 33)

    def test_settings_old_and_new(self):
        p = self.root / 'settings.json'
        for obj in ({'market': str(self.root)}, {'market_zips': [str(self.a), str(self.b)]}, {}):
            p.write_text(json.dumps(obj), encoding='utf-8')
            self.assertEqual(scope['read_folders'](p), obj)

    def test_settings_invalid(self):
        p = self.root / 'settings.json'
        for obj in ({'market_zips': 'bad'}, {'market_zips': [1]}, {'unknown': 'x'}):
            p.write_text(json.dumps(obj), encoding='utf-8')
            with self.assertRaises(ValueError):
                scope['read_folders'](p)


if __name__ == '__main__':
    unittest.main()
