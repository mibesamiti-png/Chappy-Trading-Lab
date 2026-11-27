"""Paper-only durability study. No market connection. Run with a NEW output directory.
Requires Integrated Replay v0.1 and its dependencies beside this file.
An independent SQLite checkpoint and a process lock protect the journal. A prepared
checkpoint admits exactly the old or new head after interruption; this cannot distinguish
an uncommitted write from malicious rollback to the old head during the prepare window.
"""
import csv, importlib.util, json, os, signal, sqlite3, subprocess, sys, tempfile
from pathlib import Path
P=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('durability_integrated',P/'Chappy_Trading_Integrated_Replay_v0.1.py'); r=importlib.util.module_from_spec(spec);sys.modules[spec.name]=r;spec.loader.exec_module(r)

class Lock:
    def __init__(self,path):
        self.f=open(path,'a+b')
        try:
            if os.name=='nt':
                import msvcrt
                self.f.seek(0,2)
                if self.f.tell()==0:self.f.write(b'0');self.f.flush()
                self.f.seek(0);msvcrt.locking(self.f.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(self.f.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BaseException:self.f.close();raise
    def close(self):self.f.close()

def pair(j):return (j.seq,j.head)
def crash(stage,at):
    if stage==at:
        if os.name=='posix':os.kill(os.getpid(),signal.SIGKILL)
        os._exit(91)

class Durable:
    def __init__(self,db,anchor,*,create=False):
        self.dbpath=Path(db).resolve();self.apath=Path(anchor).resolve();self.j=None;self.a=None;self.failed=False
        if self.dbpath==self.apath:raise ValueError('separate checkpoint required')
        self.lock=Lock(str(self.apath)+'.lock')
        try:
            if create:
                if self.dbpath.exists() or self.apath.exists():raise FileExistsError('refuse overwrite')
                self.j=r.Journal(self.dbpath)
                self.a=sqlite3.connect(self.apath)
                self.a.execute('PRAGMA synchronous=FULL')
                self.a.execute('CREATE TABLE checkpoint(id INTEGER PRIMARY KEY CHECK(id=1), oldseq INTEGER NOT NULL, oldhead TEXT NOT NULL, newseq INTEGER, newhead TEXT)')
                self.a.execute('CREATE TABLE reconciliation(id INTEGER PRIMARY KEY, outcome TEXT NOT NULL, oldseq INTEGER NOT NULL, oldhead TEXT NOT NULL, newseq INTEGER NOT NULL, newhead TEXT NOT NULL)');self.a.execute('INSERT INTO checkpoint VALUES(1,?,?,NULL,NULL)',pair(self.j));self.a.commit();self.outcome='CREATED'
            else:
                if not self.dbpath.is_file() or not self.apath.is_file():raise ValueError('journal or checkpoint missing')
                self.a=sqlite3.connect(self.apath.as_uri()+'?mode=rw',uri=True);self.a.execute('PRAGMA synchronous=FULL')
                # Verify checkpoint before opening the journal; Journal's replay validates every row.
                row=self.a.execute('SELECT oldseq,oldhead,newseq,newhead FROM checkpoint WHERE id=1').fetchone()
                if not row:raise ValueError('missing checkpoint row')
                old=tuple(row[:2]);new=tuple(row[2:]);
                if (new[0] is None)!=(new[1] is None) or (new[0] is not None and new[0]!=old[0]+1):raise ValueError('invalid prepared checkpoint')
                with sqlite3.connect(self.dbpath.as_uri()+'?mode=rw',uri=True) as probe:
                    if not probe.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='journal'").fetchone():raise ValueError('journal table missing')
                probe.close()
                self.j=r.Journal(self.dbpath);actual=pair(self.j)
                if actual==old:self.outcome='PREPARED_OLD' if new[0] is not None else 'CLEAN'
                elif actual==new:self.outcome='PREPARED_NEW'
                else:raise ValueError('checkpoint head mismatch')
                if new[0] is not None:
                    with self.a:
                        self.a.execute('INSERT INTO reconciliation(outcome,oldseq,oldhead,newseq,newhead) VALUES(?,?,?,?,?)',(self.outcome,*old,*new))
                        self.a.execute('UPDATE checkpoint SET oldseq=?,oldhead=?,newseq=NULL,newhead=NULL WHERE id=1',actual)
                self.j.requires_recovery=True # even an empty journal reopened must be reviewed
        except BaseException:self.close();raise
    def _checkpoint(self,old,new=(None,None)):
        with self.a:
            cur=self.a.execute('UPDATE checkpoint SET oldseq=?,oldhead=?,newseq=?,newhead=? WHERE id=1',(*old,*new))
            if cur.rowcount!=1:raise ValueError('checkpoint update failed')
    @property
    def g(self):return self.j.g
    def send(self,kind,now,*,inject=None,**kw):
        if self.failed:raise RuntimeError('reopen and recover required')
        j=self.j
        if j.requires_recovery and kind!='recover':raise ValueError('restart requires recovery')
        e=json.loads(r.canonical(dict(kind=kind,now=now,**kw)))
        try:
            j.db.execute('BEGIN IMMEDIATE')
            last=j.db.execute('SELECT seq,chain FROM journal ORDER BY seq DESC LIMIT 1').fetchone() or (0,r.ZERO)
            if last!=pair(j):raise ValueError('stale writer')
            j.g.apply(e);state=r.digest(j.g.state());seq=j.seq+1;head=r.digest([j.head,seq,e,state]);old=pair(j);new=(seq,head)
            crash('before_prepare',inject)
            if inject=='checkpoint_error':raise OSError('injected checkpoint write failure')
            self._checkpoint(old,new)
            crash('after_prepare',inject)
            j.db.execute('INSERT INTO journal VALUES(?,?,?,?)',(seq,r.canonical(e),state,head))
            crash('after_insert',inject)
            j.db.commit()
            crash('after_commit',inject)
            if inject=='finalize_error':raise OSError('injected checkpoint finalize failure')
            self._checkpoint(new)
            crash('after_finalize',inject)
            j.seq,j.head=new
            if kind=='recover':j.requires_recovery=False
        except BaseException:
            self.failed=True;j.db.rollback();j.reload();j.requires_recovery=True;raise
    def close(self):
        try:
            if self.j:self.j.close()
        finally:
            try:
                if self.a:self.a.close()
            finally:self.lock.close()
    def __enter__(self):return self
    def __exit__(self,*exc):self.close()

def status(g,now):
    if now<g.clock:raise ValueError('backdated display')
    legs=[];prices={}
    for key,l in sorted(g.book.legs.items()):
        quote=g.quotes.get(l.symbol);age=now-quote[0] if quote else None
        # Restored quotes remain historical until a post-recovery fresh quote arrives.
        fresh=bool(quote and 0<=age<=r.f.QUOTE_MAX and g.session and g.session[0]<=quote[0]<=now<g.session[1] and (not g.exit or quote[0]>g.exit[0]))
        if fresh:prices[l.symbol]=quote[1]
        legs.append(dict(symbol=l.symbol,side=l.side,qty=l.qty,last_price=quote[1] if quote else None,quote_stamp=quote[0] if quote else None,age=age,fresh=fresh))
    complete=all(x['fresh'] for x in legs)
    return dict(now=now,cash=g.book.cash,legs=legs,exit_pending=bool(g.exit),fault=g.fault,equity=g.book.equity(prices) if complete else None,valuation='FLAT' if not legs else 'FRESH_ESTIMATE' if complete else 'INCOMPLETE',exposure='UNRESOLVED' if legs and g.exit else 'OPEN' if legs else 'FLAT')

def setup(d,kind):
    for i,k in enumerate(d.g.symbols):d.send('bar',1200+i,symbol=k,end=300,price=1000)
    d.send('request',1202,orders=[('A',1,300),('B',-1,300)])
    d.send('quote',1203,symbol='A',price=1000,stamp=1203)
    if kind=='exit':
        d.send('quote',1204,symbol='B',price=1000,stamp=1204);d.send('recover',1205)

def event(kind):return dict(kind='quote',now=1204 if kind=='entry' else 1206,symbol='B' if kind=='entry' else 'A',price=1000,stamp=1204 if kind=='entry' else 1206)

def worker(db,a,kind,stage):
    # Start a fresh process; no restart bypass.
    with Durable(db,a,create=True) as d:
        setup(d,kind);d.send(**event(kind),inject=stage)

def tests(out):
    rows=[];views=[]
    with tempfile.TemporaryDirectory() as td:
        root=Path(td)
        def paths(name):return root/(name+'.db'),root/(name+'.anchor.db')
        def row(name,**kw):rows.append(dict(case=name,result='PASS',**kw))
        for kind in ('entry','exit'):
            for stage in ('before_prepare','after_prepare','after_insert','after_commit','after_finalize'):
                name=kind+'_'+stage;db,a=paths(name)
                cp=subprocess.run([sys.executable,__file__,'--worker',str(db),str(a),kind,stage],capture_output=True,timeout=20)
                assert cp.returncode==(-signal.SIGKILL if os.name=='posix' else 91),cp.stderr.decode()
                committed=stage in ('after_commit','after_finalize')
                with Durable(db,a) as d:
                    expected={'before_prepare':'CLEAN','after_prepare':'PREPARED_OLD','after_insert':'PREPARED_OLD','after_commit':'PREPARED_NEW','after_finalize':'CLEAN'}[stage]
                    assert d.outcome==expected
                    recorded=d.a.execute('SELECT outcome FROM reconciliation').fetchall();assert recorded==([(expected,)] if expected.startswith('PREPARED') else [])
                    assert d.j.seq==(5 if kind=='entry' else 7)+int(committed)
                    assert len(d.g.book.fills)==((2 if committed else 0) if kind=='entry' else (3 if committed else 2))
                    pre=len(d.g.book.legs);fills=len(d.g.book.fills)
                    try:d.send('tick',1210)
                    except ValueError:pass
                    else:raise AssertionError('recovery bypass')
                    d.send('recover',1210);views.append(dict(case=name,phase='recovered',**status(d.g,1210)))
                    d.send('quote',1211,symbol='A',price=1000,stamp=1211);d.send('quote',1212,symbol='B',price=1000,stamp=1212)
                    assert not d.g.book.legs and d.g.pending is None;r.ls.audit(d.g.book)
                    assert len(d.g.book.fills)==fills+pre
                    row(name,checkpoint=expected,committed=committed,open_before_recovery=pre,final_fills=len(d.g.book.fills))
        for mode in ('checkpoint_error','finalize_error','sql_abort'):
            db,a=paths(mode)
            with Durable(db,a,create=True) as d:
                setup(d,'entry')
                if mode=='sql_abort':d.j.db.execute("CREATE TRIGGER reject_insert BEFORE INSERT ON journal BEGIN SELECT RAISE(ABORT,'injected'); END");d.j.db.commit()
                try:d.send(**event('entry'),inject=mode)
                except (OSError,sqlite3.DatabaseError):pass
                else:raise AssertionError('failure not injected')
                assert d.failed
                try:d.send('tick',1210)
                except RuntimeError:pass
                else:raise AssertionError('failed writer continued')
            if mode=='sql_abort':
                with sqlite3.connect(db) as c:c.execute('DROP TRIGGER reject_insert')
            with Durable(db,a) as d:
                expected={'checkpoint_error':'CLEAN','finalize_error':'PREPARED_NEW','sql_abort':'PREPARED_OLD'}[mode];assert d.outcome==expected
                assert len(d.g.book.legs)==(2 if mode=='finalize_error' else 0)
                d.send('recover',1210);d.send('quote',1211,symbol='A',price=1000,stamp=1211);d.send('quote',1212,symbol='B',price=1000,stamp=1212);r.ls.audit(d.g.book)
                row(mode,checkpoint=expected,final_fills=len(d.g.book.fills))
        for mode in ('tail_removed','all_removed','missing_checkpoint','missing_journal','changed_checkpoint','changed_payload','missing_table'):
            db,a=paths(mode)
            with Durable(db,a,create=True) as d:setup(d,'exit')
            if mode=='missing_checkpoint':a.unlink()
            elif mode=='missing_journal':db.unlink()
            elif mode=='changed_checkpoint':
                with sqlite3.connect(a) as c:c.execute("UPDATE checkpoint SET oldhead='bad'")
            else:
                with sqlite3.connect(db) as c:
                    if mode=='missing_table':c.execute('DROP TABLE journal')
                    elif mode=='tail_removed':c.execute('DELETE FROM journal WHERE seq=(SELECT MAX(seq) FROM journal)')
                    elif mode=='all_removed':c.execute('DELETE FROM journal')
                    else:c.execute("UPDATE journal SET payload='{}' WHERE seq=1")
            try:Durable(db,a)
            except (ValueError,KeyError,sqlite3.DatabaseError):row(mode)
            else:raise AssertionError('corruption accepted')
        db,a=paths('lock')
        with Durable(db,a,create=True) as d:
            try:Durable(db,a)
            except OSError:
                cp=subprocess.run([sys.executable,__file__,'--lock-probe',str(db),str(a)],capture_output=True,timeout=20);assert cp.returncode==73,cp.stderr.decode();row('concurrent_writer_lock')
            else:raise AssertionError('lock bypass')
        db,a=paths('view')
        with Durable(db,a,create=True) as d:
            setup(d,'entry');d.send(**event('entry'));v=status(d.g,1204);assert v['valuation']=='FRESH_ESTIMATE' and v['equity'] is not None;views.append(dict(case='view',phase='fresh',**v))
            v=status(d.g,1210);assert v['equity'] is None and v['valuation']=='INCOMPLETE';views.append(dict(case='view',phase='stale',**v))
            d.send('recover',1210);d.send('quote',1211,symbol='A',price=1000,stamp=1211);v=status(d.g,1211);assert v['equity'] is None and v['exposure']=='UNRESOLVED' and len(v['legs'])==1;views.append(dict(case='view',phase='partial',**v))
            d.send('quote',1212,symbol='B',price=1000,stamp=1212);v=status(d.g,1212);assert v['valuation']=='FLAT' and v['equity']==d.g.book.cash;r.ls.audit(d.g.book);views.append(dict(case='view',phase='flat',**v));row('valuation_fresh_stale_partial_flat')
    out.mkdir(exist_ok=False)
    with (out/'scenarios.csv').open('x',encoding='utf-8-sig',newline='') as h:
        w=csv.DictWriter(h,fieldnames=list(dict.fromkeys(k for x in rows for k in x)));w.writeheader();w.writerows(rows)
    (out/'valuation_views.json').write_text(json.dumps(views,indent=2),encoding='utf-8')
    print(json.dumps(dict(scenarios=len(rows),process_kills=10,views=len(views))))

if __name__=='__main__':
    if sys.argv[1]=='--worker':worker(*sys.argv[2:])
    elif sys.argv[1]=='--lock-probe':
        try:
            with Durable(*sys.argv[2:]):pass
        except OSError:sys.exit(73)
        sys.exit(0)
    else:tests(Path(sys.argv[1]))
