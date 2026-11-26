"""R131 synthetic delayed observation monitor. No market data or live execution."""
import argparse, hashlib, json, runpy, math
from pathlib import Path
from collections import Counter, defaultdict
import numpy as np
ROOT=Path(__file__).parent
P=ROOT/'Chappy_Trading_Coverage_Monitor_Study_v0.1.py'
PIN='7a4b57b376dd80b2373815f07ed99ba4abbeaabb9da8db610f436946a53fc0ac'
if hashlib.sha256(P.read_bytes()).hexdigest()!=PIN: raise ValueError('R130 hash')
R=runpy.run_path(str(P)); N,K=R['N'],R['K']; digest=R['digest']
H=1024; GRACE=16; SEEDS=range(131000,131128)
# eligible %, initial win %, later win %, receipt %, delay maximum, wrong first report %, correction delay
CASES={'stable_immediate':(25,90,90,100,0,0,0),'bad_immediate':(25,10,10,100,0,0,0),'bad_delayed':(25,10,10,100,32,0,0),'stable_delayed':(25,90,90,100,32,0,0),'bad_missing':(25,10,10,50,32,0,0),'stable_missing':(25,90,90,50,32,0,0),'corrections':(25,90,90,100,8,30,32),'rare_bad':(5,10,10,100,32,0,0),'absent':(0,90,90,100,0,0,0)}
MODES=('IMMEDIATE','WAIT','WAIT_HOLD')
PLAN=dict(parent=PIN,horizon=H,grace=GRACE,monitor=[N,K],seeds=list(SEEDS),cases=CASES,modes=MODES,scope='known eligibility, binary versioned outcomes; same-tick receipts before seal; sealed decisions immutable; changing a used value after seal quarantines; unknown only halts WAIT_HOLD; no auto resume; no trades')
def status(vals):
    w=sum(v==1 for v in vals); u=vals.count(None)
    return 'ALARM' if w+u<=K else 'CLEAR' if w>K else 'UNKNOWN'
class Engine:
    def __init__(self,mode):
        self.mode=mode;self.t=0;self.rows={};self.group=[];self.pending=[];self.sealed=[];self.owner={};self.audit=[];self.stop=None
    def receipt(self,i,rev,value):
        if type(i)!=int or i not in self.rows or type(rev)!=int or type(value)!=int or value not in (0,1):raise ValueError('receipt')
        old=self.rows[i]
        if rev!=(old[0]+1 if old else 1):raise ValueError('revision')
        self.rows[i]=(rev,value)
        if i in self.owner:
            g,used=self.owner[i];kind='LATE_RECEIPT' if old is None else 'CORRECTION'
            self.audit.append((self.t,i,rev,value,g,kind))
            if used is not None and value!=used and self.stop is None:self.stop=(self.t,'CORRECTION')
    def step(self,eligible,receipts):
        self.t+=1
        if eligible:
            self.rows[self.t]=None;self.group.append(self.t)
            if len(self.group)==N:
                self.pending.append((self.t,tuple(self.group)));self.group=[]
        for i,rev,value in receipts:self.receipt(i,rev,value)
        remaining=[]
        for close,ids in self.pending:
            vals=tuple(self.rows[i][1] if self.rows[i] else None for i in ids)
            if self.mode!='IMMEDIATE' and None in vals and self.t<close+GRACE:
                remaining.append((close,ids));continue
            result=status(vals);g=len(self.sealed);self.sealed.append((self.t,close,ids,vals,result))
            for i,v in zip(ids,vals):self.owner[i]=(g,v)
            if self.stop is None and (result=='ALARM' or (result=='UNKNOWN' and self.mode=='WAIT_HOLD')):self.stop=(self.t,result)
        self.pending=remaining
    def result(self):return dict(sealed=self.sealed,audit=self.audit,stop=self.stop,pending=[(c,ids) for c,ids in self.pending],partial=tuple(self.group))
def run(e,events,mode):
    x=Engine(mode);by=defaultdict(list)
    for t,i,r,v in events:by[t].append((i,r,v))
    for t,eligible in enumerate(e,1):x.step(eligible,by[t])
    return x.result()
def oracle(e,events,mode):
    # Independent offline event-time reconstruction; never uses receipts after a decision boundary.
    times=defaultdict(list)
    for t,i,r,v in events:
        if t<=len(e):times[i].append((t,r,v))
    ids=[i for i,v in enumerate(e,1) if v]; sealed=[];pending=[]
    for j in range(0,len(ids)-N+1,N):
        group=tuple(ids[j:j+N]);close=group[-1];ends=[times[i][0][0] if times[i] else math.inf for i in group]
        t=close if mode=='IMMEDIATE' else min(close+GRACE,max(close,max(ends)))
        if t>len(e):pending.append((close,group));continue
        vals=tuple(next((v for a,r,v in reversed(times[i]) if a<=t),None) for i in group)
        w=vals.count(1);u=vals.count(None);s='ALARM' if w+u<=K else 'CLEAR' if w>K else 'UNKNOWN'
        sealed.append((int(t),close,group,vals,s))
    sealed.sort(key=lambda g:(g[0],g[1])); audit=[]; candidates=[];owned={}
    for g,(t,c,group,vals,s) in enumerate(sealed):
        if s=='ALARM' or (s=='UNKNOWN' and mode=='WAIT_HOLD'):candidates.append((t,1,c,s))
        for i,v in zip(group,vals):owned[i]=(g,t,v)
    for t,i,r,v in events:
        if t>len(e) or i not in owned:continue
        g,seal,used=owned[i]
        if t<=seal:continue
        audit.append((t,i,r,v,g,'LATE_RECEIPT' if r==1 else 'CORRECTION'))
        if used is not None and v!=used:candidates.append((t,0,len(audit),'CORRECTION'))
    first=min(candidates) if candidates else None
    return dict(sealed=sealed,audit=audit,stop=(first[0],first[-1]) if first else None,pending=pending,partial=tuple(ids[len(ids)//N*N:]))
def generate(seed,case):
    p,w1,w2,rec,dmax,err,cd=case;rng=np.random.default_rng(seed);e=rng.random(H)<p/100;w=rng.random(H)<np.where(np.arange(H)<512,w1/100,w2/100);events=[]
    for i in np.flatnonzero(e):
        if rng.random()>=rec/100:continue
        t=int(i)+1+int(rng.integers(dmax+1));v=int(w[i]);wrong=rng.random()<err/100
        events.append((t,int(i)+1,1,1-v if wrong else v))
        if wrong:events.append((t+cd,int(i)+1,2,v))
    return e,sorted(events)
def study():
    c=Counter();summaries={};fixtures={}
    def ck(k,v):
        if not v:raise AssertionError(k)
        c[k]+=1
    def test(e,ev,m):
        a=run(e,ev,m);ck('oracle',a==oracle(e,ev,m)); seen=set()
        for t,close,ids,vals,s in a['sealed']:
            ck('support',len(ids)==N and all(e[i-1] for i in ids) and not seen.intersection(ids));seen.update(ids)
            ck('deadline',close<=t<=close+(0 if m=='IMMEDIATE' else GRACE));ck('bounds',s==status(vals));ck('causal',all(i<=close for i in ids))
        return a
    for name,case in CASES.items():
        agg={m:Counter() for m in MODES}
        for seed in SEEDS:
            e,ev=generate(seed,case)
            for m in MODES:
                a=test(e,ev,m);z=agg[m];z['groups']+=len(a['sealed']);z['unknown_groups']+=sum(g[-1]=='UNKNOWN' for g in a['sealed']);z['alarms']+=any(g[-1]=='ALARM' for g in a['sealed']);z['late_receipts']+=sum(g[-1]=='LATE_RECEIPT' for g in a['audit']);z['corrections']+=sum(g[-1]=='CORRECTION' for g in a['audit']);z['pending_at_end']+=len(a['pending']);
                if a['stop']:z['stop_'+a['stop'][1]]+=1;z['stop_time_sum']+=a['stop'][0]
                if seed==SEEDS[0]:
                    cut=512;b=run(e[:cut],ev,m);ck('future_prefix',b['sealed']==[g for g in a['sealed'] if g[0]<=cut] and b['audit']==[g for g in a['audit'] if g[0]<=cut] and b['stop']==(a['stop'] if a['stop'] and a['stop'][0]<=cut else None))
                if name in ('stable_immediate','bad_immediate'):
                    r=np.full(H,-1);r[e]=[v for t,i,rev,v in ev];old=R['scan'](e,r,'BOUNDS');ck('R130_equivalence',[(g[0],g[3]) for g in old[1]]==[(g[0],g[-1]) for g in a['sealed']])
        summaries[name]={m:dict(z,mean_stop_time=z['stop_time_sum']/sum(z['stop_'+k] for k in ('ALARM','UNKNOWN','CORRECTION')) if sum(z['stop_'+k] for k in ('ALARM','UNKNOWN','CORRECTION')) else None) for m,z in agg.items()}
    for name,events in {'late_bad':[(i+12,i,1,0) for i in range(1,33)],'missing':[(i,i,1,0) for i in range(1,24)],'correct_after':[(i,i,1,1) for i in range(1,33)]+[(40,1,2,0)],'correct_before':[(i,i,1,1) for i in range(1,32)]+[(20,1,2,0),(40,32,1,1)],'after_deadline':[(i+60,i,1,0) for i in range(1,33)]}.items():
        e=[True]*32+[False]*64;ev=sorted(events);fixtures[name]={m:test(e,ev,m) for m in MODES}
    ck('late_alarm',fixtures['late_bad']['WAIT']['stop']==(44,'ALARM'));ck('immediate_unchanged',fixtures['late_bad']['IMMEDIATE']['sealed'][0][-1]=='UNKNOWN');ck('unknown_hold',fixtures['missing']['WAIT_HOLD']['stop']==(48,'UNKNOWN'));ck('correction_quarantine',fixtures['correct_after']['WAIT']['stop']==(40,'CORRECTION'));ck('sealed_immutable',fixtures['correct_after']['WAIT']['sealed'][0][3][0]==1);ck('before_seal',fixtures['correct_before']['WAIT']['sealed'][0][3][0]==0);ck('late_after_deadline',fixtures['after_deadline']['WAIT']['sealed'][0][-1]=='UNKNOWN')
    x=Engine('WAIT');x.step(True,[(1,1,1)])
    for args in [(2,1,1),(1,1,0),(1,3,0),(1,2,2),(True,2,1)]:
        before=(dict(x.rows),list(x.audit),x.stop)
        try:x.receipt(*args)
        except ValueError:ck('reject',before==(dict(x.rows),list(x.audit),x.stop))
        else:raise AssertionError('accepted bad receipt')
    return dict(passed=sum(c.values()),checks=dict(c)),dict(plan=PLAN,plan_sha=digest(PLAN),cases=summaries,fixtures=fixtures)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',default='.');a=p.parse_args();t,e=study();out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    for n,z in [('tests',t),('examples',e)]:(out/f'Trading_Round131_{n}.json').write_text(json.dumps(z,sort_keys=True,indent=2)+'\n')
    print(t)
