"""Round 48: synthetic decision evidence journal; no feeds, trades or market data.
Hash chain detects changes relative to a separately trusted head. Not authenticated storage.
Uses R47's synthetic long-only gate. Times are integer synthetic seconds.
"""
import argparse, copy, hashlib, importlib.util, json, sys
from pathlib import Path
from dataclasses import asdict, replace

BASE = Path(__file__).with_name('Chappy_Trading_Decision_Quality_v0.2.py')
BASE_SHA = '4b3c220610f54ab0a764dcbc4d27e8809a9c19ebf8d358e7cad5ac116b4e390c'
if hashlib.sha256(BASE.read_bytes()).hexdigest()!=BASE_SHA: raise RuntimeError('R47 dependency changed')
spec=importlib.util.spec_from_file_location('round47_pinned', BASE)
r47=importlib.util.module_from_spec(spec); sys.modules[spec.name]=r47; spec.loader.exec_module(r47)
GENESIS='0'*64

def canonical(x): return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()
def digest(x): return hashlib.sha256(canonical(x)).hexdigest()
def require(ok,msg):
    if not ok: raise ValueError(msg)
def nat(x): return type(x) is int and x>=0
def name(x): return isinstance(x,str) and bool(x.strip())
def parse_plan(d):
    d=copy.deepcopy(d)
    for k in ('entry','refute','confirm'): d[k]=r47.Predicate(**d[k])
    return r47.Plan(**d)

class Journal:
    def __init__(self):
        self._records=[]; self._obs={}; self._active=set(); self._decisions={}
    @property
    def head(self): return self._records[-1]['hash'] if self._records else GENESIS
    def export(self): return copy.deepcopy(self._records)
    def _append(self,kind,clock,body):
        require(nat(clock) and (not self._records or clock>=self._records[-1]['clock']),'journal clock reversal')
        rec={'seq':len(self._records)+1,'prev':self.head,'clock':clock,'kind':kind,'body':copy.deepcopy(body)}
        rec['hash']=digest(rec); self._records.append(rec); return rec['hash']
    def observations(self,clock,items):
        require(nat(clock) and isinstance(items,list) and bool(items),'invalid batch')
        ids=set(); targets=set()
        for item in items:
            require(set(item)=={'id','symbol','evidence','supersedes'},'observation schema')
            i,s,e,old=item['id'],item['symbol'],item['evidence'],item['supersedes']
            require(name(i) and name(s) and i not in self._obs and i not in ids,'duplicate/invalid id or symbol'); ids.add(i)
            row=r47.Evidence(**e)
            require(row.field in r47.FIELDS and nat(row.event) and nat(row.received) and row.event<=row.received<=clock,'invalid event/receipt')
            require(nat(row.value) and (row.field not in {'close','bid','ask'} or row.value>0) and name(row.source) and name(row.snapshot),'invalid value/provenance')
            if old is not None:
                require(name(old) and old in self._active and old not in targets,'unknown/inactive/duplicate correction target'); targets.add(old)
                previous=self._obs[old]; pe=previous['evidence']
                require(previous['symbol']==s and all(e[k]==pe[k] for k in ('field','event','source','snapshot')) and row.received>=pe['received'],'correction identity mismatch')
        self._append('OBS',clock,{'items':items})
        for item in items:
            i=item['id']; self._obs[i]=copy.deepcopy(item); self._active.add(i)
            if item['supersedes'] is not None: self._active.remove(item['supersedes'])
        return self.head
    def _snapshot(self,symbol):
        ids=sorted(i for i in self._active if self._obs[i]['symbol']==symbol)
        return ids,[r47.Evidence(**self._obs[i]['evidence']) for i in ids]
    def decide(self,clock,decision_id,symbol,plan,supported):
        require(name(decision_id) and decision_id not in self._decisions and name(symbol),'invalid decision id/symbol')
        require(isinstance(supported,(set,list,tuple)) and all(f in r47.FIELDS for f in supported),'invalid capabilities')
        supported=sorted(set(supported)); ids,rows=self._snapshot(symbol)
        result=r47.evaluate(plan,rows,clock,set(supported))
        body={'id':decision_id,'symbol':symbol,'plan':asdict(plan),'supported':supported,'evidence_ids':ids,'gate':result,'engine_sha':BASE_SHA}
        self._append('DECISION',clock,body); self._decisions[decision_id]=self._records[-1]
        return copy.deepcopy(body)
    def _review_result(self,decision_id,clock):
        require(decision_id in self._decisions,'unknown decision')
        d=self._decisions[decision_id]; b=d['body']; p=parse_plan(b['plan'])
        require(b['gate']['gate']=='RESEARCH_ELIGIBLE','decision not eligible for outcome review')
        require(nat(clock) and clock>=d['clock'],'review clock reversal')
        # Prefix replay by append order; batches are atomic. Only information logged by deadline can resolve it.
        active={}; outcome=None; decisive=[]; decisive_seq=None; corrected=set(); corrections=[]
        for rec in self._records:
            if rec['clock']>clock: break
            if rec['kind']!='OBS': continue
            for item in rec['body']['items']:
                if item['symbol']!=b['symbol']: continue
                old=item['supersedes']
                if old is not None:
                    active.pop(old,None); corrected.add(old)
                    if rec['seq']>d['seq']: corrections.append({'old':old,'new':item['id'],'seq':rec['seq']})
                active[item['id']]=item
            if rec['seq']<=d['seq'] or rec['clock']>p.deadline or outcome is not None: continue
            candidates={i:r47.Evidence(**o['evidence']) for i,o in active.items() if o['evidence']['event']>d['clock'] and o['evidence']['received']>d['clock'] and o['evidence']['field']=='close'}
            states,values=r47.collect(list(candidates.values()),rec['clock'],set(b['supported']))
            if states['close']!='OK': continue
            if r47.truth(p.refute,values)=='TRUE': outcome='REFUTED'
            elif r47.truth(p.confirm,values)=='TRUE': outcome='CONFIRMED_OBSERVED'
            if outcome:
                newest=max(e.event for e in candidates.values()); decisive=sorted(i for i,e in candidates.items() if e.event==newest); decisive_seq=rec['seq']
        return {'decision_hash':d['hash'],'outcome':outcome or ('EXPIRED_UNRESOLVED' if clock>=p.deadline else 'OPEN_UNRESOLVED'),'decisive_ids':decisive,'decisive_seq':decisive_seq,'decision_evidence_corrected':sorted(set(b['evidence_ids'])&corrected),'decisive_evidence_corrected':sorted(set(decisive)&corrected),'corrections_after_decision':corrections,'execution_proven':False}
    def review(self,clock,decision_id):
        result=self._review_result(decision_id,clock); self._append('REVIEW',clock,{'decision_id':decision_id,'result':result}); return copy.deepcopy(result)
    @classmethod
    def restore(cls,records,expected_head=None):
        require(isinstance(records,list),'invalid journal'); j=cls()
        for rec in records:
            require(isinstance(rec,dict) and set(rec)=={'seq','prev','clock','kind','body','hash'},'record schema')
            require(type(rec['seq']) is int and rec['seq']==len(j._records)+1 and rec['prev']==j.head and rec['hash']==digest({k:v for k,v in rec.items() if k!='hash'}),'hash/sequence mismatch')
            b=rec['body']; c=rec['clock']; k=rec['kind']
            if k=='OBS': j.observations(c,b['items'])
            elif k=='DECISION': j.decide(c,b['id'],b['symbol'],parse_plan(b['plan']),b['supported'])
            elif k=='REVIEW': j.review(c,b['decision_id'])
            else: raise ValueError('unknown record kind')
            require(canonical(j._records[-1])==canonical(rec),'semantic replay mismatch')
        if expected_head is not None: require(j.head==expected_head,'external head mismatch')
        return j

def self_test():
    tests=[]
    def check(n,a,b):
        if a!=b: raise RuntimeError(f'{n}: {a!r} != {b!r}')
        tests.append({'test':n,'result':'PASS'})
    def reject(n,fn):
        try: fn()
        except (ValueError,TypeError,KeyError): tests.append({'test':n,'result':'PASS'}); return
        raise RuntimeError(n+' unexpectedly accepted')
    p=r47.Plan(r47.Predicate('close','>=',100),r47.Predicate('close','<=',95),r47.Predicate('close','>=',110),1100,100,100000,100000,100,10,1)
    s=set(r47.FIELDS)
    def obs(i,f,v,e=995,t=997,symbol='A',old=None,source='feed',snap='X'):
        return {'id':i,'symbol':symbol,'evidence':asdict(r47.Evidence(f,v,e,t,source,snap)),'supersedes':old}
    initial=[obs(f,f,v) for f,v in {'close':100,'bid':99,'ask':100,'bid_depth':100,'ask_depth':100,'volume':0}.items()]
    def fresh():
        j=Journal();j.observations(998,initial);j.decide(1000,'D','A',p,s);return j
    j=fresh(); frozen=j.export()[1]; check('initial gate',frozen['body']['gate']['gate'],'RESEARCH_ELIGIBLE')
    check('snapshot ids',frozen['body']['evidence_ids'],sorted(x['id'] for x in initial)); check('pinned engine',frozen['body']['engine_sha'],BASE_SHA)
    check('open review',j.review(1001,'D')['outcome'],'OPEN_UNRESOLVED')
    j.observations(1010,[obs('close-c','close',94,t=1009,old='close')]); rr=j.review(1011,'D')
    check('late correction not retroactive',rr['outcome'],'OPEN_UNRESOLVED');check('corrected decision flagged',rr['decision_evidence_corrected'],['close']);check('original decision immutable',j.export()[1],frozen)
    j.observations(1020,[obs('b','close',115,e=1019,t=1020,symbol='B')]);check('other symbol not used',j.review(1020,'D')['outcome'],'OPEN_UNRESOLVED')
    j.observations(1030,[obs('hit','close',111,e=1029,t=1030)]);r=j.review(1030,'D');check('confirm',r['outcome'],'CONFIRMED_OBSERVED');check('decisive proof ids',r['decisive_ids'],['hit']);check('bound decision',r['decision_hash'],frozen['hash'])
    j.observations(1040,[obs('hit-c','close',94,e=1029,t=1040,old='hit')]);r=j.review(1040,'D');check('original observed result persists',r['outcome'],'CONFIRMED_OBSERVED');check('decisive correction flagged',r['decisive_evidence_corrected'],['hit']);check('two corrections',len(r['corrections_after_decision']),2);check('no execution claim',r['execution_proven'],False)
    check('prior review immutable',j.export()[-3]['body']['result']['decisive_evidence_corrected'],[])
    check('restore exact',Journal.restore(j.export(),j.head).export(),j.export());check('restore head',Journal.restore(j.export(),j.head).head,j.head)
    c=j.export();c[1]['body']['plan']['confirm']['threshold']=999;reject('tamper plan',lambda:Journal.restore(c,j.head))
    c=j.export();c[0]['body']['items'][0]['evidence']['value']=99;reject('tamper evidence',lambda:Journal.restore(c,j.head))
    reject('truncated anchored chain',lambda:Journal.restore(j.export()[:-1],j.head));check('unanchored truncation undetectable',Journal.restore(j.export()[:-1]).head,j.export()[-2]['hash'])
    c=j.export();c[1],c[2]=c[2],c[1];reject('reorder',lambda:Journal.restore(c))
    c=j.export();c[-1]['body']['result']['outcome']='REFUTED';c[-1]['hash']=digest({k:v for k,v in c[-1].items() if k!='hash'});reject('rehashed false review semantic mismatch',lambda:Journal.restore(c))
    c=j.export();c[1]['body']['gate']['gate']='BLOCK'
    for idx,rec in enumerate(c):
        rec['prev']=c[idx-1]['hash'] if idx else GENESIS;rec['hash']=digest({k:v for k,v in rec.items() if k!='hash'})
    reject('rehashed false gate semantic mismatch',lambda:Journal.restore(c))
    k=fresh(); h=k.head;reject('duplicate id',lambda:k.observations(1001,[initial[0]]));check('rejected batch unchanged',k.head,h)
    reject('future receipt',lambda:k.observations(1001,[obs('future','close',100,t=1002)]));reject('event after receipt',lambda:k.observations(1001,[obs('bad','close',100,e=1001,t=1000)]));reject('backdated append',lambda:k.observations(999,[obs('back','close',100)]))
    reject('bad correction symbol',lambda:k.observations(1001,[obs('cross','close',100,symbol='B',old='close')]));reject('bad correction event',lambda:k.observations(1001,[obs('cross','close',100,e=996,old='close')]));reject('bad correction source',lambda:k.observations(1001,[obs('cross','close',100,source='other',old='close')]));reject('missing target',lambda:k.observations(1001,[obs('cross','close',100,old='absent')]));reject('double correction same batch',lambda:k.observations(1001,[obs('x','close',100,old='close'),obs('y','close',100,old='close')]))
    k.observations(1001,[obs('correct','close',99,t=1001,old='close')]);reject('superseded correction target',lambda:k.observations(1002,[obs('x','close',101,t=1002,old='close')]))
    check('new decision sees correction',k.decide(1002,'D2','A',p,s)['gate']['gate'],'BLOCK');reject('blocked decision cannot review',lambda:k.review(1003,'D2'));reject('duplicate decision id',lambda:k.decide(1003,'D','A',p,s));reject('unknown decision',lambda:k.review(1003,'none'))
    k=fresh();k.observations(1010,[obs('down','close',94,e=1009,t=1010)]);check('refute',k.review(1010,'D')['outcome'],'REFUTED');k.observations(1020,[obs('up','close',111,e=1019,t=1020)]);check('first decisive persists',k.review(1020,'D')['outcome'],'REFUTED')
    k=fresh();k.observations(1010,[obs('down','close',94,e=1009,t=1010),obs('up','close',111,e=1009,t=1010)]);check('atomic conflict',k.review(1010,'D')['outcome'],'OPEN_UNRESOLVED');k.observations(1020,[obs('fixed','close',94,e=1009,t=1020,old='up')]);check('resolved conflict at correction receipt',k.review(1020,'D')['outcome'],'REFUTED')
    k=fresh();k.observations(1101,[obs('late','close',111,e=1099,t=1100)]);check('logged after deadline',k.review(1101,'D')['outcome'],'EXPIRED_UNRESOLVED')
    k=fresh();k.observations(1000,[obs('same','close',111,e=1000,t=1000)]);check('same decision timestamp excluded',k.review(1001,'D')['outcome'],'OPEN_UNRESOLVED')
    k=fresh();k.observations(1010,[obs('late','close',111,e=999,t=1010)]);check('predecision event not outcome',k.review(1100,'D')['outcome'],'EXPIRED_UNRESOLVED')
    k=fresh();k.observations(1100,[obs('edge','close',111,e=1099,t=1100)]);check('deadline inclusive',k.review(1100,'D')['outcome'],'CONFIRMED_OBSERVED')
    k=fresh();x=k.export();x[0]['body']['items'][0]['evidence']['value']=4;check('export detached',k.export()[0]['body']['items'][0]['evidence']['value'],100)
    k=Journal();k.observations(998,initial);d=k.decide(1000,'W','A',replace(p,action='WAIT'),s);check('wait retained',d['gate']['gate'],'WAIT_UNVERIFIED');reject('wait outcome review rejected',lambda:k.review(1001,'W'))
    check('R47 regression',r47.self_test()['test_count'],52)
    return {'scope':'synthetic decision journal; no execution; external head needed for tamper/truncation detection','test_count':len(tests),'tests':tests,'example_head':j.head},j.export()

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--self-test',action='store_true');ap.add_argument('--example-journal',action='store_true');args=ap.parse_args()
    if args.self_test==args.example_journal: ap.error('choose exactly one mode')
    tests,example=self_test();print(json.dumps(tests if args.self_test else example,ensure_ascii=False,indent=2,sort_keys=True))
