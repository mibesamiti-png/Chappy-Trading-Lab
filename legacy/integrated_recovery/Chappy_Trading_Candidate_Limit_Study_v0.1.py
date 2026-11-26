"""R92: synthetic distribution shifts and missing candidates, no market data."""
import argparse, hashlib, json, runpy
from pathlib import Path
from fractions import Fraction as F
from itertools import product
p=Path(__file__).with_name('Chappy_Trading_Candidate_Selection_Study_v0.1.py')
if hashlib.sha256(p.read_bytes()).hexdigest()!='bdaef292a21e8a5114883895b7b77000f8994f4fae83656ef4d29fd426e6e66f':raise ValueError('R91 hash')
R=runpy.run_path(str(p)); B=R['R']; C=R['CAND']; CELLS=R['CELLS']; SIGNS=R['SIGNS']; N=R['N']; POL=R['POL']; OFF=R['OFFSETS']; SEEDS=range(92000,92256)
M=dict(R['MODELS'],inverse_context=(25,25,75,75),absolute_up=(75,75,75,75))
CASES={'stable':('interaction',)*3,'shift_before_audit':('interaction','opposite_interaction','opposite_interaction'),'shift_after_audit':('interaction','interaction','opposite_interaction'),'null_after_audit':('interaction','interaction','null'),'temporary_audit_shift':('interaction','opposite_interaction','interaction'),'missing_inverse_context':('inverse_context',)*3,'missing_absolute_up':('absolute_up',)*3}
PLAN=dict(synthetic_only=True,cases=CASES,models=M,seeds=list(SEEDS),offsets=OFF,candidates=C,policies=POL,slots_per_phase=N,selection='R91 choose/gates unchanged',cost_bps=20,amplitude_bps=100,notional_yen=100000,absolute_up='75% absolute positive independent of input sign',reference='inverse context and absolute up diagnostic only',market_adoption=False)
SHA=B['digest'](PLAN)
DIRS=((1,1,1,1),(-1,-1,-1,-1),(1,1,-1,-1),(1,-1,1,-1),(1,-1,-1,1),(-1,1,1,-1))
def value(m,cell,sg,u):return (1 if u<75 else -1) if m=='absolute_up' else sg*(1 if u<M[m][CELLS.index(cell)] else -1)
def scores(m,rows):
    h=[0]*8
    for cell,sg,u in rows:
        a=R['A'][cell,sg];v=value(m,cell,sg,u)
        for j,d in enumerate((*a,-a[2],1)):h[j]+=d*v>0
    return tuple(h)
def oracle(m,rows):
    h=[0]*8
    for cell,sg,u in rows:
        i=CELLS.index(cell);v=(1 if u<75 else -1) if m=='absolute_up' else sg*(1 if u<M[m][i] else -1)
        for j,d in enumerate((*[sg*d[i] for d in DIRS],-sg*DIRS[2][i],1)):h[j]+=d*v>0
    return tuple(h)
def theory(m):return tuple(F(x,800) for x in scores(m,product(CELLS,SIGNS,range(100))))
def run(case,seed):
    t,a,e=(scores(m,B['inputs'](seed+o)) for m,o in zip(CASES[case],OFF));j=R['choose'](t[:6]);g=R['gates'](t[j],a[j]);return dict(seed=seed,chosen=C[j],train_all=t,audit_all=a,eval_all=e,admitted=g,eval_net={p:R['net'](e[j]) if g[p] else 0 for p in POL})
def examples():
    summary={};runs={}
    for case,ms in CASES.items():
        rows=[run(case,s) for s in SEEDS];runs[case]=rows;q=[theory(m) for m in ms]
        summary[case]=dict(phases=ms,phase_accuracy=[dict(zip((*C,'INVERSE_CONTEXT','ABSOLUTE_UP'),map(str,x))) for x in q],chosen_counts={c:sum(r['chosen']==c for r in rows) for c in C},policies={p:dict(admitted=sum(r['admitted'][p] for r in rows),mean_net_yen=sum(r['eval_net'][p] for r in rows)/len(rows),negative=sum(r['eval_net'][p]<0 for r in rows),positive=sum(r['eval_net'][p]>0 for r in rows),admitted_nonpositive_eval=sum(r['admitted'][p] and q[-1][C.index(r['chosen'])]<=F(3,5) for r in rows)) for p in POL})
    return dict(plan=PLAN,plan_sha=SHA,summary=summary,runs=runs)
def tests():
    counts={}
    def ck(k,x,y):
        if x!=y:raise AssertionError((k,x,y))
        counts[k]=counts.get(k,0)+1
    for m in M:
        ck('theory',theory(m),tuple(F(x,800) for x in oracle(m,product(CELLS,SIGNS,range(100)))))
        if m in R['MODELS']:ck('R91_theory',theory(m)[:6],R['theory'](m))
    for m,j in [('inverse_context',6),('absolute_up',7)]:
        ck('missing_no_positive',max(theory(m)[:6]),F(1,2));ck('missing_reference',theory(m)[j],F(3,4))
    ck('seed_separation',len({s+o for s,o in product(SEEDS,OFF)}),len(SEEDS)*3)
    for case,seed in product(CASES,SEEDS):
        r=run(case,seed);t,a,e=(oracle(m,B['inputs'](seed+o)) for m,o in zip(CASES[case],OFF));j=sorted(range(6),key=lambda i:(-t[i],i))[0]
        for k,v in [('train_all',t),('audit_all',a),('eval_all',e),('chosen',C[j])]:ck(k,r[k],v)
        g=dict(SELECT_ONLY=True,TRAIN_POSITIVE=800*t[j]-1200*(N-t[j])>0,GATE50=a[j]>=142,GATE60=a[j]>=167,WAIT=False);ck('gates',r['admitted'],g)
        for pol in POL:ck('net',r['eval_net'][pol],800*e[j]-1200*(N-e[j]) if g[pol] else 0)
        if case=='stable':
            old=R['run']('interaction',seed)
            for k in ('chosen','admitted','eval_net'):ck('R91_reuse',r[k],old[k])
        if case in ('shift_before_audit','shift_after_audit','null_after_audit','temporary_audit_shift'):
            base=run('stable',seed);ck('no_future_selection',r['chosen'],base['chosen'])
            if CASES[case][1]=='interaction':ck('no_future_audit',r['admitted'],base['admitted'])
    return dict(passed=sum(counts.values()),counts=counts)
if __name__=='__main__':
    p=argparse.ArgumentParser();g=p.add_mutually_exclusive_group(required=True);g.add_argument('--self-test',action='store_true');g.add_argument('--example',action='store_true');a=p.parse_args();print(json.dumps(tests() if a.self_test else examples(),indent=2,sort_keys=True))
