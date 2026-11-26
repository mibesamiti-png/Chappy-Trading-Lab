"""R139: fixed external audit route adapter, synthetic only; not live order authority."""
import argparse, hashlib, json, runpy
from collections import Counter
from pathlib import Path
import numpy as np
ROOT=Path(__file__).parent
PARENTS={'Audit_Value':'88d66682d24ad0183d5914bb5b6e66b37f72182043074c8fe67d77fe7d000708','Admission_Evidence_Ledger':'798ee9a2ebf9199064d9fb8d502396aea3798fe0f837a119a457243997953d63'}
for p,h in PARENTS.items():
    if hashlib.sha256((ROOT/f'Chappy_Trading_{p}_Study_v0.1.py').read_bytes()).hexdigest()!=h:raise ValueError(p)
R,L=[runpy.run_path(str(ROOT/f'Chappy_Trading_{p}_Study_v0.1.py')) for p in PARENTS]; A=R['A'];H=R['H'];K=R['K'];digest=L['digest'];J=9
if L['K'][32]!=K:raise ValueError('threshold')
SEEDS=range(139000,139064); PLAN=dict(parents=PARENTS,seed=list(SEEDS),audit=list(A),horizon=H,threshold=K,cap=35,route='one external purchase at t0; candidate9 fixed; same canonical market-slot across sources, no cross-batch reuse; all purchases charged; one look at fixed deadline; conflict latches stop; synthetic local adapter')
def key(t):return ('synthetic',t)
def prior_ids(entries):return {key(i+1) for e in entries for i in e['indices']}
class Ledger:
    def __init__(self,spent=34,cash=100000,prior=(),generation=1):
        if type(spent)!=int or not 0<=spent<=35 or type(cash)!=int or cash<0:raise ValueError('init')
        self.spent=spent;self.cash=cash;self.prior=set(prior);self.generation=generation;self.t=0;self.order=None;self.reports=[];self.values={};self.conflict=False;self.entry=None;self.closed=False;self.stop=None;self.cost=0
    def snapshot(self):return digest([self.spent,self.cash,sorted(self.prior),self.generation,self.t,self.order,self.reports,self.values,self.conflict,self.entry,self.closed,self.stop,self.cost])
    def open(self,providers,delay):
        if self.order is not None or self.t!=0 or type(delay)!=int or delay<0 or self.spent>=35 or not isinstance(providers,dict) or not providers or any(p not in ('A','B') or type(c)!=int or c<0 for p,c in providers.items()) or any(key(t) in self.prior for t in A):return False
        cost=len(A)*sum(providers.values())
        if cost>self.cash:return False
        self.order=dict(providers=dict(sorted(providers.items())),due=A[-1]+delay,ids=list(A),j=J,g=self.generation+1);self.cash-=cost;self.cost=cost;return True
    def advance(self,t):
        if type(t)!=int or not self.t<=t<=H or (self.order and not self.closed and self.t<=min(H,self.order['due'])<t):return False
        self.t=t;return True
    def receive(self,p,t,w):
        if self.order is None or p not in self.order['providers'] or type(t)!=int or t not in A or t>self.t or type(w)!=int or w not in (0,1):return False
        if [p,t,w] in [r[1:] for r in self.reports]:return True
        self.reports.append([self.t,p,t,w]);old=self.values.get(t)
        if old is not None and old!=w:
            self.conflict=True
            if self.stop is None:self.stop=self.t
        elif old is None:self.values[t]=w
        return True
    def finalize(self):
        if self.order is None or self.closed or self.t!=min(H,self.order['due']):return False
        self.closed=True
        if self.t==H or self.conflict:return True
        rows=[[list(key(t)),self.values.get(t)] for t in A];w=sum(v==1 for _,v in rows);ev=digest(rows);ok=w>=K
        self.entry=dict(t=self.t,j=J,g=self.order['g'],n=len(A),wins=w,passed=ok,evidence_sha=ev,claim_sha=digest(['external',J,self.order['g'],ev]),rows=rows,provenance=[r.copy() for r in self.reports]);self.spent+=1;self.prior.update(key(t) for t in A)
        if ok:self.generation+=1
        return True
    def permit(self,t):return bool(self.entry and self.entry['passed'] and self.entry['t']<t<=H and (self.stop is None or t<=self.stop) and t<=self.t+1)

def study():
    c=Counter();summary={};fixtures={}
    def ck(k,b):
        if not b:raise AssertionError(k)
        c[k]+=1
    def reject(l,f):
        s=l.snapshot();ck('reject',not f());ck('atomic',s==l.snapshot())
    def send(l,p,t,w):ck('receive',l.receive(p,t,w))
    # Same underlying observations, duplicate supplier has same receipts; independent cost, no extra vote.
    for name,(rw,rl) in R['SOURCES'].items():
      for delay in R['DELAY']:
        for world in ('good','bad'):
          z=Counter()
          for seed in SEEDS:
            _,ys=R['R']['world'](seed);y=ys[world];w=y[np.array(A)-1];u=np.random.default_rng(seed+1000000).integers(0,100,len(A));r=u<np.where(w==1,rw,rl);ls=[]
            for providers in ({'A':100},{'A':100,'B':100}):
              l=Ledger();ck('open',l.open(providers,delay));due=min(H,A[-1]+delay)
              for t,v,rec in zip(A,w,r):
                at=t+delay
                if at>due:continue
                ck('advance',l.advance(at))
                if rec:
                    for p in providers:send(l,p,t,int(v))
              ck('deadline',l.advance(due));ck('finalize',l.finalize());ck('end',l.advance(H));a=R['decision'](w,r,delay);passed=a is not None;ck('parent_decision',bool(l.entry and l.entry['passed'])==passed);ck('budget',l.spent==34+int(due<H));ck('cost',l.cost==32*sum(providers.values()) and l.cash==100000-l.cost)
              if l.entry:
                ck('unique_obs',len({tuple(i) for i,_ in l.entry['rows']})==32);ck('win_oracle',l.entry['wins']==int(np.count_nonzero((w==1)&r)));ck('provenance',len(l.entry['provenance'])==int(r.sum())*len(providers));ck('hash',l.entry['evidence_sha']==digest(l.entry['rows']))
              acts=[l.permit(t) for t in range(1,H+1)];ck('authority',acts==[bool(passed and t>a) for t in range(1,H+1)]);net=sum((800 if v else -1200) for v,b in zip(y,acts) if b)-H-200-l.cost;ls.append((l,net));z['passes']+=int(passed) if len(providers)==1 else 0
            a,b=ls;ck('duplicate_no_weight',a[0].entry is None and b[0].entry is None or a[0].entry['claim_sha']==b[0].entry['claim_sha']);ck('duplicate_cost',a[1]-b[1]==3200);z['single_net']+=a[1];z['double_net']+=b[1]
          summary[f'{name}_{delay}_{world}']=dict(passes=z['passes'],trials=len(SEEDS),single_net=z['single_net']/len(SEEDS),double_net=z['double_net']/len(SEEDS))
    # Existing R120 native ledger evidence IDs translated using the shared synthetic stream/slot mapping.
    old=L['Ledger']();ck('native_open',old.open('initial',[J]))
    for i in range(64):
        ck('native_ingest',old.ingest(0,1 if i%2==0 else -1))
        if i+1 in (16,32,64):ck('native_spend',old.spend('initial',J,1,i+1) is not None)
    ck('native_close',old.close());l=Ledger(prior=prior_ids(old.entries));reject(l,lambda:l.open({'A':100},0));fixtures['native_overlap']=sorted(t for _,t in l.prior if t in A)
    for spent,cash in ((35,100000),(34,3199)):
        l=Ledger(spent,cash);reject(l,lambda:l.open({'A':100},0))
    l=Ledger();ck('open',l.open({'A':100,'B':100},0));reject(l,lambda:l.open({'A':100},0));reject(l,lambda:l.receive('A',40,1));reject(l,lambda:l.receive('C',40,1));reject(l,lambda:l.finalize());reject(l,lambda:l.advance(289))
    for t in A:
        ck('advance',l.advance(t));send(l,'A',t,1)
    s=l.snapshot();send(l,'A',40,1);ck('idempotent',s==l.snapshot());send(l,'B',40,0);ck('conflict',l.conflict);ck('finalize',l.finalize());ck('no_conflict_admission',l.entry is None and l.spent==34 and l.cost==6400);fixtures['conflict_before']=dict(spent=l.spent,cost=l.cost,stop=l.stop)
    l=Ledger();ck('open',l.open({'A':100,'B':100},0));ck('advance',l.advance(288))
    for t in A:send(l,'A',t,1)
    ck('finalize',l.finalize());s=digest(l.entry);ck('next_action',l.permit(289) and not l.permit(288));reject(l,lambda:l.finalize());ck('advance',l.advance(300));send(l,'B',40,0);ck('immutable',digest(l.entry)==s);ck('advance',l.advance(H));ck('revocation',l.permit(300) and not l.permit(301));fixtures['conflict_after']=dict(admission=l.entry['t'],stop=l.stop,spent=l.spent,cost=l.cost,claim=l.entry['claim_sha'])
    # Missing results cannot become independent samples. Late first receipt does not rewrite historical claim.
    l=Ledger();ck('open',l.open({'A':100},0));ck('advance',l.advance(288))
    for t in A[:27]:send(l,'A',t,1)
    ck('finalize',l.finalize());s=digest(l.entry);ck('not_pass',not l.entry['passed']);ck('advance',l.advance(289));send(l,'A',A[27],1);ck('late_immutable',digest(l.entry)==s and not l.permit(290));fixtures['late']=dict(wins=l.entry['wins'],current_wins=sum(l.values.values()),passed=l.entry['passed'])
    return dict(passed=sum(c.values()),checks=dict(c)),dict(plan=PLAN,plan_sha=digest(PLAN),summary=summary,fixtures=fixtures)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',default='.');a=p.parse_args();t,e=study();o=Path(a.out);o.mkdir(parents=True,exist_ok=True)
    for n,z in [('tests',t),('examples',e)]:(o/f'Trading_Round139_{n}.json').write_text(json.dumps(z,sort_keys=True,indent=2)+'\n')
    print(t)
