"""R98: observation frequency imbalance; synthetic research only, no orders."""
import argparse, hashlib, json, random, runpy
from pathlib import Path
from fractions import Fraction as F
from itertools import product
import numpy as np
p=Path(__file__).with_name('Chappy_Trading_Hypothesis_Pool_Study_v0.1.py')
if hashlib.sha256(p.read_bytes()).hexdigest()!='be460ac944cbf4168c6fd86cfb03be1f36e0f1a40af60a8c04630b3b312bcb60':raise ValueError('R97 hash')
R=runpy.run_path(str(p)); C=R['C']; MAT=R['MAT']; METHODS=R['METHODS']; N=256
SEEDS=range(98000,98256); LENGTHS=(64,256,1024); WEIGHTS={'balanced':(25,25,25,25),'skewed':(70,20,9,1)}
MODELS={'null':(50,50,50,50),'interaction':(75,25,25,75),'nonlinear':(70,70,70,30),'rare_only':(50,50,50,90)}
CELLS=C['CELLS']; SIGNS=C['SIGNS']; STATES=C['STATES']; IDX=C['IDX']; OFF=(0,100000,200000)
PLAN=dict(synthetic_only=True,models=MODELS,weights=WEIGHTS,seeds=list(SEEDS),lengths=LENGTHS,offsets=OFF,audit_eval_length=N,methods=METHODS,selection='R97 unchanged',audit='R91 single GATE60 unchanged',rare_cell=3,stress='exact equal-weight evaluation of selected frozen rule, no re-selection',cost_bps=20,amplitude_bps=100,notional_yen=100000)
SHA=C['B']['digest'](PLAN)
def inputs(seed,n,w,m):
    rng=random.Random(seed); boundaries=np.cumsum(w); rows=[(rng.randrange(100),rng.randrange(2),rng.randrange(100)) for _ in range(n)]
    cells=np.searchsorted(boundaries,[r[0] for r in rows],side='right'); signs=np.array([SIGNS[r[1]] for r in rows]);u=np.array([r[2] for r in rows]);x=np.array([IDX[CELLS[i],int(s)] for i,s in zip(cells,signs)],dtype=np.int32);y=signs*np.where(u<np.array(m)[cells],1,-1)
    return x,y,cells

def theoretical(m,w):
    # state-conditional correct probability in percentage units
    q=np.array([[m[CELLS.index(c)] if d==s else 100-m[CELLS.index(c)] for (c,s),d in zip(STATES,table)] for table in MAT]);weights=np.array([w[CELLS.index(c)] for c,s in STATES]);rare=np.array([CELLS.index(c)==3 for c,s in STATES]);return q@weights, q[:,rare].sum(axis=1),q.sum(axis=1)

def study(test=False):
    counts={};summary={}
    def ck(k,a,b):
        if a!=b:raise AssertionError((k,a,b))
        counts[k]=counts.get(k,0)+1
    ck('seeds',len({s+o for s,o in product(SEEDS,OFF)}),len(SEEDS)*3);ck('tables',len(set(map(tuple,MAT))),256)
    for model,m in MODELS.items():
        summary[model]={}
        for freq,w in WEIGHTS.items():
            q,rare_q,bal_q=theoretical(m,w);best=max(q);rows={n:{method:[] for method in METHODS} for n in LENGTHS};coverage={n:[] for n in LENGTHS}
            if test:
                # exact enumeration of outcomes and state weights
                for j,table in enumerate(MAT):
                    total=0;rare_total=0;bal_total=0
                    for i,(c,s) in enumerate(STATES):
                        k=CELLS.index(c);hits=sum(int(table[i])==s*(1 if u<m[k] else -1) for u in range(100));total+=w[k]*hits;bal_total+=hits
                        if k==3:rare_total+=hits
                    ck('theory',(int(q[j]),int(rare_q[j]),int(bal_q[j])),(total,rare_total,bal_total))
            for seed in SEEDS:
                x,y,c=inputs(seed,max(LENGTHS),w,m);ax,ay,ac=inputs(seed+OFF[1],N,w,m);ex,ey,ec=inputs(seed+OFF[2],N,w,m);audit=C['scores'](ax,ay);ev=C['scores'](ex,ey)
                for n in LENGTHS:
                    half=n//2;a=C['scores'](x[:half],y[:half]);b=C['scores'](x[half:n],y[half:n]);t=a+b;chosen,detail=R['choose'](t,a,b);rare_train=int(np.count_nonzero(c[:n]==3));coverage[n].append(rare_train)
                    if test:
                        aa=np.count_nonzero(MAT[:,x[:half]]==y[:half],axis=1);bb=np.count_nonzero(MAT[:,x[half:n]]==y[half:n],axis=1);ck('scores',bool(np.array_equal(a,aa) and np.array_equal(b,bb)),True);ck('coverage',rare_train,sum(int(i)==3 for i in c[:n]));ia=[int(np.argmax(aa[:k])) for k in R['POOLS']];ib=[int(np.argmax(bb[:k])) for k in R['POOLS']];va=[int(bb[j]) for j in ia];vb=[int(aa[j]) for j in ib];ks=[16,24,256,256,R['POOLS'][int(np.argmax(va))],R['POOLS'][int(np.argmax(np.array(va)+vb))]];ck('folds',detail,dict(first_fit=ia,second_fit=ib,forward=va,backward=vb))
                    for method,(j,k) in zip(METHODS,chosen):
                        g=bool(R['S']['gates'](int(t[j]),int(audit[j]))['GATE60']);net=R['S']['net'](int(ev[j])) if g else 0;rows[n][method].append((j,g,net,int(t[j])))
                        if test:
                            kk=ks[METHODS.index(method)];jj=int(np.argmax((aa+bb)[:kk]-(R['PEN'][:kk] if method=='PENALIZED256' else 0)));ah=int(np.count_nonzero(MAT[j,ax]==ay));eh=int(np.count_nonzero(MAT[j,ex]==ey));ck('selection',(j,k),(jj,kk));ck('gate',g,ah>=167);ck('net',net,(2000*eh-1200*N) if g else 0)
            summary[model][freq]={}
            for n in LENGTHS:
                summary[model][freq][str(n)]={'rare_unseen':coverage[n].count(0),'rare_mean_count':sum(coverage[n])/len(SEEDS),'theory_no_rare':((100-w[3])/100)**n,'methods':{}}
                for method,vs in rows[n].items():
                    js=[v[0] for v in vs];ad=[v for v in vs if v[1]];z=len(vs);summary[model][freq][str(n)]['methods'][method]=dict(optimal=sum(bool(q[j]==best) for j in js),admitted=len(ad),admitted_nonpositive=sum(bool(q[j]<=12000) for j,g,net,t in ad),mean_train_accuracy=sum(v[3] for v in vs)/z/n,mean_true_accuracy=sum(int(q[j]) for j in js)/z/20000,mean_rare_accuracy=sum(int(rare_q[j]) for j in js)/z/200,admitted_rare_accuracy=(sum(int(rare_q[j]) for j,g,net,t in ad)/len(ad)/200 if ad else None),mean_gated_eval_net=sum(v[2] for v in vs)/z,expected_gated_net_same_weights=sum((int(q[j])/20000*2000-1200)*N for j,g,net,t in ad)/z,expected_gated_net_equal_weights=sum((int(bal_q[j])/800*2000-1200)*N for j,g,net,t in ad)/z)
    return dict(passed=sum(counts.values()),counts=counts,plan_sha=SHA) if test else dict(plan=PLAN,plan_sha=SHA,summary=summary)
if __name__=='__main__':
    p=argparse.ArgumentParser();g=p.add_mutually_exclusive_group(required=True);g.add_argument('--self-test',action='store_true');g.add_argument('--example',action='store_true');a=p.parse_args();print(json.dumps(study(a.self_test),indent=2,sort_keys=True))
