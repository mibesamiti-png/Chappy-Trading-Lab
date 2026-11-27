"""R91: fixed-candidate selection with independent one-shot audit; synthetic only."""
import argparse, hashlib, json, runpy, math
from pathlib import Path
from itertools import product
from fractions import Fraction as F

def load(name,sha):
    p=Path(__file__).with_name(name)
    if hashlib.sha256(p.read_bytes()).hexdigest()!=sha:raise ValueError(name+' hash')
    return runpy.run_path(str(p))
R=load('Chappy_Trading_Feature_Interaction_Study_v0.1.py','80f993c78544601a8b854acc0c6c1e70bf0e465a5e8a48ab02de53edb434cdc5')
G=load('Chappy_Trading_Statistical_Gate_Study_v0.1.py','27df717768cc5ada8d11f7d53ede615c24399eb125c68d2b29e2883503ee6b8b')
MODELS=dict(R['MODELS'],boundary_interaction=(60,40,40,60)); CAND=R['POLICIES'][:-1]; N=R['N']; SEEDS=range(91000,91256); OFFSETS=(0,100000,200000); POL=('SELECT_ONLY','TRAIN_POSITIVE','GATE50','GATE60','WAIT'); TH=G['TH']; CELLS=R['CELLS']; SIGNS=R['SIGNS']
PLAN=dict(synthetic_only=True,models=MODELS,candidates=CAND,seeds=list(SEEDS),offsets=OFFSETS,slots_per_phase=N,cost_bps=20,amplitude_bps=100,notional_yen=100000,tie='first in fixed order',audit='only chosen candidate, independent data, one attempt per policy, R86 thresholds',selection='maximize training net',evaluation='independent frozen candidate',observations_cost_yen=0,market_adoption=False)
SHA=R['digest'](PLAN)
A={(cell,sg):tuple(R['actions'](*cell,sg)[c] for c in CAND) for cell,sg in product(CELLS,SIGNS)}
def scores(model,seed):
    h=[0]*len(CAND)
    for cell,sg,u in R['inputs'](seed):
        v=sg*(1 if u<MODELS[model][CELLS.index(cell)] else -1)
        for i,a in enumerate(A[cell,sg]):h[i]+=a*v>0
    return tuple(h)
def net(h):return 2000*h-1200*N
def choose(h):return max(range(len(h)),key=lambda i:h[i])
def gates(train,audit):return dict(SELECT_ONLY=True,TRAIN_POSITIVE=net(train)>0,GATE50=audit>=TH[50][N],GATE60=audit>=TH[60][N],WAIT=False)
def theory(model):
    return tuple(F(sum((MODELS[model][i] if A[cell,1][j]==1 else 100-MODELS[model][i]) for i,cell in enumerate(CELLS)),400) for j in range(len(CAND)))
def run(model,seed):
    t,a,e=(scores(model,seed+offset) for offset in OFFSETS); j=choose(t); g=gates(t[j],a[j]);return dict(seed=seed,chosen=CAND[j],train_hits=t[j],audit_hits=a[j],eval_hits=e[j],train_all=t,audit_all=a,eval_all=e,admitted=g,eval_net={p:net(e[j]) if g[p] else 0 for p in POL})
def examples():
    out={}; runs={}
    for m in MODELS:
        rows=[run(m,s) for s in SEEDS];runs[m]=rows;q=theory(m);best=max(q); correct={c for c,v in zip(CAND,q) if v==best and v>F(3,5)}
        out[m]=dict(theoretical_accuracy={c:str(v) for c,v in zip(CAND,q)},best_economic_candidates=sorted(correct),chosen_counts={c:sum(r['chosen']==c for r in rows) for c in CAND},correct_choice=sum(r['chosen'] in correct for r in rows),mean_training_net=sum(net(r['train_hits']) for r in rows)/len(rows),mean_evaluation_net=sum(net(r['eval_hits']) for r in rows)/len(rows),policies={p:dict(admitted=sum(r['admitted'][p] for r in rows),mean_net_yen=sum(r['eval_net'][p] for r in rows)/len(rows),positive=sum(r['eval_net'][p]>0 for r in rows),negative=sum(r['eval_net'][p]<0 for r in rows),admitted_economic=sum(r['admitted'][p] and r['chosen'] in correct for r in rows),admitted_nonpositive=sum(r['admitted'][p] and q[CAND.index(r['chosen'])]<=F(3,5) for r in rows)) for p in POL})
    return dict(plan=PLAN,plan_sha=SHA,thresholds={g:TH[g][N] for g in TH},summary=out,runs=runs)
def tests():
    counts={}
    def ck(k,x,y):
        if x!=y:raise AssertionError((k,x,y))
        counts[k]=counts.get(k,0)+1
    dirs=((1,1,1,1),(-1,-1,-1,-1),(1,1,-1,-1),(1,-1,1,-1),(1,-1,-1,1),(-1,1,1,-1))
    for cell,sg in product(CELLS,SIGNS):ck('directions',A[cell,sg],tuple(sg*d[CELLS.index(cell)] for d in dirs))
    for g,a,b in ((50,1,2),(60,3,5)):
        k=TH[g][N];tail=lambda j:sum(math.comb(N,i)*a**i*(b-a)**(N-i) for i in range(j,N+1));ck('threshold_valid',20*tail(k)<=b**N,True);ck('threshold_minimal',20*tail(k-1)>b**N,True)
    ck('disjoint_seeds',len({s+o for s,o in product(SEEDS,OFFSETS)}),len(SEEDS)*3)
    for m in MODELS:
        for j,d in enumerate(dirs):
            h=sum(d[i]*(1 if u<MODELS[m][i] else -1)>0 for i,u in product(range(4),range(100)));ck('theory',theory(m)[j],F(h,400))
        for s in SEEDS:
            r=run(m,s);allh=[]
            for o in OFFSETS:
                rows=R['inputs'](s+o); h=tuple(sum(d[CELLS.index(cell)]*(1 if u<MODELS[m][CELLS.index(cell)] else -1)>0 for cell,sg,u in rows) for d in dirs);allh.append(h)
            t,a,e=allh;j=sorted(range(len(CAND)),key=lambda i:(-t[i],i))[0];ck('train_scores',r['train_all'],t);ck('audit_scores',r['audit_all'],a);ck('eval_scores',r['eval_all'],e);ck('choice',r['chosen'],CAND[j]);ck('selected_hits',(r['train_hits'],r['audit_hits'],r['eval_hits']),(t[j],a[j],e[j]));ck('audit_gate50',r['admitted']['GATE50'],a[j]>=TH[50][N]);ck('audit_gate60',r['admitted']['GATE60'],a[j]>=TH[60][N]);ck('train_positive',r['admitted']['TRAIN_POSITIVE'],800*t[j]-1200*(N-t[j])>0);ck('baseline',r['admitted']['SELECT_ONLY'] and not r['admitted']['WAIT'],True)
            for p in POL:ck('net',r['eval_net'][p],(800*e[j]-1200*(N-e[j])) if r['admitted'][p] else 0)
            if s==SEEDS.start and m in R['MODELS']:
                for o,h in zip(OFFSETS,allh):ck('R90_reuse',h,tuple(R['evaluate'](m,s+o)[c]['hits'] for c in CAND))
    return dict(passed=sum(counts.values()),counts=counts)
if __name__=='__main__':
    p=argparse.ArgumentParser();g=p.add_mutually_exclusive_group(required=True);g.add_argument('--self-test',action='store_true');g.add_argument('--example',action='store_true');a=p.parse_args();print(json.dumps(tests() if a.self_test else examples(),indent=2,sort_keys=True))
