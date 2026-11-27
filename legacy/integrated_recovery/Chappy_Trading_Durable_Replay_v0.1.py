"""R61: durable offline synthetic event journal, not an execution engine.
Dependencies: R60 and its pinned sibling modules. Python 3.10+, SQLite.
"""
import argparse, hashlib, importlib.util, json, os, sqlite3, subprocess, sys, tempfile
from pathlib import Path
P=Path(__file__).with_name('Chappy_Trading_Event_Replay_v0.1.py')
PIN='1a7fe6066ac887ebab3d5fbd3a717971e8d67a3e5d7fe8b986452823148fa033'
if hashlib.sha256(P.read_bytes()).hexdigest()!=PIN: raise RuntimeError('R60 hash mismatch')
spec=importlib.util.spec_from_file_location('r60',P); r=importlib.util.module_from_spec(spec);sys.modules[spec.name]=r;spec.loader.exec_module(r)

def require(ok,msg):
    if not ok: raise ValueError(msg)
def canonical(x): return json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False)
class Store:
    def __init__(self,path,create=False):
        self.path=Path(path); self.approved=None
        if create:
            # Never overwrite an existing database; exclusive creation.
            fd=os.open(self.path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600);os.close(fd)
        require(self.path.is_file(),'database missing')
        self.db=sqlite3.connect(self.path.resolve().as_uri()+'?mode=rw',uri=True,isolation_level=None,timeout=2)
        try:
            self.db.execute('PRAGMA synchronous=FULL')
            if create:
                require(self.db.execute('PRAGMA journal_mode=DELETE').fetchone()[0]=='delete','journal mode')
                self.db.executescript('BEGIN IMMEDIATE; CREATE TABLE records(seq INTEGER PRIMARY KEY, event_id TEXT NOT NULL UNIQUE, body TEXT NOT NULL); CREATE TABLE meta(id INTEGER PRIMARY KEY CHECK(id=1), pin TEXT NOT NULL, head TEXT NOT NULL, count INTEGER NOT NULL); INSERT INTO meta VALUES(1,\''+PIN+'\',\''+r.Z+'\',0); COMMIT;')
            require(self.db.execute('PRAGMA journal_mode').fetchone()[0]=='delete','unexpected journal mode')
            self.inspect()
        except BaseException:
            self.db.close();raise
    def close(self): self.db.close()
    def _read(self):
        m=self.db.execute('SELECT pin,head,count FROM meta WHERE id=1').fetchone();require(m is not None and m[0]==PIN,'metadata mismatch')
        rows=self.db.execute('SELECT seq,event_id,body FROM records ORDER BY seq').fetchall();require(len(rows)==m[2],'count mismatch');records=[]
        for i,(seq,eid,body) in enumerate(rows,1):
            rec=json.loads(body);require(seq==i and rec['event']['id']==eid and canonical(rec)==body,'record identity mismatch');records.append(rec)
        return r.restore(records,m[1])
    def inspect(self):
        self.db.execute('BEGIN')
        try: return self._read()
        finally: self.db.execute('ROLLBACK')
    def authorize(self,expected_head,expected_pending):
        # Offline append approval only; does not authorize new orders or attest external account.
        self.approved=None;v=self.inspect();require(v['head']==expected_head,'external head mismatch');require(v['result']['pending']==expected_pending,'pending review mismatch');self.approved=expected_head;return v
    def append(self,event,expected_head,crash=None):
        require(self.approved==expected_head and self.approved is not None,'explicit review required')
        self.db.execute('BEGIN IMMEDIATE')
        try:
            v=self._read();require(v['head']==expected_head,'stale writer')
            events=[x['event'] for x in v['records']];new=r.seal(events+[event]);rec=new['records'][-1]
            require(new['records'][:-1]==v['records'],'prefix mismatch')
            if crash=='before_insert':os._exit(71)
            self.db.execute('INSERT INTO records VALUES(?,?,?)',(len(events)+1,event['id'],canonical(rec)))
            if crash=='after_insert':os._exit(72)
            self.db.execute('UPDATE meta SET head=?,count=? WHERE id=1',(new['head'],len(events)+1))
            if crash=='after_meta':os._exit(73)
            self.db.execute('COMMIT')
            if crash=='after_commit':os._exit(74)
            self.approved=new['head'];return new
        except BaseException:
            self.approved=None
            if self.db.in_transaction:self.db.execute('ROLLBACK')
            raise

def worker(path,idx,case,crash):
    ev=r.fixture(case=='cancel');s=Store(path);v=s.inspect();s.authorize(v['head'],v['result']['pending']);s.append(ev[idx],v['head'],crash);s.close()

def self_test():
    tests=[];examples={}
    def ck(n,a,b=True):
        if a!=b:raise AssertionError((n,a,b))
        tests.append({'name':n,'pass':True})
    def reject(n,f):
        try:f()
        except (ValueError,KeyError,TypeError,sqlite3.Error,FileExistsError):ck(n,True)
        else:ck(n,False)
    with tempfile.TemporaryDirectory() as td:
        root=Path(td)
        for case in ('normal','cancel'):
            ev=r.fixture(case=='cancel');ref=r.seal(ev);p=root/(case+'.db');s=Store(p,True);v=s.inspect();ck(case+' empty',v['head'],r.Z);reject(case+' unopened review',lambda:s.append(ev[0],r.Z));s.authorize(r.Z,[])
            for i,e in enumerate(ev):
                v=s.append(e,v['head']);ck(case+' persisted prefix '+str(i+1),v,r.seal(ev[:i+1]))
            s.close();s=Store(p);ck(case+' reopen',s.inspect(),ref);reject(case+' reopen needs review',lambda:s.append(ev[-1],ref['head']));reject(case+' incorrect external head',lambda:s.authorize(r.Z,[]));s.authorize(ref['head'],[]);reject(case+' incorrect pending review',lambda:s.authorize(ref['head'],['unknown']));require(s.approved is None,'failed review must clear approval');s.close();reject(case+' existing DB protected',lambda:Store(p,True));examples[case]={'events':len(ev),'final_cash_cents':ref['result']['cash_cents'],'held':ref['result']['held'],'pending':ref['result']['pending'],'head':ref['head']}
        # Kill a real subprocess at four precise boundaries of an entry fill and a cancel.
        for case,kind in [('normal','fill'),('cancel','cancel')]:
            ev=r.fixture(case=='cancel');idx=next(i for i,e in enumerate(ev) if e['kind']==kind);before=r.seal(ev[:idx]);after=r.seal(ev[:idx+1]);
            for phase,code in [('before_insert',71),('after_insert',72),('after_meta',73),('after_commit',74)]:
                p=root/(case+phase+'.db');s=Store(p,True);v=s.authorize(r.Z,[])
                for e in ev[:idx]:v=s.append(e,v['head'])
                s.close();proc=subprocess.run([sys.executable, *(['-O'] if not __debug__ else []), __file__,'--worker',str(p),str(idx),case,phase],capture_output=True,timeout=20);ck(case+phase+' exit',proc.returncode,code)
                s=Store(p);v=s.inspect();target=after if phase=='after_commit' else before;ck(case+phase+' recovered state',v,target);reject(case+phase+' cannot auto append',lambda:s.append(ev[idx],v['head']));s.authorize(v['head'],v['result']['pending'])
                if phase=='after_commit':reject(case+phase+' retry duplicate',lambda:s.append(ev[idx],v['head']));ck(case+phase+' unchanged',s.inspect(),after)
                else:ck(case+phase+' retry once',s.append(ev[idx],v['head']),after)
                examples[case+'_'+phase]={'exit':code,'committed':phase=='after_commit','pending_on_restart':v['result']['pending'],'cash_cents_on_restart':v['result']['cash_cents'],'recovered_head':v['head']};s.close()
        p=root/'writers.db';a=Store(p,True);b=Store(p);a.authorize(r.Z,[]);b.authorize(r.Z,[]);ev=r.fixture();v=a.append(ev[0],r.Z);reject('stale writer',lambda:b.append(ev[0],r.Z));ck('stale writer no change',b.inspect(),v);b.authorize(v['head'],[]);reject('invalid event rollback',lambda:b.append(ev[0],v['head']));ck('rollback preserves state',b.inspect(),v);a.close();b.close()
        for field in ('body','count','head','seq'):
            p=root/(field+'.db');s=Store(p,True);s.authorize(r.Z,[]);v=s.append(ev[0],r.Z);s.close();d=sqlite3.connect(p)
            sql={'body':"UPDATE records SET body='{}'",'count':'UPDATE meta SET count=0','head':"UPDATE meta SET head='wrong'",'seq':'UPDATE records SET seq=2'}[field];d.execute(sql);d.commit();d.close();reject('tamper '+field,lambda:Store(p))
        # A coherent tail deletion is internally consistent, but old external head rejects it.
        p=root/'truncate.db';s=Store(p,True);s.authorize(r.Z,[]);v=s.append(ev[0],r.Z);v2=s.append(ev[1],v['head']);s.close();d=sqlite3.connect(p);d.execute('DELETE FROM records WHERE seq=2');d.execute('UPDATE meta SET count=1,head=?',(v['head'],));d.commit();d.close();s=Store(p);ck('coherent truncate internally valid',s.inspect(),v);reject('external head detects truncate',lambda:s.authorize(v2['head'],[]));s.close()
    return {'test_count':len(tests),'tests':tests,'examples':examples}
if __name__=='__main__':
    ap=argparse.ArgumentParser();g=ap.add_mutually_exclusive_group(required=True);g.add_argument('--self-test',action='store_true');g.add_argument('--example',action='store_true');g.add_argument('--worker',nargs=4);a=ap.parse_args()
    if a.worker:worker(a.worker[0],int(a.worker[1]),a.worker[2],a.worker[3])
    else:
        res=self_test();print(json.dumps(res['examples'] if a.example else {k:v for k,v in res.items() if k!='examples'},sort_keys=True,indent=2))
