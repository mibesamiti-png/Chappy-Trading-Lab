"""R33: research-only proposal review, using R32's bounded verifier.
No AI call, authentic reviewer login, market clock, live Fact, or order path.
All approvals in the synthetic test ledger are simulated. Historical excerpts stay pending.
CLI: python this.py NEW_OUTPUT_DIR
"""
import csv, hashlib, importlib.util, json, sqlite3, sys, tempfile
from pathlib import Path
from datetime import datetime, timezone, timedelta
P=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('r32_review',P/'Chappy_Trading_Common_Document_Study_v0.1.py'); r32=importlib.util.module_from_spec(spec);spec.loader.exec_module(r32)
ZERO='0'*64

def canon(x):return json.dumps(x,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()
def digest(x):return hashlib.sha256(x).hexdigest()
def ident(x):return digest(canon(x))
def require(b,msg):
    if not b:raise ValueError(msg)
def clock(x):
    t=datetime.fromisoformat(x);require(t.tzinfo is not None and t.utcoffset() is not None,'CLOCK');return t

def candidate_key(c):return tuple(c[k] for k in ('symbol','event','period_end','metric','kind','unit'))
def comparison(c):return tuple(c.get(k) for k in ('value','old_value','delta','revision_pct','prior_actual','yoy_pct'))

class State:
    def __init__(self,mode):
        self.mode=mode;self.docs={};self.proposals={};self.last=None
    def apply(self,e):
        t=clock(e['at']);require(self.last is None or t>=self.last,'BACKDATED');kind=e['kind'];d=e['data']
        if kind=='REGISTER':
            require(set(d)=={'doc','envelope'},'SCHEMA');env=d['envelope'];key=d['doc'];require(ident(env)==key,'DOC_HASH');require(key not in self.docs,'DUPLICATE_DOC')
            require(env['origin']==('SYNTHETIC' if self.mode=='SYNTHETIC' else 'WEB_RENDERED_EXCERPT_MANUAL_SELECTION'),'ORIGIN')
            result=r32.project(env);self.docs[key]={'envelope':env,'status':result['status'],'retired':False}
        elif kind=='SUBMIT':
            require(set(d)=={'proposal','doc','candidate','proposer'},'SCHEMA');key=d['proposal'];doc=self.docs.get(d['doc']);require(doc is not None and not doc['retired'],'DOCUMENT_UNAVAILABLE')
            require(d['proposer']=='SIMULATED_AI' if self.mode=='SYNTHETIC' else d['proposer']=='REFERENCE_PROJECTION','PROPOSER')
            require(key==ident([d['doc'],d['candidate'],d['proposer']]),'PROPOSAL_HASH');require(key not in self.proposals,'DUPLICATE_PROPOSAL')
            result=r32.project(doc['envelope']);valid=result['status']=='CANDIDATE_ONLY' and any(canon(c)==canon(d['candidate']) for c in result['candidates'])
            self.proposals[key]={**d,'status':'PENDING' if valid else 'REJECTED_BY_VERIFIER','reviewer':None,'reason':None if valid else 'EXACT_PROJECTION_MISMATCH'}
        elif kind=='REVIEW':
            require(self.mode=='SYNTHETIC','REAL_APPROVAL_DISABLED');require(set(d)=={'proposal','binding','reviewer','decision','reason'},'SCHEMA');p=self.proposals.get(d['proposal']);require(p is not None and p['status']=='PENDING','NOT_PENDING');require(not self.docs[p['doc']]['retired'],'DOCUMENT_UNAVAILABLE')
            require(d['reviewer']=='SIMULATED_REVIEWER' and d['reviewer']!=p['proposer'],'REVIEWER_ROLE');require(d['binding']==ident([p['doc'],p['candidate'],p['proposer']]),'STALE_BINDING');require(d['decision'] in ('APPROVE','REJECT') and isinstance(d['reason'],str) and bool(d['reason'].strip()),'REVIEW_REQUIRED')
            p.update(status='APPROVED_RESEARCH_ONLY' if d['decision']=='APPROVE' else 'REJECTED_BY_REVIEWER',reviewer=d['reviewer'],reason=d['reason'])
        elif kind=='RETIRE':
            require(self.mode=='SYNTHETIC','REAL_APPROVAL_DISABLED');require(set(d)=={'doc','reason','reviewer'},'SCHEMA');require(d['reviewer']=='SIMULATED_REVIEWER' and isinstance(d['reason'],str) and d['reason'].strip(),'REVIEWER_ROLE');doc=self.docs.get(d['doc']);require(doc is not None and not doc['retired'],'DOCUMENT_UNAVAILABLE');doc['retired']=True
            for p in self.proposals.values():
                if p['doc']==d['doc'] and p['status'] in ('PENDING','APPROVED_RESEARCH_ONLY'):p.update(status='RETIRED',reason=d['reason'])
        else:raise ValueError('EVENT_KIND')
        self.last=t
    def snapshot(self):
        groups={}
        for p in self.proposals.values():
            if p['status']=='APPROVED_RESEARCH_ONLY':groups.setdefault(candidate_key(p['candidate']),[]).append(p)
        conflict={p['proposal'] for ps in groups.values() if len({comparison(p['candidate']) for p in ps})>1 for p in ps}
        return {'mode':self.mode,'documents':{k:{'status':v['status'],'retired':v['retired']} for k,v in self.docs.items()},'proposals':{k:{'status':v['status'],'effective':'HOLD_CONFLICT' if k in conflict else v['status'],'doc':v['doc'],'reviewer':v['reviewer'],'reason':v['reason'],'candidate':v['candidate']} for k,v in self.proposals.items()},'live_eligible':0,'execution':'DISABLED'}

class Ledger:
    def __init__(self,path,mode,create=False):
        require(mode in ('SYNTHETIC','HISTORICAL_REVIEW'),'MODE');self.mode=mode;self.path=Path(path)
        if create and self.path.exists():raise FileExistsError(path)
        self.db=sqlite3.connect(path if create else self.path.resolve().as_uri()+'?mode=rw',uri=not create,isolation_level=None);self.db.execute('PRAGMA synchronous=FULL')
        if create:self.db.execute('CREATE TABLE log(seq INTEGER PRIMARY KEY,payload BLOB NOT NULL,chain TEXT NOT NULL)')
        self.read()
    def __enter__(self):return self
    def __exit__(self,*a):self.db.close()
    def read(self,limit=None,expected=None):
        state=State(self.mode);head=ZERO;rows=[];prefix=state.snapshot()
        for n,p,h in self.db.execute('SELECT seq,payload,chain FROM log ORDER BY seq'):
            require(n==len(rows)+1 and digest(bytes.fromhex(head)+n.to_bytes(8,'big')+p)==h,'CHAIN');e=json.loads(p);require(canon(e)==p and e['mode']==self.mode,'CONTENT');state.apply(e);rows.append(e);head=h
            if limit is not None and n==limit:prefix=state.snapshot()
        if expected is not None:require((len(rows),head)==tuple(expected),'CHECKPOINT')
        if limit is not None:require(0<=limit<=len(rows),'PREFIX');return rows,head,prefix
        return rows,head,state.snapshot()
    def append(self,kind,at,data):
        e={'mode':self.mode,'kind':kind,'at':at,'data':data};p=canon(e);require(len(p)<=4_000_000,'SIZE');self.db.execute('BEGIN IMMEDIATE')
        try:
            rows,head,_=self.read();state=State(self.mode)
            for old in rows:state.apply(old)
            state.apply(e);n=len(rows)+1;h=digest(bytes.fromhex(head)+n.to_bytes(8,'big')+p);self.db.execute('INSERT INTO log VALUES(?,?,?)',(n,p,h));self.db.execute('COMMIT');return n,h
        except BaseException:
            if self.db.in_transaction:self.db.execute('ROLLBACK')
            raise


def main(out):
    old=P/'Trading_Round32_Common_Document';source=json.loads((old/'evidence.json').read_text());protected=list(json.loads((old/'manifest.json').read_text())['protected'])+['Chappy_Trading_Common_Document_Study_v0.1.py','Trading_Round32_Common_Document/evidence.json'];before={n:digest((P/n).read_bytes()) for n in protected};require(before['Trading_Prospective_Plan_01.json']=='3311941f206b44220374d38e7cef86900cdb1bd480c111d0d2403ad73d1589cb','PLAN')
    out.mkdir(parents=True,exist_ok=False);tests=[];timeline=[];at=datetime(2026,11,25,12,tzinfo=timezone.utc);counter=0
    def ts():
        nonlocal counter
        counter+=1;return (at+timedelta(seconds=counter)).isoformat()
    def ok(name,b):require(b,name);tests.append({'test':name,'result':'PASS'})
    def reject(name,l,kind,data,reason,stamp=None):
        prior=l.read()
        try:l.append(kind,stamp or ts(),data)
        except ValueError as ex:ok(name,str(ex)==reason and l.read()==prior)
        else:raise RuntimeError('unexpected acceptance: '+name)
    def event(l,k,d):
        n,h=l.append(k,ts(),d);s=l.read()[2];timeline.append({'mode':l.mode,'seq':n,'event':k,'state_sha256':ident(s),'pending':sum(p['effective']=='PENDING' for p in s['proposals'].values()),'approved':sum(p['effective']=='APPROVED_RESEARCH_ONLY' for p in s['proposals'].values()),'conflict':sum(p['effective']=='HOLD_CONFLICT' for p in s['proposals'].values()),'live_eligible':s['live_eligible']});return s
    def register(l,e):
        key=ident(e);event(l,'REGISTER',{'doc':key,'envelope':e});return key
    def submit(l,doc,c):
        proposer='SIMULATED_AI' if l.mode=='SYNTHETIC' else 'REFERENCE_PROJECTION';p=ident([doc,c,proposer]);s=event(l,'SUBMIT',{'doc':doc,'candidate':c,'proposal':p,'proposer':proposer});return p,s['proposals'][p]['status']
    def review(p,**kw):return {'proposal':p,'binding':p,'reviewer':'SIMULATED_REVIEWER','decision':'APPROVE','reason':'synthetic review fixture',**kw}
    with Ledger(out/'historical.sqlite','HISTORICAL_REVIEW',True) as l:
        for i,row in enumerate(source):
            e=row['input'];doc=register(l,e);r=r32.project(e);ok('historical_projection_'+str(i),r==row['output'])
            for c in r['candidates']:
                p,status=submit(l,doc,c);ok('historical_pending_'+p[:8],status=='PENDING');last=p
        reject('historical_approval_disabled',l,'REVIEW',review(last),'REAL_APPROVAL_DISABLED');hist=l.read();ok('historical_seven_pending',len(hist[2]['proposals'])==7 and all(p['status']=='PENDING' for p in hist[2]['proposals'].values()))
    with Ledger(out/'synthetic.sqlite','SYNTHETIC',True) as l:
        e=dict(source[1]['input'],origin='SYNTHETIC');doc=register(l,e);c=r32.project(e)['candidates'][1];p,status=submit(l,doc,c);ok('valid_pending',status=='PENDING')
        for field,value in [('value','690001'),('metric','OPERATING'),('proof',{}),('receipt_verified',True),('execution','ENABLED'),('source','fake'),('revision_pct','-5.6'),('period_end','2026-03-31')]:
            _,status=submit(l,doc,dict(c,**{field:value}));ok('bad_'+field,status=='REJECTED_BY_VERIFIER')
        reject('duplicate',l,'SUBMIT',{'doc':doc,'candidate':c,'proposal':p,'proposer':'SIMULATED_AI'},'DUPLICATE_PROPOSAL')
        reject('self_review',l,'REVIEW',review(p,reviewer='SIMULATED_AI'),'REVIEWER_ROLE')
        reject('stale_binding',l,'REVIEW',review(p,binding=ZERO),'STALE_BINDING')
        reject('missing_reason',l,'REVIEW',review(p,reason=''),'REVIEW_REQUIRED')
        reject('backdated',l,'REVIEW',review(p),'BACKDATED',at.isoformat())
        s=event(l,'REVIEW',review(p));ok('approved_research_only',s['proposals'][p]['effective']=='APPROVED_RESEARCH_ONLY' and s['live_eligible']==0)
        reject('double_review',l,'REVIEW',review(p),'NOT_PENDING')
        # Different, arithmetically consistent source revision for same semantic field.
        t=e['text'].replace('6,900（10.0%）','6,800（10.0%）').replace('▲407','▲507').replace('▲5.6%','▲6.9%').replace('▲300 |','▲400 |')
        e2=dict(e,text=t,source='synthetic://alternate');doc2=register(l,e2);r=r32.project(e2);ok('alternate_consistent',r['status']=='CANDIDATE_ONLY');p2,status=submit(l,doc2,r['candidates'][1]);ok('alternate_pending',status=='PENDING')
        s=event(l,'REVIEW',review(p2));ok('conflict_holds_both',all(s['proposals'][k]['effective']=='HOLD_CONFLICT' for k in (p,p2)))
        s=event(l,'RETIRE',{'doc':doc2,'reason':'simulated withdrawal','reviewer':'SIMULATED_REVIEWER'});ok('retirement_resolves',s['proposals'][p]['effective']=='APPROVED_RESEARCH_ONLY' and s['proposals'][p2]['effective']=='RETIRED')
        reject('stale_after_retire',l,'REVIEW',review(p2),'NOT_PENDING')
        reject('submit_retired',l,'SUBMIT',{'doc':doc2,'candidate':r['candidates'][0],'proposal':ident([doc2,r['candidates'][0],'SIMULATED_AI']),'proposer':'SIMULATED_AI'},'DOCUMENT_UNAVAILABLE')
        p3,status=submit(l,doc,r32.project(e)['candidates'][0]);s=event(l,'REVIEW',review(p3,decision='REJECT'));ok('reviewer_reject',s['proposals'][p3]['effective']=='REJECTED_BY_REVIEWER')
        reject('doc_hash_wrong',l,'REGISTER',{'doc':ZERO,'envelope':e},'DOC_HASH')
        reject('origin_wrong',l,'REGISTER',{'doc':ident(source[1]['input']),'envelope':source[1]['input']},'ORIGIN')
        rows,head,s=l.read();ok('no_execution',s['execution']=='DISABLED' and s['live_eligible']==0)
        synthetic=(rows,head,s)
    # Independently rebuild each historical prefix in a separate SQLite database.
    count=0
    for mode,path,baseline in [('SYNTHETIC','synthetic.sqlite',synthetic),('HISTORICAL_REVIEW','historical.sqlite',hist)]:
        rows,head,s=baseline
        with Ledger(out/path,mode) as original, tempfile.TemporaryDirectory() as tmp:
            with Ledger(Path(tmp)/'prefix.sqlite',mode,True) as prefix:
                for i in range(len(rows)+1):
                    if i:
                        e=rows[i-1];prefix.append(e['kind'],e['at'],e['data'])
                    require(original.read(limit=i,expected=(len(rows),head))[2]==prefix.read()[2],'PREFIX_MISMATCH');count+=1
            ok('prefix_'+mode,True)
        with Ledger(out/path,mode) as reopened:ok('reopen_'+mode,reopened.read(expected=(len(rows),head))==baseline)
    import shutil
    for name,sql in [('changed','UPDATE log SET payload=x\'7b7d\' WHERE seq=2'),('middle','DELETE FROM log WHERE seq=2'),('tail','DELETE FROM log WHERE seq=(SELECT MAX(seq) FROM log)')]:
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'bad.sqlite';shutil.copy2(out/'synthetic.sqlite',path)
            with sqlite3.connect(path) as db:db.execute(sql)
            try:
                with Ledger(path,'SYNTHETIC') as l:l.read(expected=(len(synthetic[0]),synthetic[1]))
            except ValueError:ok('tamper_'+name,True)
            else:raise RuntimeError('tamper undetected')
    ok('protected_unchanged',before=={n:digest((P/n).read_bytes()) for n in protected})
    for name,data in [('tests.csv',tests),('timeline.csv',timeline)]:
        with (out/name).open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=list(data[0]));w.writeheader();w.writerows(data)
    (out/'historical_queue.json').write_bytes(canon(hist[2]));manifest={'tests':len(tests),'prefix_checks':count,'historical_documents':len(hist[2]['documents']),'historical_pending':len(hist[2]['proposals']),'synthetic_events':len(synthetic[0]),'historical_events':len(hist[0]),'checkpoints':{'synthetic':[len(synthetic[0]),synthetic[1]],'historical':[len(hist[0]),hist[1]]},'protected':before,'live_eligible':0,'limits':'Simulated proposer/reviewer only, historical projection pending. Rendered excerpts not authentic original bytes. No model call, authenticated identity, live ingestion, facts or orders. Separate checkpoint required for tail deletion.'};(out/'manifest.json').write_text(json.dumps(manifest,indent=2));print(json.dumps(manifest,indent=2))
if __name__=='__main__':main(Path(sys.argv[1]))
