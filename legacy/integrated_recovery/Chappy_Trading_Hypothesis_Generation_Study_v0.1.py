"""R93: bounded structural hypothesis generation; synthetic only, no orders."""
import argparse, hashlib, json, runpy
from pathlib import Path
from itertools import product
from fractions import Fraction as F
p=Path(__file__).with_name('Chappy_Trading_Candidate_Limit_Study_v0.1.py')
if hashlib.sha256(p.read_bytes()).hexdigest()!='e90760f0539e336e87e843d0325f6a83fd337513857fd53f2bc0131e58de06d5':raise ValueError('R92 hash')
R=runpy.run_path(str(p)); S=R['R']; B=R['B']; C=R['C']; CELLS=R['CELLS']; SIGNS=R['SIGNS']; N=R['N']; OFF=R['OFF']; STATES=tuple(product(CELLS,SIGNS)); SEEDS=range(93000,93256)
# Each hypothesis is an eight-state direction table; names retain provenance.
def generate():
    out={c:tuple(S['A'][state][j] for state in STATES) for j,c in enumerate(C)}
    seen=set(out.values()); provenance={c:('base',c) for c in C}
    for op in ('NEGATE','REMOVE_SIGNAL','NEGATE_REMOVE_SIGNAL'):
        for c in C:
            v=tuple(d*(-1 if op in ('NEGATE','NEGATE_REMOVE_SIGNAL') else 1)*(sg if op!='NEGATE' else 1) for d,(_,sg) in zip(out[c],STATES))
            if v not in seen:
                name=op+':'+c;out[name]=v;seen.add(v);provenance[name]=(op,c)
    return out,provenance
H,PROV=generate(); NAMES=tuple(H); POOLS={'BASE':C,'EXPANDED':NAMES}
MODELS={k:R['M'][k] for k in ('null','weak_interaction','boundary_interaction','interaction','inverse_context','absolute_up')};MODELS.update(inverse_body=(25,75,25,75),nonlinear=(70,70,70,30))
PLAN=dict(synthetic_only=True,models=MODELS,seed_start=SEEDS.start,seed_stop=SEEDS.stop,offsets=OFF,slots=N,pools=POOLS,operators=['NEGATE','REMOVE_SIGNAL','NEGATE_REMOVE_SIGNAL'],dedup='exact action table',selection='R91 fixed-order training maximum',audit='R91 independent one-shot GATE60',cost_bps=20,amplitude_bps=100,notional_yen=100000,market_adoption=False)
SHA=B['digest'](PLAN)
IDX={s:i for i,s in enumerate(STATES)}
TABLE=tuple(H.values())
def outcome(m,cell,sg,u):
    return (1 if u<75 else -1) if m=='absolute_up' else sg*(1 if u<MODELS[m][CELLS.index(cell)] else -1)
def scores(m,rows):
    # compress observations into signed outcome frequencies per input state.
    v=[0]*8; n=0
    for cell,sg,u in rows:v[IDX[cell,sg]]+=outcome(m,cell,sg,u);n+=1
    return tuple((n+sum(d*x for d,x in zip(h,v)))//2 for h in TABLE)
def theory(m):return tuple(F(h,800) for h in scores(m,product(CELLS,SIGNS,range(100))))
def run(m,seed):
    t,a,e=(scores(m,B['inputs'](seed+o)) for o in OFF); result={}
    for pool,names in POOLS.items():
        j=S['choose'](t[:len(names)]);g=S['gates'](t[j],a[j])['GATE60'];result[pool]=dict(chosen=NAMES[j],train_hits=t[j],audit_hits=a[j],eval_hits=e[j],admitted=g,train_net=S['net'](t[j]),raw_eval_net=S['net'](e[j]),gated_eval_net=S['net'](e[j]) if g else 0)
    return dict(seed=seed,pools=result)
def examples():
    summary={}; runs={}
    for m in MODELS:
        q=theory(m);rows=[run(m,s) for s in SEEDS];runs[m]=rows;summary[m]={}
        for pool,names in POOLS.items():
            vv=[r['pools'][pool] for r in rows];best=max(q[:len(names)]);correct={n for n,x in zip(names,q) if x==best and x>F(3,5)}
            summary[m][pool]=dict(best_accuracy=str(best),best_candidates=sorted(correct),correct_choice=sum(v['chosen'] in correct for v in vv),admitted=sum(v['admitted'] for v in vv),admitted_nonpositive=sum(v['admitted'] and q[NAMES.index(v['chosen'])]<=F(3,5) for v in vv),chosen_counts={n:sum(v['chosen']==n for v in vv) for n in names},**{f'mean_{k}':sum(v[k] for v in vv)/len(vv) for k in ('train_net','raw_eval_net','gated_eval_net')})
    return dict(plan=PLAN,plan_sha=SHA,provenance=PROV,tables=H,summary=summary,runs=runs)
def tests():
    counts={}
    def ck(k,x,y):
        if x!=y:raise AssertionError((k,x,y))
        counts[k]=counts.get(k,0)+1
    ck('pool_count',len(H),16);ck('dedup',len(set(TABLE)),16)
    # Independent oracle: all signed monomials in context/body, with optional input sign.
    expected={tuple(z*(sg if use else 1)*(1 if cell[0]=='isolated' else -1)**a*(1 if cell[1]=='strong' else -1)**b for cell,sg in STATES) for z,use,a,b in product((-1,1),(0,1),(0,1),(0,1))}
    ck('closure',set(TABLE),expected)
    ck('base',TABLE[:6],tuple(tuple(S['A'][s][j] for s in STATES) for j in range(6)))
    ck('seeds',len({s+o for s,o in product(SEEDS,OFF)}),len(SEEDS)*3)
    def oracle(m,rows):
        rows=list(rows);return tuple(sum(h[STATES.index((cell,sg))]==((1 if u<75 else -1) if m=='absolute_up' else sg*(1 if u<MODELS[m][CELLS.index(cell)] else -1)) for cell,sg,u in rows) for h in TABLE)
    for m in MODELS:
        q=theory(m);ck('theory',q,tuple(F(x,800) for x in oracle(m,product(CELLS,SIGNS,range(100)))))
        if m in R['M']:ck('R92_base_theory',q[:6],R['theory'](m)[:6])
        if m in ('inverse_context','absolute_up','inverse_body'):ck('missing_base',max(q[:6]),F(1,2));ck('recovered',max(q),F(3,4))
        if m=='nonlinear':ck('remaining_limit',max(q),F(3,5))
        for seed in SEEDS:
            r=run(m,seed);t,a,e=(oracle(m,B['inputs'](seed+o)) for o in OFF)
            for pool,names in POOLS.items():
                v=r['pools'][pool];j=sorted(range(len(names)),key=lambda i:(-t[i],i))[0];g=a[j]>=167
                ck('choice',v['chosen'],NAMES[j]);ck('hits',(v['train_hits'],v['audit_hits'],v['eval_hits']),(t[j],a[j],e[j]));ck('audit',v['admitted'],g);ck('train_net',v['train_net'],800*t[j]-1200*(N-t[j]));ck('raw_net',v['raw_eval_net'],800*e[j]-1200*(N-e[j]));ck('gated_net',v['gated_eval_net'],(800*e[j]-1200*(N-e[j])) if g else 0)
            if m in R['M']:ck('base_score_reuse',t[:6],R['scores'](m,B['inputs'](seed))[:6])
    return dict(passed=sum(counts.values()),counts=counts)
if __name__=='__main__':
    p=argparse.ArgumentParser();g=p.add_mutually_exclusive_group(required=True);g.add_argument('--self-test',action='store_true');g.add_argument('--example',action='store_true');a=p.parse_args();print(json.dumps(tests() if a.self_test else examples(),indent=2,sort_keys=True))
