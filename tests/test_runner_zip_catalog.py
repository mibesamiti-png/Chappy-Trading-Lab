"""Artificial on-disk ZIP catalog checks, no market data."""
import ast
import io
import json
import os
from pathlib import Path
import re
import stat
import struct
import tempfile
import unittest
from unittest.mock import patch
import zipfile
import warnings

SOURCE = Path(__file__).resolve().parents[1] / 'operations/runner_dist/START_GUI.pyw'
tree = ast.parse(SOURCE.read_text(encoding='utf-8'))
names = {'drive_allowed', 'local_folder', 'local_zip', 'zip_paths', 'read_folders',
         'catalog_bounds', 'CatalogView', 'catalog_file', 'catalog_registered'}
nodes = [n for n in tree.body if
         isinstance(n, (ast.FunctionDef, ast.ClassDef)) and n.name in names or
         isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and
             (t.id.startswith('CATALOG_') or t.id in {'ROLES', 'ZIP_LIMIT', 'SETTINGS_LIMIT'}) for t in n.targets)]
scope = dict(Path=Path, os=os, re=re, stat=stat, struct=struct, json=json,
             zipfile=zipfile, atomic=lambda p, b: p.write_bytes(b))
exec(compile(ast.Module(body=nodes, type_ignores=[]), str(SOURCE), 'exec'), scope)


class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.path = self.root / 'artificial.zip'

    def make(self, names=('A.parquet', '2026/locked.parquet', 'readme.txt'), zip64=False):
        with patch.object(zipfile, 'ZIP64_LIMIT', 100 if zip64 else zipfile.ZIP64_LIMIT):
            with zipfile.ZipFile(self.path, 'w', allowZip64=True) as z:
                for name in names:
                    z.writestr(name, b'x' * 256)
        return self.path

    def test_catalog_payload_never_opened(self):
        self.make()
        with patch.object(zipfile.ZipFile, 'open', side_effect=AssertionError('payload access')):
            a = scope['catalog_file'](str(self.path))
        self.assertEqual((a['entries'], a['locked_names'], a['other']), (3, 1, 1))
        self.assertEqual(a['parquet_candidates'][0]['member'], 'A.parquet')
        self.assertEqual(a['parquet_candidates'][0]['access'], 'LOCKED_UNVERIFIED_PERIOD')
        self.assertNotIn('locked.parquet', json.dumps(a))

    def test_zip64_directory(self):
        self.make(zip64=True)
        self.assertTrue(scope['catalog_file'](str(self.path))['zip64_directory'])

    def test_view_refuses_payload(self):
        view = scope['CatalogView'](io.BytesIO(b'0123456789'), 5, 10)
        view.seek(4)
        with self.assertRaises(ValueError):
            view.read(1)
        view.seek(5)
        self.assertEqual(view.read(5), b'56789')

    def test_unsafe_names(self):
        for name in ('../evil.parquet', '/x.parquet', 'C:/x.parquet'):
            self.make((name,))
            with self.assertRaisesRegex(ValueError, 'CATALOG_UNSAFE_NAME'):
                scope['catalog_file'](str(self.path))

    def test_duplicate(self):
        self.make(('A.parquet', 'a.parquet'))
        with self.assertRaisesRegex(ValueError, 'CATALOG_DUPLICATE'):
            scope['catalog_file'](str(self.path))

    def test_comment_rejected(self):
        self.make()
        with zipfile.ZipFile(self.path, 'a') as z:
            z.comment = b'not supported yet'
        with self.assertRaises(ValueError):
            scope['catalog_file'](str(self.path))

    def test_corrupt_end(self):
        self.path.write_bytes(b'x' * 100)
        with self.assertRaises(ValueError):
            scope['catalog_file'](str(self.path))

    def test_count_preflight(self):
        self.make()
        with self.path.open('rb') as f, patch.dict(scope, {'CATALOG_MAX_ENTRIES': 2}):
            with self.assertRaisesRegex(ValueError, 'CATALOG_DIRECTORY_LIMIT'):
                scope['catalog_bounds'](f)

    def test_persistence(self):
        self.make()
        (self.root / 'research_folders.local.json').write_text(json.dumps({'market_zips': [str(self.path)]}))
        self.assertEqual(scope['catalog_registered'](self.root), (1, 3, 1))
        receipt = json.loads((self.root / 'market_zip_catalog.local.json').read_text())
        self.assertEqual(receipt['research_access'], 'LOCKED')
        self.assertEqual(receipt['member_reads'], 0)

    def test_no_registration(self):
        with self.assertRaisesRegex(ValueError, 'CATALOG_NO_ZIP'):
            scope['catalog_registered'](self.root)


if __name__ == '__main__':
    unittest.main()
