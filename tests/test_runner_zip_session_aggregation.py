"""Session-relative synthetic OHLCV aggregation and strict gaps."""
import ast
import json
from pathlib import Path
import tempfile
import unittest

SOURCE=Path(__file__).resolve().parents[1]/'operations/runner_dist/START_GUI.pyw'
tree=ast.parse(SOURCE.read_text(encoding='utf-8'))
names={'aggregate_session_rows','synthetic_horizon_expected','synthetic_horizon_checkpoint'}
nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names or
       isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id in ('RESEARCH_HORIZONS','HORIZON_RECEIPT') for t in n.targets)]
scope=dict(json=json,local_folder=Path,atomic=lambda p,b:p.write_bytes(b))
exec(compile(ast.Module(body=nodes,type_ignores=[]),str(SOURCE),'exec'),scope)
aggregate=scope['aggregate_session_rows']

class SessionAggregationTests(unittest.TestCase):
    def test_known_ohlcv(self):
        rows=[(i,10+i,13+i,8+i,11+i,i+1) for i in range(5)]
        self.assertEqual(aggregate(rows,5,5),dict(bars=[(0,10,17,8,15,15)],missing_windows=0,tail_minutes=0,missing_minutes=0))

    def test_missing_no_shift_no_imputation(self):
        rows=[(i,10,12,9,11,1) for i in range(12) if i!=2]
        result=aggregate(rows,12,5)
        self.assertEqual(result,dict(bars=[(5,10,12,9,11,5)],missing_windows=1,tail_minutes=2,missing_minutes=1))
        self.assertEqual(aggregate([],12,5)['missing_windows'],2)

    def test_separate_short_sessions(self):
        rows=[(i,10,12,9,11,1) for i in range(20)]
        self.assertEqual(aggregate(rows,20,30)['bars'],[])
        self.assertEqual(aggregate(rows,20,30)['tail_minutes'],20)
        self.assertEqual(aggregate(rows,20,15)['bars'],[(0,10,12,9,11,15)])

    def test_bad_input(self):
        r=(0,10,12,9,11,1)
        for rows,n,h in [([r,r],5,5),([r],0,5),([r],5,True),([r],5,3),
                         ([(5,10,12,9,11,1)],5,5),([(0,10,12,9,11,None)],5,5),
                         ([(0,10,12,9,11,-1)],5,5),([(0,10,8,9,11,1)],5,5),
                         ([(1,10,12,9,11,1),r],5,5)]:
            with self.subTest(rows=rows,n=n,h=h), self.assertRaises(ValueError):
                aggregate(rows,n,h)

    def test_fixed_checkpoint(self):
        with tempfile.TemporaryDirectory() as tmp:
            parent=Path(tmp)
            r=scope['synthetic_horizon_checkpoint'](parent)
            self.assertEqual(r['results'],scope['synthetic_horizon_expected']())
            dest=parent/scope['HORIZON_RECEIPT']
            first=dest.read_bytes()
            self.assertEqual(scope['synthetic_horizon_checkpoint'](parent),r)
            self.assertEqual(dest.read_bytes(),first)
            self.assertEqual(r['market_member_reads'],0)

if __name__=='__main__':
    unittest.main()
