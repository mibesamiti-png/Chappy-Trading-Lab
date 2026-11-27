"""R28: append-only evidence journal; synthetic research only, no orders.
Run with a new output directory. Depends on Evidence Gate v0.1 in same folder.
Receipt stamps are assertions, not proof of genuine remote receipt.
"""
from dataclasses import asdict,replace
from datetime import datetime,timedelta
from decimal import Decimal
from pathlib import Path
import base64,hashlib,json,sqlite3,sys,subprocess,os,csv
import importlib.util
P=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('evidence_gate_r28',P/'Chappy_Trading_Evidence_Gate_v0.1.py');g=importlib.util.module_from_spec(spec);sys.modules[spec.name]=g;spec.loader.exec_module(g)
D=Decimal
ZERO='0'*64

def canonical(x):return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()
def digest(x):return hashlib.sha256(x).hexdigest()
def fact_dict(f):
    x=asdict(f)
    for k in ('observed','published','received'):x[k]=x[k].isoformat() if x[k] is not None else None
    x['value']=str(x['value']);return x

def fact_load(x):
    x=dict(x)
    for k in ('observed','published','received'):x[k]=datetime.fromisoformat(x[k]) if x[k] is not None else None
    x['value']=D(x['value']);return g.Fact(**x)

def identity(f):return (f.symbol,f.event,f.kind,f.period,f.metric,f.unit,f.source,f.origin)

def event(f,action='ADD',target=None,raw=None):
    if raw is None:raw=canonical(fact_dict(f)) # synthetic fixture, not original vendor response
    return dict(action=action,target=target,fact=fact_dict(f),raw_b64=base64.b64encode(raw).decode(),raw_sha256=digest(raw))

def validate(e,active,seen,last):
    if set(e)!={'action','target','fact','raw_b64','raw_sha256'}:raise ValueError('EVENT_SCHEMA')
    raw=base64.b64decode(e['raw_b64'],validate=True)
    if not raw or digest(raw)!=e['raw_sha256']:raise ValueError('RAW_HASH')
    f=fact_load(e['fact']);a=e['action'];target=e['target']
    if f.origin!='SYNTHETIC':raise ValueError('SYNTHETIC_ONLY')
    if not all(g.aware(t) for t in (f.observed,f.published,f.received)):raise ValueError('CLOCK_REQUIRED')
    if not f.observed<=f.published<=f.received:raise ValueError('CLOCK_ORDER')
    if last is not None and f.received<last:raise ValueError('RECEIPT_BACKDATED')
    if not f.evidence_id.strip() or not f.source.strip() or not f.value.is_finite() or f.kind not in g.KINDS:raise ValueError('FACT_INVALID')
    if f.evidence_id in seen:raise ValueError('DUPLICATE_ID')
    if a=='ADD':
        if target is not None:raise ValueError('ADD_TARGET')
    elif a in ('CORRECT','WITHDRAW'):
        if target not in active:raise ValueError('TARGET_NOT_ACTIVE')
        old=active[target]
        if identity(old)!=identity(f):raise ValueError('TARGET_IDENTITY')
        if f.received<=old.received:raise ValueError('CORRECTION_CLOCK')
        if f.published<old.published:raise ValueError('PUBLICATION_BACKDATED')
        del active[target]
    else:raise ValueError('ACTION_INVALID')
    if a!='WITHDRAW':active[f.evidence_id]=f
    seen.add(f.evidence_id);return f.received

class Journal:
    def __init__(self,path,create=False):
        self.path=Path(path)
        if create:
            if self.path.exists():raise FileExistsError(path)
            self.db=sqlite3.connect(path,isolation_level=None)
            self.db.execute('PRAGMA synchronous=FULL')
            self.db.execute('CREATE TABLE journal(seq INTEGER PRIMARY KEY, payload BLOB NOT NULL, chain TEXT NOT NULL)')
        else:
            self.db=sqlite3.connect(self.path.resolve().as_uri()+'?mode=rw',uri=True,isolation_level=None)
            self.db.execute('PRAGMA synchronous=FULL')
        self.verify()
    def __enter__(self):return self
    def __exit__(self,*a):self.db.close()
    def verify(self,expected=None,now=None):
        active={};seen=set();last=None;head=ZERO;seq=0;visible={};visible_n=0
        if now is not None and not g.aware(now):raise ValueError('CLOCK_REQUIRED')
        for n,p,h in self.db.execute('SELECT seq,payload,chain FROM journal ORDER BY seq'):
            if n!=seq+1 or digest(bytes.fromhex(head)+n.to_bytes(8,'big')+p)!=h:raise ValueError('CHAIN_MISMATCH')
            e=json.loads(p)
            if canonical(e)!=p:raise ValueError('NONCANONICAL')
            last=validate(e,active,seen,last);seq=n;head=h
            if now is None or last<now:visible=dict(active);visible_n=n
        if expected is not None and (seq,head)!=tuple(expected):raise ValueError('CHECKPOINT_MISMATCH')
        return dict(seq=seq,head=head,active=active,seen=seen,last=last,visible=visible,visible_n=visible_n)
    def append(self,e,inject=None):
        self.db.execute('BEGIN IMMEDIATE')
        try:
            s=self.verify();validate(e,s['active'],s['seen'],s['last']);n=s['seq']+1;p=canonical(e);h=digest(bytes.fromhex(s['head'])+n.to_bytes(8,'big')+p)
            self.db.execute('INSERT INTO journal VALUES(?,?,?)',(n,p,h))
            if inject=='before_commit':os._exit(91)
            self.db.execute('COMMIT')
            if inject=='after_commit':os._exit(92)
        except BaseException:
            if self.db.in_transaction:self.db.execute('ROLLBACK')
            raise
        return n,h
    def snapshot(self,c,now):
        s=self.verify(now=now);return dict(visible_seq=s['visible_n'],active_ids=sorted(s['visible']),decision=g.evaluate(c,list(s['visible'].values()),now))

def fixture():
    t=datetime.fromisoformat('2026-11-04T14:00:00+09:00');c=g.Context('SYNTH','E1',t,'PRETAX','PRETAX');fs=[]
    for k,v in zip(g.KINDS,[110,100,100,120,110,2]):
        obs=t-timedelta(days=1) if k in g.PRE else t+timedelta(minutes=5 if k=='PRICE_REACTION' else 0)
        fs.append(g.Fact(c.symbol,c.event,k,*g.definition(c,k),D(v),obs,obs,obs+timedelta(seconds=1),'synthetic://A',k))
    return c,sorted(fs,key=lambda f:f.received)

def changed(f,t,id,value=None,**kw):return replace(f,evidence_id=id,value=f.value if value is None else D(value),published=t,received=t+timedelta(seconds=1),**kw)

def main(out):
    protected=['CTRL.zip','Trading_Prospective_Plan_01.json','Chappy_Trading_Lab_v1.1.0-rc1.py','Chappy_Trading_Research_Lab_v0.5.0.py','Chappy_Trading_Evidence_Gate_v0.1.py','Trading_Round26_Consensus/consensus_events.csv']
    before={n:g.sha(P/n) for n in protected};assert before['Trading_Prospective_Plan_01.json']=='3311941f206b44220374d38e7cef86900cdb1bd480c111d0d2403ad73d1589cb'
    out.mkdir(parents=True,exist_ok=False);c,fs=fixture();t=c.release;actual=next(f for f in fs if f.kind=='H1_ACTUAL');expect=next(f for f in fs if f.kind=='H1_EXPECTED');cases=[];timeline=[];events=[event(f) for f in fs]
    def ok(name,detail=''):cases.append(dict(case=name,result='PASS',detail=detail))
    def reject(j,name,e,reason):
        s=j.verify();head=(s['seq'],s['head'])
        try:j.append(e)
        except ValueError as ex:assert str(ex)==reason,(name,str(ex),reason)
        else:raise AssertionError(name)
        j.verify(expected=head);ok(name,reason)
    db=out/'synthetic_journal.sqlite'
    with Journal(db,True) as j:
        for e in events:j.append(e)
        at=t+timedelta(minutes=6);base=j.snapshot(c,at);assert base['decision']['state']=='ALIGNED_UP_RESEARCH';ok('initial_aligned')
        correction=changed(actual,at,'ACTUAL_V2',90);e=event(correction,'CORRECT',actual.evidence_id);j.append(e);events.append(e)
        assert j.snapshot(c,at)==base;assert j.snapshot(c,correction.received)==base;ok('correction_not_visible_at_receipt')
        assert j.snapshot(c,correction.received+timedelta(seconds=1))['decision']['state']=='MIXED_SIGNALS_REVIEW';ok('correction_visible_next_second')
        second=changed(correction,at+timedelta(seconds=5),'ACTUAL_V3',125);e=event(second,'CORRECT',correction.evidence_id);j.append(e);events.append(e)
        assert j.snapshot(c,second.received+timedelta(seconds=1))['decision']['state']=='ALIGNED_UP_RESEARCH';ok('second_correction')
        other=changed(actual,at+timedelta(seconds=7),'OTHER_SOURCE',80,source='synthetic://B');e=event(other);j.append(e);events.append(e)
        assert j.snapshot(c,other.received+timedelta(seconds=1))['decision']['state']=='SOURCE_CONFLICT_REVIEW';ok('independent_source_conflict')
        when=at+timedelta(seconds=10)
        reject(j,'cross_source_correction',event(changed(second,when,'BAD',90),'CORRECT',other.evidence_id),'TARGET_IDENTITY')
        reject(j,'superseded_target',event(changed(actual,when,'BAD2',90),'CORRECT',actual.evidence_id),'TARGET_NOT_ACTIVE')
        reject(j,'duplicate_id',event(changed(second,when,second.evidence_id,90)),'DUPLICATE_ID')
        reject(j,'backdated_receipt',event(changed(actual,at,'BACK',99)),'RECEIPT_BACKDATED')
        reject(j,'wrong_period',event(changed(second,when,'BAD3',90,period='FY'),'CORRECT',second.evidence_id),'TARGET_IDENTITY')
        reject(j,'missing_target',event(changed(second,when,'BAD4',90),'CORRECT','absent'),'TARGET_NOT_ACTIVE')
        reject(j,'unverified_origin',event(changed(second,when,'BAD5',90,origin='CAPTURED')),'SYNTHETIC_ONLY')
        bad=event(changed(second,when,'BAD6',90));bad['raw_sha256']=ZERO;reject(j,'payload_hash_mismatch',bad,'RAW_HASH')
        reject(j,'naive_timestamp',event(replace(changed(second,when,'BAD7',90),received=when.replace(tzinfo=None))),'CLOCK_REQUIRED')
        reject(j,'same_receipt_correction',event(replace(changed(other,when,'BAD8',90),published=other.published,received=other.received),'CORRECT',other.evidence_id),'CORRECTION_CLOCK')
        withdrawal=changed(other,when,'WITHDRAW_B');e=event(withdrawal,'WITHDRAW',other.evidence_id);j.append(e);events.append(e)
        assert j.snapshot(c,withdrawal.received+timedelta(seconds=1))['decision']['state']=='ALIGNED_UP_RESEARCH';ok('withdraw_conflicting_source')
        late=changed(expect,when+timedelta(seconds=3),'EXPECT_LATE',105);e=event(late,'CORRECT',expect.evidence_id);j.append(e);events.append(e)
        res=j.snapshot(c,late.received+timedelta(seconds=1));assert res['decision']['state']=='INSUFFICIENT_EVIDENCE' and 'H1_EXPECTED' in res['decision']['missing'];ok('late_forecast_correction_fails_closed')
        # Compare all historical snapshots against independent incremental prefix databases.
        clocks=sorted(set([t-timedelta(days=2),t,t+timedelta(minutes=11)]+[fact_load(e['fact']).received+timedelta(seconds=s) for e in events for s in (-1,0,1)]))
        for n,clock in enumerate(clocks):
            prefix=out/'prefix.sqlite'
            with Journal(prefix,True) as k:
                for e in events:
                    if fact_load(e['fact']).received<clock:k.append(e)
                expected=k.snapshot(c,clock)
            prefix.unlink();got=j.snapshot(c,clock);assert got==expected,(clock,got,expected)
            timeline.append(dict(asof=clock.isoformat(),visible_seq=got['visible_seq'],state=got['decision']['state'],active_ids=';'.join(got['active_ids']),axes=json.dumps(got['decision']['axes'],sort_keys=True)))
        s=j.verify();checkpoint=(s['seq'],s['head']);ok('all_prefix_snapshots',str(len(clocks)))
    with Journal(db) as j:assert j.verify(expected=checkpoint)['seq']==len(events);ok('reopen_checkpoint')
    # independent digest implementation over rows; raw bytes retained as base64.
    with sqlite3.connect(db) as con:
        prev=bytes(32)
        for n,p,h in con.execute('SELECT * FROM journal ORDER BY seq'):
            prev=hashlib.sha256(prev+n.to_bytes(8,'big')+p).digest();assert prev.hex()==h
        assert prev.hex()==checkpoint[1]
    ok('independent_chain')
    import shutil
    for mode in ('modify','tail','middle'):
        path=out/f'tamper_{mode}.sqlite';shutil.copy2(db,path)
        with sqlite3.connect(path) as con:
            if mode=='modify':con.execute("UPDATE journal SET payload=CAST('bad' AS BLOB) WHERE seq=2")
            elif mode=='tail':con.execute('DELETE FROM journal WHERE seq=?',(checkpoint[0],))
            else:con.execute('DELETE FROM journal WHERE seq=2')
        try:
            with Journal(path) as j:j.verify(expected=checkpoint)
        except ValueError as ex:assert str(ex)==('CHECKPOINT_MISMATCH' if mode=='tail' else 'CHAIN_MISMATCH');ok('tamper_'+mode,str(ex))
        else:raise AssertionError(mode)
        path.unlink()
    for stage,code in [('before_commit',91),('after_commit',92)]:
        path=out/f'crash_{stage}.sqlite';shutil.copy2(db,path)
        p=subprocess.run([sys.executable,__file__,'--worker',str(path),stage],capture_output=True);assert p.returncode==code,(p.returncode,p.stderr)
        with Journal(path) as j:
            s=j.verify();assert s['seq']==checkpoint[0]+(stage=='after_commit');assert ('CRASH_ADD' in s['active'])==(stage=='after_commit')
            if stage=='before_commit':j.verify(expected=checkpoint)
        ok('process_exit_'+stage);path.unlink()
    assert before=={n:g.sha(P/n) for n in protected}
    g.write(out/'tests.csv',cases);g.write(out/'timeline.csv',timeline)
    manifest=dict(tests=len(cases),prefix_checks=len(timeline),journal_rows=checkpoint[0],head=checkpoint[1],process_exit_tests=2,protected=before,origin='SYNTHETIC',execution='DISABLED_RESEARCH_ONLY',limitations='SQLite logical append-only API; external checkpoint required to detect tail deletion; no authenticated source, trusted clock, capture adapter, real feeds, Windows or physical power failure tested. Raw payload fixtures are synthetic. No orders.')
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8');print(json.dumps(manifest,indent=2))

if __name__=='__main__':
    if sys.argv[1]=='--worker':
        c,fs=fixture();f=next(f for f in fs if f.kind=='H1_ACTUAL');f=changed(f,c.release+timedelta(minutes=7),'CRASH_ADD',111,source='synthetic://C')
        with Journal(sys.argv[2]) as j:j.append(event(f),inject=sys.argv[3])
    else:main(Path(sys.argv[1]))
