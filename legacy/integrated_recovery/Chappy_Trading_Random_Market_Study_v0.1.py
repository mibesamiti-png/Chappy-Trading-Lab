"""R85: synthetic null and positive controls; no market data or orders."""
import argparse, hashlib, json, random, runpy
from fractions import Fraction as F
from itertools import product
from pathlib import Path
P=Path(__file__).with_name('Chappy_Trading_Latency_Phase_Study_v0.1.py')
if hashlib.sha256(P.read_bytes()).hexdigest()!='846aced7c1e28922bf32c290f328c8790e5b2579c0457c943a32035d01d4293d':raise ValueError('R84 hash')
R=runpy.run_path(str(P)); POL=R['POL']; N=256; SEEDS=tuple(range(85000,85064)); D=(1,3,8); C=20
MODES={'iid':50,'weak':55,'moderate':70,'strong':90,'irregular_bias':None}
PLAN=dict(slots=N,seeds=list(SEEDS),delays=D,modes=MODES,window=4,cost_bps=C,notional=100000,amplitude_bps=100,policies=POL,random='local Python Random; Markov stay probability in percent; irregular bias switches sign after uniform integer 8..40 slots and emits matching sign 80% of time',observation='free complete fixed-delay synthetic shadow outcomes; no contemporaneous truth',method='R84 equivalent lookup for all binary evidence windows',synthetic_only=True)
def series(mode,seed):
    r=random.Random(seed); x=r.choice((-100,100)); out=[]
    if mode=='irregular_bias':
        left=0
        for _ in range(N):
            if left==0:x=-x;left=r.randint(8,40)
            out.append(x if r.randrange(100)<80 else -x);left-=1
    else:
        out.append(x)
        for _ in range(N-1):
            if r.randrange(100)>=MODES[mode]:x=-x
            out.append(x)
    return out
# Cache upstream actions for each of 31 binary suffixes, and each delay.
def table():
    t={}
    for d,k,p in product(D,range(5),POL):
        for w in product((-100,100),repeat=k):
            i=k+d-1; rec=[dict(index=j,received=j+d,bps=v) for j,v in enumerate(w)]
            t[d,p,w]=R['decide'](p,i,d,rec)['action']
    return t
T=table()
def action(p,i,d,vs):
    end=max(0,i-d+1);w=tuple(vs[max(0,end-4):end]);return T[d,p,w]
def simulate(vs,d,p):
    total=peak=dd=trades=correct=0
    for i,v in enumerate(vs):
        a=action(p,i,d,vs);g=10*(a*v-C) if a else 0
        trades+=bool(a);correct+=a*v>0;total+=g;peak=max(peak,total);dd=max(dd,peak-total)
    return dict(net_yen=total,trades=trades,correct=correct,wait=len(vs)-trades,drawdown_yen=dd)
def exact_null(d,p):
    # All independent binary mature histories and next sign, ignoring warmup.
    outcomes=[]
    for w in product((-100,100),repeat=4):
        a=T[d,p,w]
        for v in (-100,100):outcomes.append((a,10*(a*v-C) if a else 0,a*v>0))
    return dict(selection_probability=str(F(sum(bool(a) for a,g,c in outcomes),32)),expected_yen_per_mature_slot=str(F(sum(g for a,g,c in outcomes),32)),accuracy=str(F(sum(c for a,g,c in outcomes),sum(bool(a) for a,g,c in outcomes))) if any(a for a,g,c in outcomes) else None)
def examples():
    cases=[]; agg=[]
    for mode,d in product(MODES,D):
        group=[dict(seed=s,methods={p:simulate(series(mode,s),d,p) for p in POL}) for s in SEEDS]
        cases.append(dict(mode=mode,delay=d,runs=group));methods={}
        for p in POL:
            rs=[r['methods'][p] for r in group]; v=[r['net_yen'] for r in rs]; tr=sum(r['trades'] for r in rs);co=sum(r['correct'] for r in rs)
            methods[p]=dict(mean_yen=sum(v)/len(v),min_yen=min(v),max_yen=max(v),positive_runs=sum(x>0 for x in v),negative_runs=sum(x<0 for x in v),trades=tr,correct=co,selection_pct=100*tr/(N*len(rs)),accuracy_pct=100*co/tr if tr else None,mean_drawdown_yen=sum(r['drawdown_yen'] for r in rs)/len(rs))
        agg.append(dict(mode=mode,delay=d,methods=methods))
    return dict(plan=PLAN,plan_sha=R['R']['digest'](PLAN),aggregate=agg,cases=cases,exact_iid_mature={p:exact_null(1,p) for p in POL})
def tests():
    counts={}
    def ck(n,a,b):
        if a!=b:raise AssertionError((n,a,b))
        counts[n]=counts.get(n,0)+1
    for (d,p,w),a in T.items():
        m=sum(w); expected=1 if p=='FIXED' else 0
        if p not in ('FIXED','WAIT') and len(w)==4:
            if m>4*C:expected=1
            elif m< -4*C and p in ('SYMMETRIC','TARGETED'):expected=-1
        ck('lookup_arithmetic',a,expected)
        i=len(w)+d-1;rec=[dict(index=j,received=j+d,bps=v) for j,v in enumerate(w)];future=dict(index=i,received=i+d,bps=99999)
        ck('upstream_future_mask',R['decide'](p,i,d,rec)['action'],R['decide'](p,i,d,rec[::-1]+[future])['action'])
    for mode,seed in product(MODES,SEEDS):
        vs=series(mode,seed);ck('reproducible',vs,series(mode,seed));ck('length',len(vs),N);ck('binary',set(vs)<= {-100,100},True)
        for d,p in product(D,POL):
            s=simulate(vs,d,p); gs=[]; aa=[]
            for i,v in enumerate(vs):
                ids=range(i-d-3,i-d+1);a=1 if p=='FIXED' else 0
                if p not in ('FIXED','WAIT') and i>=d+3:
                    m=sum(vs[j] for j in ids)
                    if m>80:a=1
                    elif m< -80 and p in ('SYMMETRIC','TARGETED'):a=-1
                ck('decision',action(p,i,d,vs),a)
                ck('prefix',action(p,i,d,vs[:i]),a)
                gs.append(10*(a*v-C) if a else 0);aa.append(a)
            ck('total',s['net_yen'],sum(gs));ck('trades',s['trades'],sum(bool(a) for a in aa));ck('correct',s['correct'],sum(a*v>0 for a,v in zip(aa,vs)));ck('partition',s['trades']+s['wait'],N)
            cum=peak=dd=0
            for g in gs:cum+=g;peak=max(peak,cum);dd=max(dd,peak-cum)
            ck('drawdown',s['drawdown_yen'],dd)
    for d,p in product(D,POL):
        n=exact_null(d,p);prob=F(n['selection_probability']);ck('null_cost',F(n['expected_yen_per_mature_slot']),-200*prob);ck('null_accuracy',n['accuracy'],'1/2' if prob else None)
    return dict(passed=sum(counts.values()),counts=counts)
if __name__=='__main__':
    p=argparse.ArgumentParser();g=p.add_mutually_exclusive_group(required=True);g.add_argument('--self-test',action='store_true');g.add_argument('--example',action='store_true');a=p.parse_args();print(json.dumps(tests() if a.self_test else examples(),indent=2,sort_keys=True))
