"""R127: read-only trace adapter and evidence-backed admission ledger, synthetic only.
Requires prior R120/R124/R126 files in same directory. No live execution.
"""
import argparse, hashlib, json, runpy
from pathlib import Path
from collections import Counter
import numpy as np
ROOT=Path(__file__).parent
PARENTS={'Evidence_Ledger':'798ee9a2ebf9199064d9fb8d502396aea3798fe0f837a119a457243997953d63','Integration':'62d2f2fa19717d4565048a47496bdd983b357670f67a8a6af3c26c02e4a25472','Recovery':'8b33b35849d7a6c7dfbb1de0220dff22ba5beb3e2bd9e3faea4dfa5f9739e225'}
for name,h in PARENTS.items():
    if hashlib.sha256((ROOT/f'Chappy_Trading_Admission_{name}_Study_v0.1.py').read_bytes()).hexdigest()!=h:raise ValueError('parent '+name)
R=runpy.run_path(str(ROOT/'Chappy_Trading_Admission_Recovery_Study_v0.1.py'));G=R['G']; Q,H,A,B,K=R['Q'],R['H'],R['A'],R['B'],R['K']; SP=G['SP']; MODES=G['MODES']; SEEDS=range(127000,127008)
def digest(v):return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':')).encode()).hexdigest()
PLAN=dict(parents=PARENTS,seeds=list(SEEDS),modes=MODES,cases=R['CASES'],prior_spent=15,prior_qualification={B:1},cap=35,scope='state7 full support, replay only; one open batch, fixed routes; restart validates first absolute alarm and cooling',thresholds=K)
class Ledger:
    def __init__(self,mode,request):
        if mode not in MODES or type(request) is not bool:raise ValueError('mode/request')
        self.mode=mode;self.request=request;self.rows=[];self.entries=[];self.batches=[];self.gen={B:1};self.ad={};self.active=None;self.spent=15
    def snapshot(self):return digest(dict(rows=self.rows,entries=self.entries,batches=self.batches,gen=self.gen,ad=self.ad,spent=self.spent))
    def pending(self):
        b=self.active
        if b is None:return []
        t=len(self.rows);out=[]
        for j in b['js']:
            i=b['counts'][j]
            if i<len(b['schedule']) and j not in b['passed']:
                n,w=b['schedule'][i]
                if t==b['start']+n and not (b['route']=='restart' and t==H):out.append(j)
        return out
    def done(self):
        b=self.active
        return b is not None and not self.pending() and (bool(b['passed']) or all(b['counts'][j]==len(b['schedule']) for j in b['js']) or (b['route']=='restart' and len(self.rows)==H))
    def ingest(self,y):
        if type(y) is not int or y not in (-1,1) or len(self.rows)>=H or self.pending() or self.done():return False
        self.rows.append(y);return True
    def specification(self,route):
        t=len(self.rows);left=35-self.spent
        if self.active is not None or any(b['route']==route for b in self.batches):return None
        if route=='restart':
            ad=self.ad.get('recovery1') or self.ad.get('recovery2')
            if not ad or not left or t>=H:return None
            j,s=ad;stop=next((e for e in range(s+32,t+1,32) if sum(v==int(Q[j,7]) for v in self.rows[e-32:e])<=R['L']),None)
            if stop is None or t!=stop+256:return None
            return (j,),tuple((n,n) for n in SP[min(5,left)])
        if route not in ('parallel','recovery1','recovery2') or t!={'parallel':0,'recovery1':1024,'recovery2':2048}[route]:return None
        if route=='parallel' and not self.request:return None
        if route=='recovery2' and ('recovery1' in self.ad or not any(b['route']=='recovery1' for b in self.batches)):return None
        cap=0 if self.mode=='RECOVERY_FIRST' and route=='parallel' else 2
        if self.mode=='RESERVED':cap=2 if route=='recovery1' else 1
        if self.mode in ('FLEX','FLEX_SHORT',*G['NEW']):cap=left//5
        k=5
        if self.mode in ('FLEX_SHORT',*G['NEW']) and route=='recovery2' and left>=2:cap=2;k=min(5,left//2)
        js=((A,) if route=='parallel' else (A,B))[:cap]
        if not js:return None
        ns=SP[k] if self.mode in G['NEW'] and route=='recovery2' else tuple(K)[:k]
        schedule=tuple((n,int(self.mode[5:]) if self.mode.startswith('FRESH') and route=='recovery2' and n==256 else n) for n in ns)
        return js,schedule
    def open(self,route,js,schedule):
        spec=self.specification(route)
        if spec is None or spec!=(tuple(js),tuple(schedule)):return False
        reserve=len(js)*len(schedule)
        if self.spent+reserve>35:return False
        b=dict(id=len(self.batches),route=route,start=len(self.rows),end=None,js=tuple(js),schedule=tuple(schedule),counts={j:0 for j in js},gens={j:self.gen.get(j,0)+1 for j in js},passed=[],before=self.spent,reserved=reserve)
        self.batches.append(b);self.active=b;return True
    def spend(self,j,g,n,w):
        b=self.active
        if b is None or any(type(v) is not int for v in (j,g,n,w)) or j not in self.pending() or g!=b['gens'][j] or (n,w)!=b['schedule'][b['counts'][j]] or self.spent>=35:return None
        t=len(self.rows);ix=list(range(t-w,t));wins=sum(self.rows[i]==int(Q[j,7]) for i in ix);ok=wins>=K[w]
        evidence=digest([[i,7,self.rows[i]] for i in ix]);claim=digest([b['id'],j,g,n,w,evidence]);e=dict(route=b['route'],j=j,generation=g,n=n,t=t,w=wins,window=w,passed=ok,indices=ix,evidence_sha=evidence,claim_sha=claim)
        self.entries.append(e);self.spent+=1;b['counts'][j]+=1
        if ok:b['passed'].append(j);self.gen[j]=g
        return e
    def close(self):
        if not self.done():return False
        b=self.active;b['end']=len(self.rows);b['after']=self.spent
        if b['passed']:self.ad[b['route']]=(next(j for j in b['js'] if j in b['passed']),b['end'])
        self.active=None;return True

def replay(y,req,mode,z,s,ck):
    l=Ledger(mode,req)
    def advance(t):
        while len(l.rows)<t:
            if not l.ingest(int(y[len(l.rows)])):raise AssertionError('ingest')
    def audit(route,js,sch,start,end,events):
        advance(start);ck('open',l.open(route,js,sch));b=l.active
        for e in events:
            advance(e['t']);q=l.spend(e['j'],b['gens'][e['j']],e['n'],e['window']);ck('trace_look',q is not None and (q['w'],q['passed'])==(e['w'],e['pass']))
            ck('evidence',q['indices']==list(range(e['t']-e['window'],e['t'])) and q['evidence_sha']==digest([[i,7,int(y[i])] for i in q['indices']]))
        advance(end);ck('close',l.close());ck('reserved',b['before']+b['reserved']<=35 and b['after']-b['before']<=b['reserved'])
    for b in z['batches']:
        audit(b['route'],b['js'],b['schedule'],b['start'],b['end'],[e for e in z['entries'] if e['route']==b['route']])
    ck('initial_trace',l.ad==z['admissions'] and l.spent==z['spent'])
    if s['start'] is not None:
        j=s['ad'][0];ns=SP[min(5,35-l.spent)];events=[dict(j=j,t=t,n=n,window=n,w=w,**{'pass':ok}) for t,n,w,ok in s['looks']];end=s['resume'] or min(H,s['start']+ns[-1]);audit('restart',(j,),tuple((n,n) for n in ns),s['start'],end,events)
    ck('total_spent',l.spent==s['spent']<=35);ck('resume',l.ad.get('restart')==((s['ad'][0],s['resume']) if s['resume'] else None));ck('claims_unique',len({e['claim_sha'] for e in l.entries})==len(l.entries))
    used={};last=-1
    for b in l.batches:
        ck('batch_disjoint',last<=b['start']<=b['end']);last=b['end']
        for e in (e for e in l.entries if e['route']==b['route']):
            ck('cross_batch_evidence',all(i not in used or used[i]==b['id'] for i in e['indices']));used.update({i:b['id'] for i in e['indices']})
    return l

def study():
    c=Counter();summary=Counter();examples={}
    def ck(k,v):
        if not v:raise AssertionError(k)
        c[k]+=1
    def reject(l,fn):
        old=l.snapshot();ck('reject',not fn());ck('reject_atomic',old==l.snapshot())
    for name,(req,phases) in R['CASES'].items():
        ps=np.zeros(H,dtype=int)
        for t,v in phases:ps[t:]=v
        for seed in SEEDS:
            y=np.where(np.random.default_rng(seed).random(H)<ps/100,1,-1)
            for mode in MODES:
                z=G['simulate'](y,req,mode)
                for p in ('STOP','RESTART'):
                    s=R['run'](y,z,p);l=replay(y,req,mode,z,s,ck);summary['trials']+=1;summary['looks']+=len(l.entries);summary['restart_batches']+=int(s['start'] is not None);summary['resumes']+=int(s['resume'] is not None);summary['sparse_looks']+=sum(e['n']==256 for e in l.entries);summary['suffix_looks']+=sum(e['window']<e['n'] for e in l.entries)
                    if seed==SEEDS[0] and s['resume'] and mode=='SPREAD':examples[name]=dict(batches=l.batches,entries=l.entries)
    # Adversarial API fixtures, fixed balanced stream then deterministic valid recovery.
    l=Ledger('SPREAD',True);sch=tuple((n,n) for n in K)
    reject(l,lambda:l.open('parallel',(A,),((256,256),)));reject(l,lambda:l.open('parallel',(B,),sch));ck('fixture_open',l.open('parallel',(A,),sch));reject(l,lambda:l.close());reject(l,lambda:l.spend(A,1,16,16));reject(l,lambda:l.ingest(0))
    for i in range(16):ck('fixture_append',l.ingest(1 if i%2==0 else -1))
    reject(l,lambda:l.ingest(1));reject(l,lambda:l.spend(A,2,16,16));reject(l,lambda:l.spend(A,1,16,32));reject(l,lambda:l.spend(B,1,16,16));ck('fixture_spend',l.spend(A,1,16,16) is not None);reject(l,lambda:l.spend(A,1,16,16));reject(l,lambda:l.close())
    # All remaining parallel/recovery1 looks fail: 5+10 consumed, five left for two sparse lanes.
    for n in tuple(K)[1:]:
        while len(l.rows)<n:l.ingest(1 if len(l.rows)%2==0 else -1)
        ck('fixture_spend',l.spend(A,1,n,n) is not None)
    ck('fixture_close',l.close())
    while len(l.rows)<1024:l.ingest(1 if len(l.rows)%2==0 else -1)
    ck('fixture_open',l.open('recovery1',(A,B),sch))
    for n in K:
        while len(l.rows)<1024+n:l.ingest(1 if len(l.rows)%2==0 else -1)
        for j in (A,B):ck('fixture_spend',l.spend(j,l.active['gens'][j],n,n) is not None)
    ck('fixture_close',l.close())
    while len(l.rows)<2048:l.ingest(1 if len(l.rows)%2==0 else -1)
    reject(l,lambda:l.open('recovery2',(A,B),sch));ck('fixture_open',l.open('recovery2',(A,B),((16,16),(256,256))))
    for i in range(16):l.ingest(1 if i%2==0 else -1)
    ck('fixture_spend',l.spend(A,1,16,16) is not None);reject(l,lambda:l.close());reject(l,lambda:l.ingest(1));ck('fixture_spend',l.spend(B,2,16,16) is not None)
    while len(l.rows)<2304:l.ingest(int(Q[A,7]))
    reject(l,lambda:l.spend(A,1,256,128));ck('fixture_spend',l.spend(A,1,256,256)['passed']);ck('fixture_spend',not l.spend(B,2,256,256)['passed']);ck('fixture_close',l.close());ck('fixture_remaining',l.spent==34)
    reject(l,lambda:l.open('restart',(A,),((256,256),)))
    while len(l.rows)<2592:l.ingest(-int(Q[A,7]))
    ck('fixture_restart',l.open('restart',(A,),((256,256),)));reject(l,lambda:l.spend(A,1,256,256))
    while len(l.rows)<2848:l.ingest(int(Q[A,7]))
    ck('fixture_spend',l.spend(A,2,256,256)['passed']);ck('fixture_close',l.close());ck('fixture_budget',l.spent==35 and l.ad['restart']==(A,2848));reject(l,lambda:l.open('restart',(A,),((256,256),)));examples['full_budget_fixture']=dict(batches=l.batches,entries=l.entries)
    return dict(passed=sum(c.values()),counts=dict(c),summary=dict(summary),plan_sha=digest(PLAN)),dict(plan=PLAN,summary=dict(summary),examples=examples)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--outdir',type=Path,required=True);a=p.parse_args();a.outdir.mkdir(exist_ok=True);t,e=study()
    for k,v in [('tests',t),('examples',e)]:(a.outdir/f'Trading_Round127_{k}.json').write_text(json.dumps(v,sort_keys=True,indent=2)+'\n')
    print(json.dumps(t))
