"""R89: conditional predictive value, synthetic only, no market prices/orders."""
import argparse, hashlib, json, random, runpy
from pathlib import Path
from fractions import Fraction as F
from itertools import product
P=Path(__file__).with_name('Chappy_Trading_Composite_Hypothesis_Study_v0.1.py')
if hashlib.sha256(P.read_bytes()).hexdigest()!='6008d21c6ee5e2ac7ce6a6a59e87c7f88bd3e7407ce99056a0859e4525ef5f31': raise ValueError('R71 hash')
R=runpy.run_path(str(P)); digest=R['digest']
CONTEXTS=('isolated','shared'); SIGNS=(-1,1)
MODELS={'null':(50,50),'uniform':(75,75),'conditional':(75,25),'opposite':(25,75),'weak':(55,45)}
POLICIES=('CONTINUE','REVERSE','CONTEXT','OPPOSITE','ISOLATED_ONLY','WAIT')
N=256; SEEDS=tuple(range(89000,89064)); COST=20; AMPLITUDE=100
PLAN=dict(synthetic_only=True,models=MODELS,policies=POLICIES,slots=N,seeds=SEEDS,cost_bps=COST,amplitude_bps=AMPLITUDE,notional_yen=100000,context_probability='1/2',sign_probability='1/2',action_before_result=True,fit=False,gate=False,paired_seeds=True,feature_source='R71 four fixed eligible prefix prototypes',market_adoption=False)
SHA=digest(PLAN)

def prototypes():
    out={}
    for st,sg in product(CONTEXTS,SIGNS):
        cid=f'R89:{st}:{sg}'; rows=R['prefix'](st,sg); fr=R['freeze'](cid,rows)
        if not fr['eligible'] or fr['stratum']!=st or fr['predictions']['CONTINUE']!=('UP' if sg==1 else 'DOWN'):raise ValueError('unexpected prefix')
        out[st,sg]=fr
    return out
PROT=prototypes()

def actions(st,sg):
    fr=PROT[st,sg]; d={'UP':1,'DOWN':-1}[fr['predictions']['CONTINUE']]; c=d if st=='isolated' else -d
    return dict(zip(POLICIES,(d,-d,c,-c,d if st=='isolated' else 0,0)))

def inputs(seed):
    rng=random.Random(seed)
    return [(CONTEXTS[rng.randrange(2)],SIGNS[rng.randrange(2)],rng.randrange(100)) for _ in range(N)]

def result(model,st,sg,u):
    return sg*(1 if u<MODELS[model][CONTEXTS.index(st)] else -1)*AMPLITUDE

def theory(model,policy):
    hit=F(0); selected=F(0); net=F(0)
    for st,sg in product(CONTEXTS,SIGNS):
        a=actions(st,sg)[policy]; p=F(MODELS[model][CONTEXTS.index(st)],100)
        for rel,pr in ((1,p),(-1,1-p)):
            w=pr/4; r=sg*rel*AMPLITUDE
            if a:
                selected+=w; hit+=w*(a*r>0);net+=w*(a*r-COST)*10
    return {'selection':str(selected),'accuracy':str(hit/selected) if selected else None,'yen_per_opportunity':str(net),'expected_total_yen':str(net*N)}

def evaluate(model,seed):
    rows=inputs(seed)
    frozen=[actions(st,sg) for st,sg,_ in rows]
    outcomes=[result(model,*r) for r in rows]
    out={}
    for policy in POLICIES:
        a=[d[policy] for d in frozen]; net=[(x*y-COST)*10 if x else 0 for x,y in zip(a,outcomes)]
        total=0; peak=0; dd=0
        for v in net:
            total+=v;peak=max(peak,total);dd=max(dd,peak-total)
        out[policy]={'selected':sum(x!=0 for x in a),'hits':sum(x*y>0 for x,y in zip(a,outcomes)),'net_yen':total,'max_dd_yen':dd}
    return out

def examples():
    summaries=[]
    for model in MODELS:
        trials=[evaluate(model,s) for s in SEEDS]
        for policy in POLICIES:
            vals=[t[policy] for t in trials];n=sum(v['selected'] for v in vals);h=sum(v['hits'] for v in vals)
            summaries.append(dict(model=model,policy=policy,theory=theory(model,policy),selected=n,hits=h,accuracy=float(F(h,n)) if n else None,mean_net_yen=sum(v['net_yen'] for v in vals)/len(vals),positive_trials=sum(v['net_yen']>0 for v in vals),mean_max_dd_yen=sum(v['max_dd_yen'] for v in vals)/len(vals)))
    return dict(plan=PLAN,plan_sha=SHA,prototype_sha={f'{st}:{sg}':digest(v) for (st,sg),v in PROT.items()},summary=summaries)

def tests():
    counts={}
    def ck(k,x):
        if not x:raise AssertionError(k)
        counts[k]=counts.get(k,0)+1
    expected={'null':(-200,-200,-200,-200,-100,0),'uniform':(300,-700,-200,-200,150,0),'conditional':(-200,-200,300,-700,150,0),'opposite':(-200,-200,-700,300,-350,0),'weak':(-200,-200,-100,-300,-50,0)}
    for model,pol in product(MODELS,POLICIES):
        ck('exact_expected_value',F(theory(model,pol)['yen_per_opportunity'])==expected[model][POLICIES.index(pol)])
        # independent enumeration of all 400 equiprobable states
        acc=[]
        for st,sg,u in product(CONTEXTS,SIGNS,range(100)):
            a=actions(st,sg)[pol]; r=result(model,st,sg,u); acc.append((a,r))
        ck('enumerated_ev',F(sum((a*r-COST)*10 if a else 0 for a,r in acc),400)==F(theory(model,pol)['yen_per_opportunity']))
        n=sum(bool(a) for a,r in acc); h=sum(a*r>0 for a,r in acc)
        ck('enumerated_selection',F(n,400)==F(theory(model,pol)['selection']));ck('enumerated_accuracy',(str(F(h,n)) if n else None)==theory(model,pol)['accuracy'])
    for model,seed in product(MODELS,SEEDS):
        rows=inputs(seed); actual=evaluate(model,seed)
        for policy in POLICIES:
            # Independently express relative-to-signal actions and calculate realized P/L.
            dirs={'CONTINUE':(1,1),'REVERSE':(-1,-1),'CONTEXT':(1,-1),'OPPOSITE':(-1,1),'ISOLATED_ONLY':(1,0),'WAIT':(0,0)}[policy]
            ds=[dirs[st=='shared'] for st,sg,u in rows]; rel=[1 if u<MODELS[model][st=='shared'] else -1 for st,sg,u in rows]
            cash=[800 if a*b==1 else -1200 if a*b==-1 else 0 for a,b in zip(ds,rel)]; curve=[0]
            for c in cash:curve.append(curve[-1]+c)
            v=actual[policy];ck('net',v['net_yen']==sum(cash));ck('hits',v['hits']==cash.count(800));ck('selected',v['selected']==sum(bool(a) for a in ds));ck('drawdown',v['max_dd_yen']==max(max(curve[:i+1])-x for i,x in enumerate(curve)))
    for st,sg in product(CONTEXTS,SIGNS):
        ck('sign_symmetry',all(a==-actions(st,-sg)[p] for p,a in actions(st,sg).items()))
        fr=PROT[st,sg]; rows=R['prefix'](st,sg)
        for rel in (-1,1):ck('R71_future_mask',R['freeze'](fr['case_id'],rows+R['tail'](rows,sg,rel))==fr)
    return dict(passed=sum(counts.values()),counts=counts)
if __name__=='__main__':
    p=argparse.ArgumentParser();g=p.add_mutually_exclusive_group(required=True);g.add_argument('--self-test',action='store_true');g.add_argument('--example',action='store_true');a=p.parse_args();print(json.dumps(tests() if a.self_test else examples(),indent=2,sort_keys=True))
