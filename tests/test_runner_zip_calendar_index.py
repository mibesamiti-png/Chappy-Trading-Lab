"""Bounded calendar projection and time normalization, invented data only."""
import ast
from datetime import date
import json
import hashlib
from pathlib import Path
import re
import sqlite3
import tempfile
import unittest
SOURCE=Path(__file__).resolve().parents[1]/'operations/runner_dist/START_GUI.pyw'
tree=ast.parse(SOURCE.read_text(encoding='utf-8'))
names={'session_day_base','map_session_rows','calendar_authorizer','calendar_query','calendar_clock','calendar_normalize','calendar_index_checkpoint','synthetic_calendar_probe'}
nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names or
       isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and (t.id.startswith('CALENDAR_') or t.id in ('SESSION_EPOCH','SESSION_FIRST','SESSION_LIMIT')) for t in n.targets)]
def metadata(value):
    p=Path(value)
    st=p.stat()
    return p,(st.st_dev,st.st_ino,st.st_size,st.st_mtime_ns)
scope=dict(date=date,json=json,hashlib=hashlib,re=re,sqlite3=sqlite3,local_folder=Path,
           index_file_metadata=metadata,INDEX_MAP_LIMIT=524288,atomic=lambda p,b:p.write_bytes(b))
exec(compile(ast.Module(body=nodes,type_ignores=[]),str(SOURCE),'exec'),scope)
class CalendarTests(unittest.TestCase):
    def test_fixture(self):
        scope['synthetic_calendar_probe']()
    def test_clock_and_period(self):
        normalize=scope['calendar_normalize']
        good=('2025-07-08',210,'13:30','17:00',-4)
        self.assertEqual(normalize([good]),[['2025-07-08',-240,210]])
        for row in [('2026-01-01',210,'13:30','17:00',-4),('2025-07-08',210,'14:30','18:00',-4),
                    ('2025-07-08',210,'13:30:01','17:00',-4),('2025-07-08',210,'13:30-04:00','17:00',-4),
                    ('2025-07-08',210,'2025-07-09T13:30','17:00',-4),('2025-07-08',0,'13:30','17:00',-4)]:
            with self.subTest(row=row),self.assertRaises(ValueError):
                normalize([row])
        with self.assertRaises(ValueError):
            normalize([good,good])
    def test_view_refused(self):
        db=sqlite3.connect(':memory:')
        try:
            db.execute('CREATE VIEW calendar AS SELECT 1')
            with self.assertRaises(ValueError):
                scope['calendar_query'](db)
        finally:
            db.close()
    def test_local_checkpoint_and_stale(self):
        with tempfile.TemporaryDirectory() as tmp:
            parent=Path(tmp)
            path=parent/'hf_light_index.sqlite'
            db=sqlite3.connect(path)
            db.execute('CREATE TABLE calendar(date TEXT,expected_minutes INTEGER,open_utc TEXT,close_utc TEXT,utc_offset_hours REAL)')
            db.execute("INSERT INTO calendar VALUES('2025-01-06',390,'14:30','21:00',-5)")
            db.commit()
            db.close()
            before=path.read_bytes()
            _,meta=metadata(str(path))
            mapping=dict(schema=1,scope='LOCAL_COLUMN_MAP_ONLY',research_access='LOCKED',market_member_reads=0,
                         application_table_queries=0,index_source=str(path),index_size=meta[2],index_mtime_ns=meta[3])
            dest=parent/'existing_index_column_map.local.json'
            dest.write_text(json.dumps(mapping))
            receipt=scope['calendar_index_checkpoint'](parent)
            self.assertEqual(receipt['sessions'],[['2025-01-06',-300,390]])
            self.assertEqual(path.read_bytes(),before)
            self.assertEqual(receipt['calendar_completeness'],'UNVERIFIED')
            mapping['index_size']+=1
            dest.write_text(json.dumps(mapping))
            with self.assertRaises(ValueError):
                scope['calendar_index_checkpoint'](parent)
if __name__=='__main__':
    unittest.main()
