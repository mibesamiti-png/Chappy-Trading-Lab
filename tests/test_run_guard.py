import importlib.util,json,pathlib,subprocess,sys,tempfile,unittest
SCRIPT=pathlib.Path(__file__).resolve().parents[1]/'scripts/run_guard.py'
spec=importlib.util.spec_from_file_location('run_guard',SCRIPT);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
class GuardTests(unittest.TestCase):
    def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.db=pathlib.Path(self.tmp.name)/'state.sqlite';self.g=module.RunGuard(self.db)
    def tearDown(self):self.tmp.cleanup()
    def child(self,*args):return subprocess.run([sys.executable,str(SCRIPT),*args,'--db',str(self.db)],capture_output=True,text=True)
    def test_second_process_cannot_acquire_active_owner(self):
        self.g.acquire('writer-a');self.assertEqual(self.child('acquire','--owner','writer-b').returncode,3);self.g.release('writer-a')
    def test_checkpoint_survives_fresh_process(self):
        self.g.acquire('writer-a');self.g.checkpoint('writer-a',{'task':'synthetic','stage':'saved'});r=self.child('inspect');self.assertEqual(r.returncode,0);self.assertEqual(json.loads(r.stdout)['guard']['checkpoint']['stage'],'saved')
    def test_foreign_release_and_checkpoint_are_rejected(self):
        self.g.acquire('writer-a')
        with self.assertRaises(module.LostLease):self.g.release('writer-b')
        with self.assertRaises(module.LostLease):self.g.checkpoint('writer-b',{})
        self.assertTrue(self.g.live('writer-a'))
    def test_expiry_never_steals_old_writer(self):
        self.g.acquire('writer-a')
        with self.g.connect() as c:c.execute("UPDATE guard SET deadline='2000-01-01T00:00:00+00:00'")
        with self.assertRaises(module.LostLease):self.g.live('writer-a')
        with self.assertRaises(module.Busy):self.g.acquire('writer-b')
        self.g.release('writer-a');self.g.acquire('writer-b')
    def test_simultaneous_contenders_have_one_winner(self):
        procs=[subprocess.Popen([sys.executable,str(SCRIPT),'acquire','--db',str(self.db),'--owner',x],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True) for x in ['a','b']]
        codes=[]
        for p in procs:p.communicate(timeout=15);codes.append(p.returncode)
        self.assertEqual(sorted(codes),[0,3])
    def test_released_run_can_resume_under_new_owner(self):
        self.g.acquire('old');self.g.release('old');self.assertEqual(self.child('acquire','--owner','new').returncode,0)
    def test_completed_revision_persists_and_is_idempotent(self):
        self.g.acquire('first');self.assertTrue(self.g.finish_task('first','synthetic-task','protocol-v1'));self.assertFalse(self.g.finish_task('first','synthetic-task','protocol-v1'));self.g.release('first');fresh=module.RunGuard(self.db);fresh.acquire('second');self.assertTrue(fresh.completed('synthetic-task','protocol-v1'));self.assertFalse(fresh.completed('synthetic-task','protocol-v2'))
    def test_foreign_writer_cannot_mark_task_done(self):
        self.g.acquire('owner')
        with self.assertRaises(module.LostLease):self.g.finish_task('other','task','v1')
        self.assertFalse(self.g.completed('task','v1'))
if __name__=='__main__':unittest.main()
