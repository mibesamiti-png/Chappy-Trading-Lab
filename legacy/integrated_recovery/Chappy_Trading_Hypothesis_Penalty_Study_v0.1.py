"""R96: fixed structural-tier penalty; synthetic only, no orders."""
import argparse, hashlib, json, runpy
from pathlib import Path
from itertools import product
from fractions import Fraction as F
import numpy as np
p=Path(__file__).with_name('Chappy_Trading_Hypothesis_Capacity_Study_v0.1.py')
if hashlib.sha256(p.read_bytes()).hexdigest()!='d81281a84a2ad36f90ea9e3cd97a974de7eb78608b1b1d7e441cb5023a6ca2bf':raise ValueError('R95 hash')
R=runpy.run_path(str(p)); MODELS=R['MODELS']; NAMES=R['NAMES']; TABLE=R['TABLE']; MAT=R['MAT']; N=R['N']; OFF=R['OFF']; LENGTHS=R['LENGTHS']; S=R['S']
SEEDS=range(96000,96256)
# Fixed illustrative hit penalties, not optimized: original structural, relative extension, general table.
PENALTY=np.array([0]*16+[2]*8+[5]*232,dtype=np.int32)
METHODS={'STRUCTURAL16':(16,False),'CONDITIONAL24':(24,False),'FULL256':(256,False),'PENALIZED256':(256,True)}
PLAN=dict(synthetic_only=True,models=MODELS,seeds=list(SEEDS),offsets=OFF,training_lengths=LENGTHS,audit_eval_length=N,methods=METHODS,penalties_hits=[0,2,5],tier_sizes=[16,8,232],tie='original order',audit='R91 single independent GATE60 unchanged',notional_yen=100000,cost_bps=20,amplitude_bps=100,market_adoption=False)
SHA=R['B']['digest'](PLAN)
def trial(m,seed):
    x,y=R['vectors'](m,R['inputs'](seed,max(LENGTHS)))
    a,e=[R['scores'](*R['vectors'](m,R['inputs'](seed+o,N))) for o in OFF[1:]]
    out={}
    for n in LENGTHS:
        t=R['scores'](x[:n],y[:n]);out[str(n)]={}
        for method,(k,pen) in METHODS.items():
            j=S['choose'](t[:k]-(PENALTY[:k] if pen else 0));g=bool(S['gates'](int(t[j]),int(a[j]))['GATE60']);out[str(n)][method]=dict(chosen=NAMES[j],index=j,penalty=int(PENALTY[j]) if pen else 0,train_hits=int(t[j]),audit_hits=int(a[j]),eval_hits=int(e[j]),admitted=g,train_net=2000*int(t[j])-1200*n,raw_eval_net=S['net'](int(e[j])),gated_eval_net=S['net'](int(e[j])) if g else 0)
    return dict(seed=seed,conditions=out)
def examples():
    summary={};runs={}
    for m in MODELS:
        q=R['theory'](m);rs=[trial(m,s) for s in SEEDS];runs[m]=rs;summary[m]={}
        for n in LENGTHS:
            summary[m][str(n)]={}
            for method,(k,_) in METHODS.items():
                vs=[r['conditions'][str(n)][method] for r in rs];qs=[q[v['index']] for v in vs];summary[m][str(n)][method]=dict(best_accuracy=str(max(q[:k])),global_optimal=sum(x==max(q) for x in qs),pool_optimal=sum(x==max(q[:k]) for x in qs),economic_choice=sum(x>F(3,5) for x in qs),admitted=sum(v['admitted'] for v in vs),admitted_nonpositive=sum(v['admitted'] and x<=F(3,5) for v,x in zip(vs,qs)),tier_counts=[sum(lo<=v['index']<hi for v in vs) for lo,hi in [(0,16),(16,24),(24,256)]],mean_true_accuracy=float(sum(qs)/len(qs)),mean_train_accuracy=sum(v['train_hits'] for v in vs)/len(vs)/n,mean_raw_eval_net=sum(v['raw_eval_net'] for v in vs)/len(vs),mean_gated_eval_net=sum(v['gated_eval_net'] for v in vs)/len(vs))
    return dict(plan=PLAN,plan_sha=SHA,summary=summary,runs=runs)
def tests():
    counts={}
    def ck(k,a,b):
        if a!=b:raise AssertionError((k,a,b))
        counts[k]=counts.get(k,0)+1
    ck('table_count',len(set(TABLE)),256);ck('penalty_distribution',tuple(map(int,np.bincount(PENALTY))), (16,0,8,0,0,232));ck('seed_disjoint',len({s+o for s,o in product(SEEDS,OFF)}),len(SEEDS)*3)
    for m in MODELS:
        q=R['theory'](m)
        for seed in SEEDS:
            r=trial(m,seed); old=R['trial'](m,seed)
            x,y=R['vectors'](m,R['inputs'](seed,max(LENGTHS)));ax,ay=R['vectors'](m,R['inputs'](seed+OFF[1],N));ex,ey=R['vectors'](m,R['inputs'](seed+OFF[2],N))
            a=np.sum(MAT[:,ax]==ay,axis=1);e=np.sum(MAT[:,ex]==ey,axis=1)
            for n in LENGTHS:
                t=np.sum(MAT[:,x[:n]]==y[:n],axis=1)
                for method,(k,pen) in METHODS.items():
                    v=r['conditions'][str(n)][method];j=max(range(k),key=lambda i:(int(t[i])-(0 if i<16 else 2 if i<24 else 5) if pen else int(t[i]),-i));g=int(a[j])>=167
                    ck('choice',v['index'],j);ck('name',v['chosen'],NAMES[j]);ck('hits',(v['train_hits'],v['audit_hits'],v['eval_hits']),(int(t[j]),int(a[j]),int(e[j])));ck('audit',v['admitted'],g);ck('raw_net',v['raw_eval_net'],800*int(e[j])-1200*(N-int(e[j])));ck('gated_net',v['gated_eval_net'],v['raw_eval_net'] if g else 0);ck('train_net',v['train_net'],800*int(t[j])-1200*(n-int(t[j])));
                    if not pen:ck('R95_reuse',{key:val for key,val in v.items() if key not in ('index','penalty')},old['conditions'][str(n)][method])
                vp=r['conditions'][str(n)]['PENALIZED256'];vr=r['conditions'][str(n)]['FULL256'];ck('penalty_nonincreasing_train',vp['train_hits']<=vr['train_hits'],True);ck('penalty_nonincreasing_tier',int(PENALTY[vp['index']])<=int(PENALTY[vr['index']]),True)
    return dict(passed=sum(counts.values()),counts=counts,plan_sha=SHA)
if __name__=='__main__':
    p=argparse.ArgumentParser();g=p.add_mutually_exclusive_group(required=True);g.add_argument('--self-test',action='store_true');g.add_argument('--example',action='store_true');a=p.parse_args();print(json.dumps(tests() if a.self_test else examples(),indent=2,sort_keys=True))
