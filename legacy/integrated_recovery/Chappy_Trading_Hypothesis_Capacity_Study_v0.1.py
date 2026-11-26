"""R95: finite direction-table capacity versus training sample size. Synthetic only."""
import argparse, hashlib, json, runpy, random
from pathlib import Path
from itertools import product
from fractions import Fraction as F
import numpy as np
p=Path(__file__).with_name('Chappy_Trading_Conditional_Hypothesis_Study_v0.1.py')
if hashlib.sha256(p.read_bytes()).hexdigest()!='2efa9f0da37216f677004ed098c756b6c11fe89ce78a65760febe0fc82a40997':raise ValueError('R94 hash')
R=runpy.run_path(str(p)); S=R['S']; B=R['B']; CELLS=R['CELLS']; SIGNS=R['SIGNS']; STATES=R['STATES']; IDX=R['IDX']; MODELS=R['MODELS']; OFF=R['OFF']; N=R['N']
SEEDS=range(95000,95256); LENGTHS=(16,64,256,1024); POOLS={'STRUCTURAL16':16,'CONDITIONAL24':24,'FULL256':256}
H=dict(R['H']); seen=set(H.values())
for table in product((-1,1),repeat=8):
    if table not in seen:H['FULL:'+''.join('+' if d==1 else '-' for d in table)]=table;seen.add(table)
NAMES=tuple(H); TABLE=tuple(H.values()); MAT=np.array(TABLE,dtype=np.int32)
PLAN=dict(synthetic_only=True,models=MODELS,seeds=list(SEEDS),offsets=OFF,training_lengths=LENGTHS,audit_eval_length=N,pools=POOLS,selection='R91 fixed-order maximum training hits',audit='R91 single independent GATE60',training_prefixes='nested, same seed stream',cost_bps=20,amplitude_bps=100,notional_yen=100000,market_adoption=False)
SHA=B['digest'](PLAN)
def inputs(seed,n):
    rng=random.Random(seed);return [(CELLS[rng.randrange(4)],SIGNS[rng.randrange(2)],rng.randrange(100)) for _ in range(n)]
def vectors(m,rows):
    return np.array([IDX[c,s] for c,s,u in rows],dtype=np.int32),np.array([R['outcome'](m,c,s,u) for c,s,u in rows],dtype=np.int32)
def scores(x,y):
    v=np.zeros(8,dtype=np.int32);np.add.at(v,x,y);return (len(y)+MAT@v)//2
def theory(m):return tuple(F(int(h),800) for h in scores(*vectors(m,list(product(CELLS,SIGNS,range(100))))))
def trial(m,seed):
    x,y=vectors(m,inputs(seed,max(LENGTHS))); ax,ay=vectors(m,inputs(seed+OFF[1],N)); ex,ey=vectors(m,inputs(seed+OFF[2],N)); a=scores(ax,ay);e=scores(ex,ey);out={}
    for n in LENGTHS:
        t=scores(x[:n],y[:n]);out[str(n)]={}
        for pool,k in POOLS.items():
            j=S['choose'](t[:k]);g=S['gates'](int(t[j]),int(a[j]))['GATE60'];out[str(n)][pool]=dict(chosen=NAMES[j],train_hits=int(t[j]),audit_hits=int(a[j]),eval_hits=int(e[j]),admitted=bool(g),train_net=2000*int(t[j])-1200*n,raw_eval_net=S['net'](int(e[j])),gated_eval_net=S['net'](int(e[j])) if g else 0)
    return dict(seed=seed,conditions=out)
def examples():
    summary={};runs={}
    for m in MODELS:
        q=theory(m);rs=[trial(m,s) for s in SEEDS];runs[m]=rs;summary[m]={}
        for n in LENGTHS:
            summary[m][str(n)]={}
            for pool,k in POOLS.items():
                vs=[r['conditions'][str(n)][pool] for r in rs];qs=[q[NAMES.index(v['chosen'])] for v in vs];best=max(q[:k]);summary[m][str(n)][pool]=dict(best_accuracy=str(best),optimal_choice=sum(x==best for x in qs),economic_choice=sum(x>F(3,5) for x in qs),admitted=sum(v['admitted'] for v in vs),admitted_nonpositive=sum(v['admitted'] and x<=F(3,5) for v,x in zip(vs,qs)),mean_true_accuracy=float(sum(qs)/len(qs)),mean_train_accuracy=sum(v['train_hits'] for v in vs)/len(vs)/n,mean_raw_eval_net=sum(v['raw_eval_net'] for v in vs)/len(vs),mean_gated_eval_net=sum(v['gated_eval_net'] for v in vs)/len(vs))
    return dict(plan=PLAN,plan_sha=SHA,tables=H,summary=summary,runs=runs)
def tests():
    counts={}
    def ck(k,a,b):
        if a!=b:raise AssertionError((k,a,b))
        counts[k]=counts.get(k,0)+1
    ck('closure',set(TABLE),set(product((-1,1),repeat=8)));ck('count',len(TABLE),256);ck('prefix',TABLE[:24],R['TABLE']);ck('seed_disjoint',len({s+o for s,o in product(SEEDS,OFF)}),len(SEEDS)*3)
    def oracle(m,rows):
        x=[];y=[]
        for c,s,u in rows:
            i=CELLS.index(c);x.append(STATES.index((c,s)))
            if m=='absolute_up':d=1 if u<75 else -1
            elif m=='absolute_nonlinear':d=1 if u<(70,70,70,30)[i] else -1
            elif m=='mixed_direction':d=(1 if i<2 else s)*(1 if u<75 else -1)
            else:d=s*(1 if u<MODELS[m][i] else -1)
            y.append(d)
        return np.array(x),np.array(y)
    for m in MODELS:
        q=theory(m);x,y=oracle(m,list(product(CELLS,SIGNS,range(100))));ck('theory',q,tuple(F(int(h),800) for h in np.sum(MAT[:,x]==y,axis=1)));ck('R94_theory',q[:24],R['theory'](m))
        for seed in SEEDS:
            r=trial(m,seed);tr=inputs(seed,max(LENGTHS));ar=inputs(seed+OFF[1],N);er=inputs(seed+OFF[2],N);x,y=oracle(m,tr);ax,ay=oracle(m,ar);ex,ey=oracle(m,er)
            ck('R94_input',tr[:N],B['inputs'](seed));ck('R94_audit_input',ar,B['inputs'](seed+OFF[1]));ck('R94_eval_input',er,B['inputs'](seed+OFF[2]))
            for n in LENGTHS:
                # independent direct match; no compressed frequency scoring
                t=np.sum(MAT[:,x[:n]]==y[:n],axis=1)
                # independent unrestricted optimum: majority direction at each input state
                optimum=sum(max(int(np.sum((x[:n]==i)&(y[:n]==d))) for d in (-1,1)) for i in range(8))
                ck('full_optimum',int(max(t)),optimum)
                for pool,k in POOLS.items():
                    v=r['conditions'][str(n)][pool];j=int(np.argmax(t[:k]));a=int(np.sum(MAT[j,ax]==ay));e=int(np.sum(MAT[j,ex]==ey));g=a>=167
                    ck('choice',v['chosen'],NAMES[j]);ck('hits',(v['train_hits'],v['audit_hits'],v['eval_hits']),(int(t[j]),a,e));ck('audit',v['admitted'],g);ck('training_net',v['train_net'],800*int(t[j])-1200*(n-int(t[j])));ck('raw_net',v['raw_eval_net'],800*e-1200*(N-e));ck('gated_net',v['gated_eval_net'],(800*e-1200*(N-e)) if g else 0)
            old=R['run'](m,seed)['pools'];ck('R94_reuse',r['conditions']['256']['CONDITIONAL24'],old['CONDITIONAL24']);ck('R94_reuse',r['conditions']['256']['STRUCTURAL16'],old['STRUCTURAL16'])
    return dict(passed=sum(counts.values()),counts=counts,plan_sha=SHA)
if __name__=='__main__':
    p=argparse.ArgumentParser();g=p.add_mutually_exclusive_group(required=True);g.add_argument('--self-test',action='store_true');g.add_argument('--example',action='store_true');a=p.parse_args();print(json.dumps(tests() if a.self_test else examples(),indent=2,sort_keys=True))
