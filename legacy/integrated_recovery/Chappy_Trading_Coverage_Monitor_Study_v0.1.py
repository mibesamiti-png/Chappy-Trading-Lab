"""R130 synthetic coverage and monitor latency. No market data, orders or live policy changes."""
import argparse, hashlib, json, runpy, math
from pathlib import Path
from collections import Counter
from fractions import Fraction
import numpy as np
from scipy.stats import binom
ROOT=Path(__file__).parent
PARENTS={'Chappy_Trading_Eligible_Lifecycle_Study_v0.1.py':'73292f378ce7a84b6d07b682a95d7c4f519f682f5e670da06b96655ae95fd395','Chappy_Trading_Observation_Coverage_Study_v0.1.py':'7b99b2893770cabee0d84b02c6a9d0f700fce72587554ca41e33e2f141f872db'}
for p,h in PARENTS.items():
    if hashlib.sha256((ROOT/p).read_bytes()).hexdigest()!=h: raise ValueError(p)
R=runpy.run_path(str(ROOT/next(iter(PARENTS)))); C=runpy.run_path(str(ROOT/list(PARENTS)[1])); digest=R['digest']
N,K=R['PLAN']['monitor']; H=2048; WINDOW=512; SEEDS=range(130000,130256)
# support %, win % in initial 512 and remaining slots, receipt % conditional on win/loss
CASES={'stable_rare':(1,90,90,100,100),'absent':(0,90,90,100,100),'persistent_rare':(1,10,10,100,100),'persistent_5pct':(5,10,10,100,100),'temporary_5pct':(5,10,90,100,100),'temporary_25pct':(25,10,90,100,100),'missing_all':(25,90,90,0,0),'missing_wins':(25,90,90,1,100),'missing_losses':(25,10,10,100,1),'missing_random':(25,10,10,50,50)}
PLAN=dict(parents=PARENTS,horizon=H,window=WINDOW,seeds=list(SEEDS),cases=CASES,monitor=[N,K],coverage='R79 planned eligible vs received; no imputation',modes=['COMPLETE','OBSERVED_ONLY','BOUNDS'],scope='fixed eligible clock from diagnostic origin, no trading; eligibility fully observed; outcomes binary or missing')
def inspect(eligible,received):
    if not eligible:return 'NO_OPPORTUNITY'
    if not received:return 'NO_OUTCOMES'
    if received<eligible:return 'PARTIAL'
    return 'COMPLETE'
def scan(e,r,mode):
    # r: -1 missing, 0 loss, 1 win. Full blocks partition known eligible events.
    ids=[]; groups=[]; alarm=None
    for i in range(len(e)):
        if not e[i] or (mode=='OBSERVED_ONLY' and r[i]<0):continue
        ids.append(i)
        if len(ids)==N:
            w=sum(int(r[j]==1) for j in ids); missing=sum(int(r[j]<0) for j in ids)
            status='UNKNOWN' if missing else ('ALARM' if w<=K else 'CLEAR')
            if mode=='BOUNDS':status='ALARM' if w+missing<=K else 'CLEAR' if w>K else 'UNKNOWN'
            groups.append((i+1,w,missing,status,tuple(ids)))
            if status=='ALARM' and alarm is None:alarm=i+1
            ids=[]
    return alarm,groups

def oracle(e,r,mode):
    ids=np.flatnonzero(e & ((r>=0) if mode=='OBSERVED_ONLY' else True));groups=[]
    for a in range(0,len(ids)-N+1,N):
        ix=ids[a:a+N]; v=r[ix]; lo=int(np.count_nonzero(v==1)); hi=lo+int(np.count_nonzero(v<0)); m=hi-lo
        status=('ALARM' if hi<=K else 'CLEAR' if lo>K else 'UNKNOWN') if mode=='BOUNDS' else ('UNKNOWN' if m else 'ALARM' if lo<=K else 'CLEAR')
        groups.append((int(ix[-1])+1,lo,m,status,tuple(map(int,ix))))
    return next((g[0] for g in groups if g[3]=='ALARM'),None),groups

def study():
    c=Counter(); summaries={}; exact=[]
    def ck(k,v):
        if not v:raise AssertionError(k)
        c[k]+=1
    for p in (1,5,25,100):
        for t in (128,256,512,1024,2048,4096):
            # exact integer mass for Pr(Bin(t,p/100)>=32), compute tail via complement
            q=100-p; den=100**t
            low=sum(math.comb(t,i)*p**i*q**(t-i) for i in range(min(N,t+1)))
            v=float(Fraction(den-low,den)); s=float(binom.sf(N-1,t,p/100))
            ck('exact_probability',math.isclose(v,s,rel_tol=1e-10,abs_tol=1e-15));exact.append(dict(support_pct=p,slots=t,probability=v,mean_slots=N*100/p))
    for name,(p,w1,w2,ow,ol) in CASES.items():
        agg={m:Counter() for m in PLAN['modes']}; coverage=Counter(); observed=eligible=0
        for seed in SEEDS:
            rng=np.random.default_rng(seed); e=rng.random(H)<p/100; w=rng.random(H)<np.where(np.arange(H)<WINDOW,w1/100,w2/100); receipt=rng.random(H)<np.where(w,ow/100,ol/100); r=np.where(receipt,w.astype(int),-1); truth=w.astype(int)
            a=int(e[:WINDOW].sum()); b=int((e[:WINDOW]&(r[:WINDOW]>=0)).sum()); coverage[inspect(a,b)]+=1; observed+=b;eligible+=a
            for m in PLAN['modes']:
                alarm,groups=scan(e,r,m);ck('oracle', (alarm,groups)==oracle(e,r,m)); z=agg[m];z['alarm_total']+=alarm is not None; z['alarm_first512']+=alarm is not None and alarm<=WINDOW;z['alarm_time_sum']+=alarm or 0
                for t,lo,missing,status,ix in groups:
                    ck('support',len(ix)==N and all(e[j] for j in ix) and t==ix[-1]+1);ck('no_future',all(j<t for j in ix));z['groups']+=1;z['unknown_groups']+=status=='UNKNOWN'
                    if m=='BOUNDS':ck('robust_bounds',status=='UNKNOWN' or (status=='ALARM')==(sum(truth[j] for j in ix)<=K))
                if seed==SEEDS[0]:
                    cut=512; rr=r.copy();rr[cut:]=1; ee=e.copy();ee[cut:]=~ee[cut:];ck('future_mask', [g for g in groups if g[0]<=cut]==[g for g in scan(ee,rr,m)[1] if g[0]<=cut])
                if ow==ol==100:ck('complete_equivalence', (alarm,groups)==scan(e,r,'COMPLETE'))
        summaries[name]={'coverage_first512':dict(coverage),'mean_eligible':eligible/len(SEEDS),'mean_received':observed/len(SEEDS),'modes':{m:dict(z,mean_alarm_time=z['alarm_time_sum']/z['alarm_total'] if z['alarm_total'] else None) for m,z in agg.items()}}
    fixtures={}
    for name,vals in {'none':[], 'all_missing':[-1]*32,'certain_bad':[0]*28+[-1]*4,'certain_good':[1]*9+[-1]*23,'ambiguous':[0]*23+[-1]*9}.items():
        e=np.ones(len(vals),dtype=bool);r=np.array(vals,dtype=int);s=[dict(id=str(i),group='A',due=i) for i in range(len(vals))];o=[dict(id='r'+str(i),opportunity=str(i),received=i,bps=100 if v==1 else -100) for i,v in enumerate(vals) if v>=0]; cov=C['fit'](s,o,cutoff=len(vals))['groups']['A']; ck('R79_coverage',cov['planned']==len(vals) and cov['observed']==len(o)); expected={'none':None,'all_missing':'UNKNOWN','certain_bad':'ALARM','certain_good':'CLEAR','ambiguous':'UNKNOWN'}[name]; a,g=scan(e,r,'BOUNDS');ck('fixture',(g[0][3] if g else None)==expected);fixtures[name]={'coverage':cov,'groups':g,'alarm':a}
    return {'passed':sum(c.values()),'checks':dict(c)},dict(plan=PLAN,plan_sha=digest(PLAN),exact=exact,cases=summaries,fixtures=fixtures)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',default='.');a=p.parse_args();t,e=study();out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    for n,z in [('tests',t),('examples',e)]: (out/f'Trading_Round130_{n}.json').write_text(json.dumps(z,sort_keys=True,indent=2)+'\n')
    print(t)
