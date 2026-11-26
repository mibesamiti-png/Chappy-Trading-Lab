"""R97: fixed-budget internal validation for hypothesis capacity. Synthetic only."""
import argparse, hashlib, json, runpy
from pathlib import Path
from fractions import Fraction
from itertools import product
import numpy as np
p=Path(__file__).with_name('Chappy_Trading_Hypothesis_Penalty_Study_v0.1.py')
if hashlib.sha256(p.read_bytes()).hexdigest()!='25b88516911ec823b9d88c046c9dba83fd84a1ee6825baa9da15df76fc748ca4':raise ValueError('R96 hash')
R=runpy.run_path(str(p)); C=R['R']; MAT=R['MAT']; NAMES=R['NAMES']; MODELS=R['MODELS']; LENGTHS=R['LENGTHS']; N=R['N']; OFF=R['OFF']; S=R['S']; PEN=R['PENALTY']; POOLS=(16,24,256); SEEDS=range(97000,97256)
METHODS=('STRUCTURAL16','CONDITIONAL24','FULL256','PENALIZED256','HOLDOUT','CV2')
PLAN=dict(synthetic_only=True,models=MODELS,seeds=list(SEEDS),lengths=LENGTHS,offsets=OFF,audit_eval_length=N,methods=METHODS,pools=POOLS,penalty_hits=[0,2,5],holdout='first half fit, second half select pool, refit on full training',cv2='two reciprocal half fits, sum validation hits, refit chosen pool on full training',ties='smaller pool, original candidate order',audit='R91 independent single GATE60 unchanged',cost_bps=20,amplitude_bps=100,notional_yen=100000)
SHA=C['B']['digest'](PLAN)
def choose(t,a,b):
    ia=[int(np.argmax(a[:k])) for k in POOLS];ib=[int(np.argmax(b[:k])) for k in POOLS]
    va=[int(b[j]) for j in ia];vb=[int(a[j]) for j in ib]
    h=int(np.argmax(va));cv=int(np.argmax(np.array(va)+vb))
    return [(int(np.argmax(t[:k])),k) for k in POOLS]+[(int(np.argmax(t-PEN)),256),(int(np.argmax(t[:POOLS[h]])),POOLS[h]),(int(np.argmax(t[:POOLS[cv]])),POOLS[cv])],dict(first_fit=ia,second_fit=ib,forward=va,backward=vb)
def run(m,seed,check=None):
    x,y=C['vectors'](m,C['inputs'](seed,max(LENGTHS))); ax,ay=C['vectors'](m,C['inputs'](seed+OFF[1],N));ex,ey=C['vectors'](m,C['inputs'](seed+OFF[2],N)); audit=C['scores'](ax,ay);ev=C['scores'](ex,ey);out={}
    for n in LENGTHS:
        half=n//2;a=C['scores'](x[:half],y[:half]);b=C['scores'](x[half:n],y[half:n]);t=a+b;chosen,detail=choose(t,a,b);rows={}
        for method,(j,k) in zip(METHODS,chosen):
            g=bool(S['gates'](int(t[j]),int(audit[j]))['GATE60']);rows[method]=dict(index=j,chosen=NAMES[j],pool=k,train_hits=int(t[j]),audit_hits=int(audit[j]),eval_hits=int(ev[j]),admitted=g,gated_eval_net=S['net'](int(ev[j])) if g else 0)
        out[str(n)]=dict(methods=rows,internal=detail)
        if check:
            # independent direct matches, no compressed score arithmetic
            aa=np.count_nonzero(MAT[:,x[:half]]==y[:half],axis=1);bb=np.count_nonzero(MAT[:,x[half:n]]==y[half:n],axis=1);tt=aa+bb
            ca=[max(range(k),key=lambda j:int(aa[j])) for k in POOLS];cb=[max(range(k),key=lambda j:int(bb[j])) for k in POOLS]
            va=[int(bb[j]) for j in ca];vb=[int(aa[j]) for j in cb];h=max(range(3),key=lambda i:va[i]);v=max(range(3),key=lambda i:va[i]+vb[i]);ks=[16,24,256,256,POOLS[h],POOLS[v]]
            check('scores',bool(np.array_equal(a,aa) and np.array_equal(b,bb)),True);check('fold_trace',detail,dict(first_fit=ca,second_fit=cb,forward=va,backward=vb))
            for method,k in zip(METHODS,ks):
                j=max(range(k),key=lambda i:int(tt[i])-(int(PEN[i]) if method=='PENALIZED256' else 0));r=rows[method];ah=int(np.count_nonzero(MAT[j,ax]==ay));eh=int(np.count_nonzero(MAT[j,ex]==ey));g=ah>=167
                check('pool',r['pool'],k);check('choice',r['index'],j);check('hits',(r['train_hits'],r['audit_hits'],r['eval_hits']),(int(tt[j]),ah,eh));check('gate',r['admitted'],g);check('net',r['gated_eval_net'],(800*eh-1200*(N-eh)) if g else 0)
    return out
def study(test=False):
    counts={};summary={}
    def ck(k,a,b):
        if a!=b:raise AssertionError((k,a,b))
        counts[k]=counts.get(k,0)+1
    ck('seed_disjoint',len({s+o for s,o in product(SEEDS,OFF)}),len(SEEDS)*3);ck('unique_tables',len(set(R['TABLE'])),256)
    for m in MODELS:
        q=C['theory'](m);best=max(q);rs=[run(m,s,ck if test else None) for s in SEEDS];summary[m]={}
        for n in LENGTHS:
            summary[m][str(n)]={}
            for method in METHODS:
                vs=[r[str(n)]['methods'][method] for r in rs];qs=[q[v['index']] for v in vs];summary[m][str(n)][method]=dict(optimal=sum(z==best for z in qs),economic_choice=sum(z>Fraction(3,5) for z in qs),admitted=sum(v['admitted'] for v in vs),admitted_nonpositive=sum(v['admitted'] and z<=Fraction(3,5) for v,z in zip(vs,qs)),pool_counts=[sum(v['pool']==k for v in vs) for k in POOLS],mean_train_accuracy=sum(v['train_hits'] for v in vs)/len(vs)/n,mean_true_accuracy=float(sum(qs)/len(qs)),mean_gated_eval_net=sum(v['gated_eval_net'] for v in vs)/len(vs))
    return dict(passed=sum(counts.values()),counts=counts,plan_sha=SHA) if test else dict(plan=PLAN,plan_sha=SHA,summary=summary)
if __name__=='__main__':
    p=argparse.ArgumentParser();g=p.add_mutually_exclusive_group(required=True);g.add_argument('--self-test',action='store_true');g.add_argument('--example',action='store_true');a=p.parse_args();print(json.dumps(study(a.self_test),indent=2,sort_keys=True))
