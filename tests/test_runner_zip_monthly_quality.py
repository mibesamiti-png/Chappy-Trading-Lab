"""Invented mixed-month index and metadata selection tests."""
import ast
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
import tempfile
import unittest
from unittest.mock import patch

SOURCE=Path(__file__).resolve().parents[1]/'operations/runner_dist/START_GUI.pyw'
tree=ast.parse(SOURCE.read_text(encoding='utf-8'))
names={'quality_authorizer','quality_read_index','quality_catalog_rows','quality_select','quality_index_run',
       'auto_market_batch','candidate_filename_symbols','index_file_metadata','local_folder','drive_allowed'}
nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names or
       isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and
       (t.id.startswith(('QUALITY_','INDEX_','CATALOG_')) or t.id=='SELECTION_MAX') for t in n.targets)]
scope=dict(Path=Path,os=os,re=re,stat=stat,sqlite3=sqlite3,hashlib=hashlib,json=json,atomic=lambda p,b:p.write_bytes(b))
exec(compile(ast.Module(body=nodes,type_ignores=[]),str(SOURCE),'exec'),scope)

class QualityTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.source=self.root/'hf_light_index.sqlite'
        db=sqlite3.connect(self.source)
        try:
            db.execute('CREATE TABLE symbols(ticker TEXT,member TEXT,member_bytes INTEGER,member_crc32 TEXT,last_datetime_utc TEXT)')
            db.execute('CREATE TABLE monthly_coverage(ticker TEXT,month TEXT,observed_regular_minutes INTEGER,scheduled_minutes_in_observed_span INTEGER)')
            db.executemany('INSERT INTO symbols VALUES(?,?,?,?,?)',[
                ('AAA','AAA_clean_1min.parquet',100,'000000ab','SEALED_CANARY'),
                ('BBB','BBB_clean_1min.parquet',100,'000000bc','SEALED_CANARY'),
                ('CCC','CCC_clean_1min.parquet',100,'00000000','SEALED_CANARY')])
            db.executemany('INSERT INTO monthly_coverage VALUES(?,?,?,?)',[
                ('AAA','2025-11',95,100),('AAA','2025-12',90,100),
                ('BBB','2025-12',30,100),('CCC','2025-12',100,100),
                ('AAA','2026-01',999999,999999),('BBB','2026-01',999999,999999)])
            db.commit()
        finally:
            db.close()
        self.rows=[dict(archive_index=0,member=t+'_clean_1min.parquet',size=100,crc32=crc)
                   for t,crc in [('AAA',0xab),('BBB',0xbc),('CCC',0xcd)]]

    def test_fixed_months_and_identity(self):
        identity,monthly=scope['quality_read_index'](self.source)
        self.assertEqual(len(monthly),4)
        self.assertNotIn('SEALED_CANARY',repr(identity))
        self.assertNotIn('999999',repr(monthly))
        r=scope['quality_select'](self.rows,identity,monthly,32,42,2,9000)
        self.assertEqual(r['metadata_matched_count'],2)
        self.assertEqual(r['eligible_count'],1)
        self.assertEqual(r['selected'][0]['ticker'],'AAA')
        self.assertEqual(r['selected'][0]['observed'],185)

    def test_holdout_and_duplicate_refusal(self):
        identity,monthly=scope['quality_read_index'](self.source)
        with self.assertRaisesRegex(ValueError,'QUALITY_PERIOD_REFUSED'):
            scope['quality_select'](self.rows,identity,monthly+[('AAA','2026-01',1,1)],32,42,1,0)
        r=scope['quality_select'](self.rows,identity,monthly+[monthly[0]],32,42,1,9000)
        self.assertEqual(r['eligible_count'],0)

    def test_columns_denied(self):
        db=sqlite3.connect(self.source)
        try:
            db.set_authorizer(scope['quality_authorizer'])
            for sql in ('SELECT last_datetime_utc FROM symbols','DELETE FROM symbols','SELECT sql FROM sqlite_schema'):
                with self.assertRaises(sqlite3.DatabaseError):
                    db.execute(sql)
        finally:
            db.close()

    def test_receipt_and_stale(self):
        st=self.source.stat()
        mapping=dict(schema=1,scope='LOCAL_COLUMN_MAP_ONLY',research_access='LOCKED',application_table_queries=0,
                     index_source=str(self.source),index_size=st.st_size,index_mtime_ns=st.st_mtime_ns,catalog_sha256='a'*64)
        (self.root/'existing_index_column_map.local.json').write_text(json.dumps(mapping))
        before=self.source.read_bytes()
        with patch.dict(scope,{'quality_catalog_rows':lambda _:('a'*64,self.rows),'load_market_candidates':lambda _:('a'*64,[])}):
            r=scope['quality_index_run'](self.root,32,42,2,9000)
            self.assertEqual(r['research_access'],'LOCKED')
            self.assertEqual(r['market_member_reads'],0)
            self.assertEqual(r['physical_period_isolation'],'UNVERIFIED')
            self.assertEqual(r,json.loads((self.root/'market_monthly_quality_selection.local.json').read_text()))
            with self.source.open('ab') as f:
                f.write(b'x')
            with self.assertRaisesRegex(ValueError,'QUALITY_STALE'):
                scope['quality_index_run'](self.root,32,42,2,9000)
        self.assertEqual(self.source.read_bytes()[:-1],before)

if __name__=='__main__':
    unittest.main()
