import importlib.util,pathlib,tempfile,unittest
P=pathlib.Path(__file__).resolve().parents[1]/'scripts/publication_gate.py';S=importlib.util.spec_from_file_location('gate',P);M=importlib.util.module_from_spec(S);S.loader.exec_module(M)
class GateTests(unittest.TestCase):
    def test_restricted_file_and_path_traversal(self):
        with tempfile.TemporaryDirectory() as d:self.assertEqual(len(M.check(d,['outputs/result.csv','../STATE.md'])),2)
    def test_allowed_file_still_scanned(self):
        with tempfile.TemporaryDirectory() as d:
            p=pathlib.Path(d)/'STATE.md';p.write_text('C:'+chr(92)+'Users'+chr(92)+'private-user'+chr(92)+'input',encoding='utf-8');self.assertTrue(M.check(d,['STATE.md']));p.write_text('Sanitized execution status only.',encoding='utf-8');self.assertFalse(M.check(d,['STATE.md']))
if __name__=='__main__':unittest.main()
