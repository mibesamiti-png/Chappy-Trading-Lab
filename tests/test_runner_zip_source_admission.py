"""Source admission checks on invented receipts. No archive or market data."""
import ast
import hashlib
import json
from pathlib import Path
from datetime import date
import tempfile
import unittest
SOURCE=Path(__file__).resolve().parents[1]/'operations/runner_dist/START_GUI.pyw'
tree=ast.parse(SOURCE.read_text(encoding='utf-8'))
names={'source_gate_receipt','session_day_base'}
nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names or
       isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id in ('SOURCE_GATE_RECEIPT','CALENDAR_RECEIPT','CALENDAR_FIRST','CALENDAR_LAST','CALENDAR_MAX','QUALITY_MONTHS','SESSION_EPOCH','SESSION_FIRST','SESSION_LIMIT') for t in n.targets)]
rows=[dict(archive_index=0,member='old_2025.parquet',size=123,crc32=42)]
scope=dict(Path=Path,date=date,json=json,hashlib=hashlib,local_folder=Path,
           INDEX_MAP_LIMIT=524288,QUALITY_RECEIPT_LIMIT=1048576,
           quality_catalog_rows=lambda _:('catalog',rows),load_market_candidates=lambda _:('catalog',rows),
           index_file_metadata=lambda _: (Path('invented'),(0,0,100,1)),atomic=lambda p,b:p.write_bytes(b))
exec(compile(ast.Module(body=nodes,type_ignores=[]),str(SOURCE),'exec'),scope)
class SourceGateTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root=Path(temp.name)
        self.common=dict(schema=1,research_access='LOCKED',market_member_reads=0)
        self.mapping=dict(self.common,scope='LOCAL_COLUMN_MAP_ONLY',application_table_queries=0,
                          catalog_sha256='catalog',index_source='invented',index_size=100,index_mtime_ns=1)
        digest=self.write('existing_index_column_map.local.json',self.mapping)
        self.selection=dict(self.common,scope='LOCAL_RETROSPECTIVE_MONTHLY_SELECTION',catalog_sha256='catalog',
                            index_map_sha256=digest,month_start='2022-03',month_end='2025-12',
                            holdout_evaluation='NOT_PERFORMED',physical_period_isolation='UNVERIFIED',selected=[dict(rows[0])])
        self.calendar=dict(self.common,scope='LOCAL_CALENDAR_METADATA',index_map_sha256=digest,
                           date_start='2022-03-07',date_end='2025-12-31',
                           holdout_evaluation='NOT_PERFORMED',physical_period_isolation='UNVERIFIED',
                           sessions=[['2025-07-08',-240,210]])
        self.write('market_monthly_quality_selection.local.json',self.selection)
        self.write(scope['CALENDAR_RECEIPT'],self.calendar)
    def write(self,name,obj):
        raw=json.dumps(obj,sort_keys=True).encode()
        (self.root/name).write_bytes(raw)
        return hashlib.sha256(raw).hexdigest()
    def test_consistent_but_locked(self):
        report=scope['source_gate_receipt'](self.root)
        self.assertEqual(report['metadata_consistency'],'PASS')
        self.assertEqual(report['research_access'],'LOCKED')
        self.assertEqual(report['candidate_count'],1)
        self.assertEqual(report,scope['source_gate_receipt'](self.root))
    def test_reject_identity_mismatch(self):
        self.selection['selected'][0]['crc32']=43
        self.write('market_monthly_quality_selection.local.json',self.selection)
        with self.assertRaises(ValueError):
            scope['source_gate_receipt'](self.root)
    def test_reject_fake_unlock(self):
        self.selection['physical_period_isolation']='VERIFIED'
        self.write('market_monthly_quality_selection.local.json',self.selection)
        with self.assertRaises(ValueError):
            scope['source_gate_receipt'](self.root)
    def test_reject_calendar_outside_period(self):
        self.calendar['sessions']=[['2026-01-01',-300,390]]
        self.write(scope['CALENDAR_RECEIPT'],self.calendar)
        with self.assertRaises(ValueError):
            scope['source_gate_receipt'](self.root)
    def test_reject_stale_map(self):
        self.calendar['index_map_sha256']='different'
        self.write(scope['CALENDAR_RECEIPT'],self.calendar)
        with self.assertRaises(ValueError):
            scope['source_gate_receipt'](self.root)
if __name__=='__main__':
    unittest.main()
