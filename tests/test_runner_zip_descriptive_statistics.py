"""Artificial descriptive statistics, no real inputs."""
import ast
import json
import math
from pathlib import Path
import tempfile
import unittest

SOURCE=Path(__file__).resolve().parents[1]/'operations/runner_dist/START_GUI.pyw'
tree=ast.parse(SOURCE.read_text(encoding='utf-8'))
names={'aggregate_session_rows','describe_session_horizon','synthetic_statistics_checkpoint'}
nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names or
       isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id in ('RESEARCH_HORIZONS','STATS_RECEIPT') for t in n.targets)]
scope=dict(json=json,math=math,local_folder=Path,atomic=lambda p,b:p.write_bytes(b))
exec(compile(ast.Module(body=nodes,type_ignores=[]),str(SOURCE),'exec'),scope)
describe=scope['describe_session_horizon']
def row(i,c,v=1):
    return (i,c,c,c,c,v)

class DescriptiveStatisticsTests(unittest.TestCase):
    def test_gap_and_session_boundary(self):
        result=describe([(5,[row(0,100),row(1,110),row(3,1000),row(4,900)]),
                         (2,[row(0,2),row(1,2)])],1)
        self.assertEqual(result['possible_pairs'],5)
        self.assertEqual(result['observed_pairs'],3)
        self.assertEqual(result['unobserved_pairs'],2)
        self.assertAlmostEqual(result['mean_return'],0)
        self.assertAlmostEqual(result['mean_absolute_return'],.2/3)
        self.assertEqual((result['positive'],result['negative'],result['zero']),(1,1,1))

    def test_known_horizon_close_and_volume(self):
        rows=[row(i,100+10*i,i+1) for i in range(10)]
        result=describe([(10,rows)],5)
        self.assertEqual(result['complete_bars'],2)
        self.assertEqual(result['observed_pairs'],1)
        self.assertAlmostEqual(result['mean_return'],50/140)
        self.assertEqual(result['volume_sum'],55)
        self.assertEqual(result['mean_volume'],27.5)
        self.assertIsNone(result['sample_return_sd'])

    def test_empty_and_short(self):
        result=describe([(4,[row(i,100) for i in range(4)])],5)
        self.assertEqual(result['tail_minutes'],4)
        self.assertEqual(result['complete_bars'],0)
        for k in ('mean_return','mean_absolute_return','sample_return_sd','mean_volume'):
            self.assertIsNone(result[k])

    def test_invalid_and_value_limit(self):
        for sessions,horizon in [([],1), ([(5,[row(0,1),row(0,1)])],1),
                                 ([(1,[row(0,10**19)])],1), ([(1,[row(0,1)])],3)]:
            with self.subTest(sessions=sessions,horizon=horizon),self.assertRaises(ValueError):
                describe(sessions,horizon)

    def test_fixture_checkpoint(self):
        with tempfile.TemporaryDirectory() as tmp:
            parent=Path(tmp)
            result=scope['synthetic_statistics_checkpoint'](parent)
            first=(parent/scope['STATS_RECEIPT']).read_bytes()
            self.assertEqual(scope['synthetic_statistics_checkpoint'](parent),result)
            self.assertEqual((parent/scope['STATS_RECEIPT']).read_bytes(),first)
            self.assertEqual(result['market_member_reads'],0)

if __name__=='__main__':
    unittest.main()
