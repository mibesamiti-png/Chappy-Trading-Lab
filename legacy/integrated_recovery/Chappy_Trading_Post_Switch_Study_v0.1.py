"""R111: bounded post-switch rollback on paired disagreement; synthetic only."""
import argparse, hashlib, json, math, runpy
from pathlib import Path
import numpy as np
P=Path(__file__).with_name('Chappy_Trading_Comparison_Drift_Study_v0.1.py')
if hashlib.sha256(P.read_bytes()).hexdigest()!='47a4909f951cb30b32a7da20f7d99208211fd68c59a55a4bd4cd2e658d9228e0':raise ValueError('R110 hash')
R=runpy.run_path(str(P)); B=R['R']; H=R['H']; JS=R['JS']; V=R['V']; SEEDS=range(111000,111256); BLOCK=32; MAX_LOOKS=H//BLOCK
METHODS=('KEEP','SHADOW','REACTIVE','BLOCK_NAIVE','BLOCK_SPEND')
def limit(den):
    return max(k for k in range(BLOCK+1) if den*sum(math.comb(BLOCK,i) for i in range(k+1))<=2**BLOCK)
K={'BLOCK_NAIVE':limit(20),'BLOCK_SPEND':limit(20*MAX_LOOKS)}
PLAN=dict(seeds=list(SEEDS),cases=R['CASES'],methods=METHODS,horizon=H,initial='R109 EB2048',block=BLOCK,limits=K,max_looks=MAX_LOOKS,rollback_limit=1,fee=200,shadow_fee=1,synthetic_only=True)
SHA=hashlib.sha256(json.dumps(PLAN,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def trigger(d,m):
    ix=np.flatnonzero(d); wins=(d[ix]>0).astype(int)
    if m=='REACTIVE' and len(ix)>=4:
        z=np.flatnonzero(np.convolve(wins,np.ones(4,dtype=int),'valid')<=1)
        if len(z):return int(ix[z[0]+3])+1
    if m in K:
        n=min(len(ix)//BLOCK,MAX_LOOKS); z=np.flatnonzero(wins[:n*BLOCK].reshape(n,BLOCK).sum(axis=1)<=K[m])
        if len(z):return int(ix[(z[0]+1)*BLOCK-1])+1
    return None

def run(x,y,base,m):
    e=base['end']; inc=base['inc']; fin=base['fin']; sw=inc!=fin; d=B['netvec'](x[e:],y[e:],fin)-B['netvec'](x[e:],y[e:],inc); off=trigger(d,m) if sw else None
    t=e+off if off is not None and e+off<H else None
    fee=200*int(t is not None); stop=t if t is not None else H
    obs=stop-e if sw and m!='KEEP' else 0
    delta=-int(d[t-e:].sum())-fee if t is not None else 0
    return dict(net=base['net']+delta-obs,rollback=t,obs=obs,delta=delta,fee=fee,sw=int(sw),n=int(np.count_nonzero(d[:stop-e])) if sw else 0)

def oracle(d,m):
    wins=[]
    for i,v in enumerate(d):
        if not v:continue
        wins.append(v>0)
        if m=='REACTIVE' and len(wins)>=4 and sum(wins[-4:])<=1:return i+1
        if m in K and len(wins)%BLOCK==0 and len(wins)//BLOCK<=MAX_LOOKS and sum(wins[-BLOCK:])<=K[m]:return i+1
    return None

def study():
    counts={}; summary={}
    def ck(k,b):
        if not b:raise AssertionError(k)
        counts[k]=counts.get(k,0)+1
    for m,den in [('BLOCK_NAIVE',20),('BLOCK_SPEND',20*MAX_LOOKS)]:
        k=K[m];tail=lambda j:sum(math.comb(BLOCK,i) for i in range(j+1));ck('threshold',den*tail(k)<=2**BLOCK<den*tail(k+1))
    for m in METHODS:
        for d in [np.zeros(64,dtype=int),np.full(32,-2000),np.full(32,2000),np.r_[np.zeros(31),np.full(32,-2000)],np.tile([2000,-2000],40)]:ck('fixture',trigger(d,m)==oracle(d,m))
    for name,changes in R['CASES'].items():
        rows={m:[] for m in METHODS}
        for seed in SEEDS:
            x,y,aa,prob,start=R['generate'](seed,changes);b=B['run'](x,y,JS,aa,'EB',2048);e=b['end'];inc=b['inc'];fin=b['fin'];d=B['netvec'](x[e:],y[e:],fin)-B['netvec'](x[e:],y[e:],inc)
            ck('paired_support',np.all(np.isin(d,[-2000,0,2000])));ck('unchanged_audit',aa==[B['audit'](x,y,j,0) for j in JS])
            for m in METHODS:
                r=run(x,y,b,m);t=r['rollback'];sw=r['sw'];stop=t if t is not None else H
                ck('time',t is None or e<t<H);ck('fee',r['fee']==200*int(t is not None));ck('observation',r['obs']==(stop-e if sw and m!='KEEP' else 0))
                ck('eligibility',t is None or sw==1);ck('count',r['n']==(int(np.count_nonzero(d[:stop-e])) if sw else 0))
                actual=int(B['netvec'](x[b['first']:e],y[b['first']:e],inc).sum()+B['netvec'](x[e:stop],y[e:stop],fin).sum()+B['netvec'](x[stop:],y[stop:],inc).sum());ck('accounting',r['net']==actual-e-b['fee']-r['obs']-r['fee'])
                if seed<111016:
                    direct=[B['payoff'](fin,int(a),int(z))-B['payoff'](inc,int(a),int(z)) for a,z in zip(x[e:],y[e:])];ck('direct_payoff',np.array_equal(d,direct));o=oracle(direct,m) if sw else None;ck('oracle',t==(e+o if o is not None and e+o<H else None))
                if t is not None:
                    gain=sum(int((prob[t:]==p).sum())*(v[inc]-v[fin]) for p,v in V.items())-200;ck('causality',trigger(d[:t-e],m)==t-e)
                    if seed<111008:
                        yy=y.copy();yy[t:]*=-1;ck('future_mask',run(x,yy,b,m)['rollback']==t)
                else:gain=0
                rows[m].append(dict(**r,good=int(t is not None and gain>0),bad=int(t is not None and gain<=0),delay=t-e if t is not None else None))
        summary[name]={m:dict(mean_net=float(np.mean([r['net'] for r in rr])),initial_switch=sum(r['sw'] for r in rr),rollback=sum(r['rollback'] is not None for r in rr),good=sum(r['good'] for r in rr),bad=sum(r['bad'] for r in rr),mean_delay=float(np.mean([r['delay'] for r in rr if r['delay'] is not None])) if any(r['delay'] is not None for r in rr) else None,mean_obs=float(np.mean([r['obs'] for r in rr]))) for m,rr in rows.items()}
    return dict(passed=sum(counts.values()),counts=counts,plan_sha=SHA),dict(plan=PLAN,plan_sha=SHA,summary=summary)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--outdir',type=Path,required=True);a=p.parse_args();t,e=study()
    for name,z in [('tests',t),('examples',e)]:(a.outdir/f'Trading_Round111_{name}.json').write_text(json.dumps(z,sort_keys=True,indent=2)+'\n')
    print(json.dumps(t))
