"""Round18: actual subprocess kill tests against Pipeline v0.2. Paper only.
Run: python this_file.py NEW_OUTPUT_DIR. Requires existing study modules.
"""
import csv, hashlib, importlib.util, json, os, signal, sqlite3, subprocess, sys, tempfile
from pathlib import Path
P=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('pipeline18',P/'Chappy_Trading_Pipeline_Study_v0.2.py');p=importlib.util.module_from_spec(spec);sys.modules[spec.name]=p;spec.loader.exec_module(p)
d=p.d;r=p.r
STAGES=('before_prepare','after_prepare','after_insert','after_commit','after_finalize')
TYPES=('provisional','decision','entry','partial_exit','recovery')

def setup(j,kind):
    j.send('configure',0,rule='PAIR')
    if kind=='provisional':return dict(kind='observe',now=1200,symbol='A',end=300,price=1004,volume=100)
    for i in range(1,17):
        end=i*300
        for rep in (0,1):
            for k in j.g.symbols:
                e=dict(kind='observe',now=end+900+rep,symbol=k,end=end,price=p.market_price(k,i),volume=100)
                if i==16 and rep==1 and k=='C' and kind=='decision':return e
                j.send(**e)
    assert j.g.pending and len(j.g.diagnostics)==16
    p.q(j,'A',5702,1068)
    e=dict(kind='quote',now=5703,symbol='B',price=932,stamp=5703)
    if kind=='entry':return e
    j.send(**e);assert len(j.g.book.legs)==2
    if kind=='recovery':return dict(kind='recover',now=5704)
    j.send('recover',5704)
    return dict(kind='quote',now=5705,symbol='A',price=1070,stamp=5705)

def snapshot(j):
    return dict(seq=j.j.seq,head=j.j.head,state=r.digest(j.g.state()),diagnostics=r.digest(j.g.diagnostics),decisions=len(j.g.diagnostics),intents=sum(x[1]=='INTENT' for x in j.g.evaluated),fills=len(j.g.book.fills),legs=len(j.g.book.legs),provisional=len(j.g.provisional),pending=bool(j.g.pending),exit=bool(j.g.exit),cash=j.g.book.cash)

def worker(db,a,kind,stage):
    with d.Durable(db,a,create=True) as j:j.send(**setup(j,kind),inject=stage)

def replay_check(j):
    g=p.PipelineGate();n=0;head=r.ZERO
    for seq,payload,state,chain in j.j.db.execute('SELECT seq,payload,state,chain FROM journal ORDER BY seq'):
        e=json.loads(payload);g.apply(e);n+=1
        assert seq==n and r.digest(g.state())==state and r.digest([head,seq,e,state])==chain
        head=chain
    assert r.digest(g.state())==r.digest(j.g.state()) and n==j.j.seq and head==j.j.head
    return n

def finish(j):
    pre=snapshot(j);n=j.g.clock+1
    try:j.send('tick',n)
    except ValueError:pass
    else:raise AssertionError('recovery bypass')
    assert snapshot(j)==pre
    j.send('recover',n);assert not j.g.pending and not j.g.provisional and j.g.fault=='RESTART_REVIEW'
    assert len(j.g.diagnostics)==pre['decisions'] and r.digest(j.g.diagnostics)==pre['diagnostics']
    assert len(j.g.book.fills)==pre['fills']
    if pre['legs']:
        assert d.status(j.g,n)['equity'] is None
        for k in ('A','B'):p.q(j,k,n+1,1000,stamp=n) # not strictly newer than recovery
        assert len(j.g.book.fills)==pre['fills']
    for i,k in enumerate(('A','B','C'),2):p.q(j,k,n+i,1000)
    assert not j.g.book.legs and len(j.g.book.fills)==pre['fills']+pre['legs']
    assert len(j.g.diagnostics)==pre['decisions']
    r.ls.audit(j.g.book)
    return snapshot(j)

def run(out):
    rows=[];reference={};checked=0
    protect=[P/x for x in ('Chappy_Trading_Pipeline_Study_v0.2.py','Chappy_Trading_Pipeline_Study_v0.1.py','Chappy_Trading_Durability_Study_v0.1.py','Chappy_Trading_Integrated_Replay_v0.1.py','Chappy_Trading_Lab_v1.1.0-rc1.py','Chappy_Trading_Research_Lab_v0.5.0.py','Trading_Prospective_Plan_01.json')]
    before={x.name:hashlib.sha256(x.read_bytes()).hexdigest() for x in protect}
    with tempfile.TemporaryDirectory() as td:
        root=Path(td)
        def paths(name):return root/(name+'.db'),root/(name+'.anchor.db')
        for kind in TYPES:
            db,a=paths('reference_'+kind)
            with d.Durable(db,a,create=True) as j:
                e=setup(j,kind);old=snapshot(j);j.send(**e);new=snapshot(j)
                assert old['state']!=new['state'] and new['seq']==old['seq']+1
                reference[kind]=(old,new)
        def verify(name,kind,committed,expected):
            nonlocal checked
            db,a=paths(name);ref=reference[kind][int(committed)]
            with d.Durable(db,a) as j:
                assert j.outcome==expected and snapshot(j)==ref
                rec=j.a.execute('SELECT outcome FROM reconciliation').fetchall();assert rec==([(expected,)] if expected.startswith('PREPARED') else [])
                checked+=replay_check(j);final=finish(j);checked+=replay_check(j)
            with d.Durable(db,a) as j:assert snapshot(j)==final and j.outcome=='CLEAN';checked+=replay_check(j)
            rows.append(dict(case=name,target=kind,result='PASS',committed=committed,checkpoint=expected,before_seq=ref['seq'],before_diagnostics=ref['decisions'],before_fills=ref['fills'],before_open=ref['legs'],before_provisional=ref['provisional'],before_pending=ref['pending'],final_fills=final['fills'],final_cash=final['cash'],final_state=final['state']))
        for kind in TYPES:
            for stage in STAGES:
                name=kind+'_'+stage;db,a=paths(name)
                cp=subprocess.run([sys.executable,__file__,'--worker',str(db),str(a),kind,stage],capture_output=True,timeout=25)
                assert cp.returncode==(-signal.SIGKILL if os.name=='posix' else 91),(name,cp.returncode,cp.stderr.decode())
                verify(name,kind,stage in STAGES[3:],dict(zip(STAGES,('CLEAN','PREPARED_OLD','PREPARED_OLD','PREPARED_NEW','CLEAN')))[stage])
            print(kind,'5/5',flush=True)
        for kind in ('decision','entry','partial_exit'):
            for mode in ('checkpoint_error','finalize_error','sql_abort'):
                name=kind+'_'+mode;db,a=paths(name)
                with d.Durable(db,a,create=True) as j:
                    e=setup(j,kind)
                    if mode=='sql_abort':j.j.db.execute("CREATE TRIGGER reject_insert BEFORE INSERT ON journal BEGIN SELECT RAISE(ABORT,'injected'); END");j.j.db.commit()
                    try:j.send(**e,inject=mode)
                    except (OSError,sqlite3.DatabaseError):pass
                    else:raise AssertionError('missing injected failure')
                    assert j.failed
                    try:j.send('tick',j.g.clock+1)
                    except RuntimeError:pass
                    else:raise AssertionError('continued failed writer')
                if mode=='sql_abort':
                    with sqlite3.connect(db) as c:c.execute('DROP TRIGGER reject_insert')
                verify(name,kind,mode=='finalize_error',{'checkpoint_error':'CLEAN','finalize_error':'PREPARED_NEW','sql_abort':'PREPARED_OLD'}[mode])
        # Test diagnostic-bearing committed decision removed from journal, and altered input.
        for mode in ('tail_removed','diagnostic_input_changed'):
            db,a=paths(mode)
            with d.Durable(db,a,create=True) as j:j.send(**setup(j,'decision'))
            with sqlite3.connect(db) as c:
                if mode=='tail_removed':c.execute('DELETE FROM journal WHERE seq=(SELECT MAX(seq) FROM journal)')
                else:
                    seq,payload=c.execute('SELECT seq,payload FROM journal ORDER BY seq DESC LIMIT 1').fetchone();e=json.loads(payload);e['price']+=1;c.execute('UPDATE journal SET payload=? WHERE seq=?',(r.canonical(e),seq))
            try:
                with d.Durable(db,a):pass
            except ValueError:rows.append(dict(case=mode,target='decision',result='PASS'))
            else:raise AssertionError('corrupt data accepted')
    after={x.name:hashlib.sha256(x.read_bytes()).hexdigest() for x in protect};assert before==after
    out.mkdir(exist_ok=False)
    with (out/'scenarios.csv').open('x',encoding='utf-8-sig',newline='') as h:
        w=csv.DictWriter(h,fieldnames=list(dict.fromkeys(k for x in rows for k in x)));w.writeheader();w.writerows(rows)
    report=dict(scenarios=len(rows),process_kills=25,storage_errors=9,corruption_rejections=2,replay_row_checks=checked,reference=reference,protected_hashes=before,platform=sys.platform)
    (out/'manifest.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps({k:v for k,v in report.items() if k not in ('reference','protected_hashes')}))
if __name__=='__main__':
    if sys.argv[1]=='--worker':worker(*sys.argv[2:])
    else:run(Path(sys.argv[1]))
