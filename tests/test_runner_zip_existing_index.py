"""Schema-only existing index intake; all fixtures are invented."""
import ast
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
import tempfile
import unittest

SOURCE=Path(__file__).resolve().parents[1]/'operations/runner_dist/START_GUI.pyw'
tree=ast.parse(SOURCE.read_text(encoding='utf-8'))
names={'drive_allowed','local_folder','index_file_metadata','index_schema_authorizer','existing_index_probe'}
nodes=[n for n in tree.body if
       isinstance(n,ast.FunctionDef) and n.name in names or
       isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id.startswith('INDEX_') for t in n.targets)]
scope=dict(Path=Path,os=os,re=re,sqlite3=sqlite3,stat=stat,json=json,atomic=lambda p,b:p.write_bytes(b))
exec(compile(ast.Module(body=nodes,type_ignores=[]),str(SOURCE),'exec'),scope)


class ExistingIndexTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.source=self.root/'hf_light_index.sqlite'
        db=sqlite3.connect(self.source)
        try:
            db.execute('CREATE TABLE monthly(month TEXT, value TEXT)')
            db.execute("INSERT INTO monthly VALUES ('2026-01','SEALED_CANARY')")
            db.execute('CREATE TABLE holdout_secret(value TEXT)')
            db.commit()
        finally:
            db.close()

    def test_schema_only_receipt_and_no_source_change(self):
        before=self.source.read_bytes()
        r=scope['existing_index_probe'](self.root,str(self.source))
        self.assertEqual(r['objects'],[{'name':'monthly','kind':'table'}])
        self.assertEqual(r['reserved_objects_omitted'],1)
        self.assertEqual(r['application_table_queries'],0)
        self.assertEqual(r['research_access'],'LOCKED')
        saved=(self.root/'existing_research_index.local.json').read_text()
        self.assertNotIn('SEALED_CANARY',saved)
        self.assertNotIn('holdout_secret',saved)
        self.assertEqual(json.loads(saved),r)
        self.assertEqual(self.source.read_bytes(),before)

    def test_authorizer_denies_rows_and_writes(self):
        db=sqlite3.connect(self.source)
        try:
            db.set_authorizer(scope['index_schema_authorizer'])
            self.assertEqual(len(db.execute("SELECT name,type FROM sqlite_schema WHERE type='table'").fetchall()),2)
            for sql in ('SELECT value FROM monthly','SELECT sql FROM sqlite_schema',
                        'DELETE FROM monthly','ATTACH DATABASE ":memory:" AS other'):
                with self.assertRaises(sqlite3.DatabaseError):
                    db.execute(sql)
        finally:
            db.close()

    def test_sidecar_and_wrong_name(self):
        p=Path(str(self.source)+'-wal')
        p.touch()
        with self.assertRaisesRegex(ValueError,'INDEX_SIDECAR_REFUSED'):
            scope['existing_index_probe'](self.root,str(self.source))
        p.unlink()
        with self.assertRaisesRegex(ValueError,'INDEX_NAME_REQUIRED'):
            scope['existing_index_probe'](self.root,str(self.root/'another.sqlite'))

    def test_invalid_database(self):
        self.source.write_bytes(b'x'*1024)
        with self.assertRaises(sqlite3.DatabaseError):
            scope['existing_index_probe'](self.root,str(self.source))


if __name__=='__main__':
    unittest.main()
