"""Explicit synthetic UTC session mapping and aggregation integration."""
import ast
from datetime import date
import json
from pathlib import Path
import tempfile
import unittest
SOURCE=Path(__file__).resolve().parents[1]/'operations/runner_dist/START_GUI.pyw'
tree=ast.parse(SOURCE.read_text(encoding='utf-8'))
names={'aggregate_session_rows','session_day_base','map_session_rows','synthetic_session_mapping_checkpoint'}
constants={'RESEARCH_HORIZONS','SESSION_MAP_RECEIPT','SESSION_EPOCH','SESSION_FIRST','SESSION_LIMIT'}
nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names or
       isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id in constants for t in n.targets)]
scope=dict(date=date,json=json,local_folder=Path,atomic=lambda p,b:p.write_bytes(b))
exec(compile(ast.Module(body=nodes,type_ignores=[]),str(SOURCE),'exec'),scope)
mapping=scope['map_session_rows']
daybase=scope['session_day_base']
class SessionMapTests(unittest.TestCase):
    def test_half_open_interval_and_closed_day(self):
        day='2025-01-06'
        start=daybase(day)+870
        valid=(10,12,9,11,1)
        rows=[(start+i,*valid) for i in (-1,0,389,390)]+[(daybase('2025-01-07')+870,*valid)]
        result=mapping([(day,-300,390)],rows)
        self.assertEqual(result['outside'],3)
        self.assertEqual(result['sessions'][0]['rows'],[(0,*valid),(389,*valid)])
    def test_explicit_offsets_and_short_close(self):
        a=daybase('2025-07-07')+810
        result=mapping([('2025-07-07',-240,210)],[(a+209,10,12,9,11,1),(a+210,10,12,9,11,1)])
        self.assertEqual(result['outside'],1)
        self.assertEqual(result['sessions'][0]['rows'][0][0],209)
    def test_invalid_schedule_and_period(self):
        for schedule in [[('2026-01-01',-300,390)],[('2025-01-06',0,390)],[('2025-01-06',-300,391)],
                         [('2025-01-06',-300,390)]*2,[('20250106',-300,390)]]:
            with self.subTest(schedule=schedule),self.assertRaises(ValueError):
                mapping(schedule,[])
    def test_invalid_rows_even_outside_session(self):
        schedule=[('2025-01-06',-300,390)]
        r=(daybase('2025-01-06')+869,10,12,9,11,1)
        for rows in [[r,r],[(scope['SESSION_LIMIT'],*r[1:])],[(r[0],10,8,9,11,1)]]:
            with self.subTest(rows=rows),self.assertRaises(ValueError):
                mapping(schedule,rows)
    def test_fixture_checkpoint(self):
        with tempfile.TemporaryDirectory() as tmp:
            parent=Path(tmp)
            result=scope['synthetic_session_mapping_checkpoint'](parent)
            self.assertEqual(result['bars_30m'],[13,13,7])
            first=(parent/scope['SESSION_MAP_RECEIPT']).read_bytes()
            self.assertEqual(scope['synthetic_session_mapping_checkpoint'](parent),result)
            self.assertEqual((parent/scope['SESSION_MAP_RECEIPT']).read_bytes(),first)
if __name__=='__main__':
    unittest.main()
