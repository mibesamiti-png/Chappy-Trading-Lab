"""R94: bounded conditional direction tables; synthetic only, no orders."""
import argparse, hashlib, json, runpy
from pathlib import Path
from itertools import product
from fractions import Fraction as F
p=Path(__file__).with_name('Chappy_Trading_Hypothesis_Generation_Study_v0.1.py')
if hashlib.sha256(p.read_bytes()).hexdigest()!='d3e35c8b08a87d2c3e5baefd22a647f88aa1c24504fbd2b9263dd3d533defdb8':raise ValueError('R93 hash')
R=runpy.run_path(str(p)); S=R['S']; B=R['B']; CELLS=R['CELLS']; SIGNS=R['SIGNS']; STATES=R['STATES']; N=R['N']; OFF=R['OFF']; SEEDS=range(94000,94256)
def generate():
    h=dict(R['H']); seen=set(h.values()); provenance=dict(R['PROV'])
    for pattern in product((-1,1),repeat=4):
        table=tuple(pattern[CELLS.index(cell)]*sg for cell,sg in STATES)
        if table not in seen:
            name='RELATIVE_TABLE:'+''.join('+' if d==1 else '-' for d in pattern);h[name]=table;seen.add(table);provenance[name]=('RELATIVE_TABLE',pattern)
    return h,provenance
H,PROV=generate(); NAMES=tuple(H); TABLE=tuple(H.values()); IDX={s:i for i,s in enumerate(STATES)}
POOLS={'STRUCTURAL16':16,'CONDITIONAL24':24}
MODELS=dict(R['MODELS'],absolute_nonlinear=(70,70,70,30),mixed_direction=(75,75,75,75))
PLAN=dict(synthetic_only=True,models=MODELS,seeds=list(SEEDS),offsets=OFF,slots=N,pools=POOLS,operators='enumerate 16 relative four-cell tables, exact dedup with R93',selection='R91 fixed order maximum',audit='R91 independent one-shot GATE60',cost_bps=20,amplitude_bps=100,notional_yen=100000,absolute_nonlinear='absolute positive probability by cell',mixed_direction='75% absolute up for isolated, 75% signal continuation for shared',market_adoption=False)
SHA=B['digest'](PLAN)
def outcome(m,cell,sg,u):
    if m=='absolute_nonlinear':return 1 if u<MODELS[m][CELLS.index(cell)] else -1
    if m=='mixed_direction':return (1 if cell[0]=='isolated' else sg)*(1 if u<75 else -1)
    return R['outcome'](m,cell,sg,u)
def scores(m,rows):
    v=[0]*8;n=0
    for cell,sg,u in rows:v[IDX[cell,sg]]+=outcome(m,cell,sg,u);n+=1
    return tuple((n+sum(d*x for d,x in zip(h,v)))//2 for h in TABLE)
def theory(m):return tuple(F(x,800) for x in scores(m,product(CELLS,SIGNS,range(100))))
def run(m,seed):
    t,a,e=(scores(m,B['inputs'](seed+o)) for o in OFF);out={}
    for pool,k in POOLS.items():
        j=S['choose'](t[:k]);g=S['gates'](t[j],a[j])['GATE60'];out[pool]=dict(chosen=NAMES[j],train_hits=t[j],audit_hits=a[j],eval_hits=e[j],admitted=g,train_net=S['net'](t[j]),raw_eval_net=S['net'](e[j]),gated_eval_net=S['net'](e[j]) if g else 0)
    return dict(seed=seed,pools=out)
def examples():
    summary={};runs={}
    for m in MODELS:
        q=theory(m);rows=[run(m,s) for s in SEEDS];runs[m]=rows;summary[m]={}
        for pool,k in POOLS.items():
            vv=[r['pools'][pool] for r in rows];best=max(q[:k]);correct={n for n,x in zip(NAMES[:k],q) if x==best and x>F(3,5)}
            summary[m][pool]=dict(best_accuracy=str(best),best_candidates=sorted(correct),correct_choice=sum(v['chosen'] in correct for v in vv),admitted=sum(v['admitted'] for v in vv),admitted_nonpositive=sum(v['admitted'] and q[NAMES.index(v['chosen'])]<=F(3,5) for v in vv),chosen_counts={n:sum(v['chosen']==n for v in vv) for n in NAMES[:k]},**{f'mean_{key}':sum(v[key] for v in vv)/len(vv) for key in ('train_net','raw_eval_net','gated_eval_net')})
    return dict(plan=PLAN,plan_sha=SHA,provenance=PROV,tables=H,summary=summary,runs=runs)
def tests():
    import numpy as np
    counts={}
    def ck(k,x,y):
        if x!=y:raise AssertionError((k,x,y))
        counts[k]=counts.get(k,0)+1
    ck('pool_count',len(H),24);ck('dedup',len(set(TABLE)),24);ck('base',TABLE[:16],R['TABLE'])
    relative={tuple(d*sg for d in pat for sg in SIGNS) for pat in product((-1,1),repeat=4)}
    ck('relative_closure',set(TABLE),set(R['TABLE'])|relative);ck('relative_count',len(relative),16)
    ck('seeds',len({s+o for s,o in product(SEEDS,OFF)}),len(SEEDS)*3)
    mat=np.array(TABLE,dtype=np.int16)
    def oracle(m,rows):
        states=[];v=[]
        for cell,sg,u in rows:
            i=CELLS.index(cell);states.append(STATES.index((cell,sg)))
            if m=='absolute_up':d=1 if u<75 else -1
            elif m=='absolute_nonlinear':d=1 if u<(70,70,70,30)[i] else -1
            elif m=='mixed_direction':d=(1 if i<2 else sg)*(1 if u<75 else -1)
            else:d=sg*(1 if u<MODELS[m][i] else -1)
            v.append(d)
        return tuple(map(int,np.sum(mat[:,states]==np.array(v),axis=1)))
    for m in MODELS:
        q=theory(m);ck('theory',q,tuple(F(x,800) for x in oracle(m,product(CELLS,SIGNS,range(100)))))
        if m in R['MODELS']:ck('R93_theory',q[:16],R['theory'](m))
        if m=='nonlinear':ck('old_limit',max(q[:16]),F(3,5));ck('new_best',max(q),F(7,10))
        if m=='absolute_nonlinear':ck('absolute_limit',max(q),F(3,5))
        if m=='mixed_direction':ck('mixed_limit',max(q),F(5,8))
        for seed in SEEDS:
            r=run(m,seed);t,a,e=(oracle(m,B['inputs'](seed+o)) for o in OFF)
            for pool,k in POOLS.items():
                v=r['pools'][pool];j=sorted(range(k),key=lambda i:(-t[i],i))[0];g=a[j]>=167
                ck('choice',v['chosen'],NAMES[j]);ck('hits',(v['train_hits'],v['audit_hits'],v['eval_hits']),(t[j],a[j],e[j]));ck('audit',v['admitted'],g);ck('train_net',v['train_net'],2000*t[j]-1200*N);ck('raw_net',v['raw_eval_net'],2000*e[j]-1200*N);ck('gated_net',v['gated_eval_net'],(2000*e[j]-1200*N) if g else 0)
            if m in R['MODELS']:ck('R93_reuse',r['pools']['STRUCTURAL16'],R['run'](m,seed)['pools']['EXPANDED'])
    return dict(passed=sum(counts.values()),counts=counts)
if __name__=='__main__':
    p=argparse.ArgumentParser();g=p.add_mutually_exclusive_group(required=True);g.add_argument('--self-test',action='store_true');g.add_argument('--example',action='store_true');a=p.parse_args();print(json.dumps(tests() if a.self_test else examples(),indent=2,sort_keys=True))
