"""R90 synthetic fixed feature interaction. No market prices, orders, fitting."""
import argparse, hashlib, json, random, runpy
from pathlib import Path
from fractions import Fraction as F
from itertools import product
P=Path(__file__).with_name('Chappy_Trading_Conditional_Edge_Study_v0.1.py')
if hashlib.sha256(P.read_bytes()).hexdigest()!='ffe40de972effd252c9e0fa27894551d9585f74850dfd7209f7db03fed560daf':raise ValueError('R89 hash')
R=runpy.run_path(str(P)); B=R['R']; digest=R['digest']
CONTEXTS=R['CONTEXTS']; SIGNS=R['SIGNS']; BODIES=('strong','weak'); CELLS=tuple(product(CONTEXTS,BODIES))
MODELS={'null':(50,50,50,50),'context_only':(75,75,25,25),'body_only':(75,25,75,25),'interaction':(75,25,25,75),'opposite_interaction':(25,75,75,25),'weak_interaction':(55,45,45,55)}
POLICIES=('CONTINUE','REVERSE','CONTEXT','BODY','JOINT','JOINT_OPPOSITE','WAIT')
N=R['N']; COST=R['COST']; AMP=R['AMPLITUDE']; SEEDS=tuple(range(90000,90064))
PLAN=dict(synthetic_only=True,cells=CELLS,models=MODELS,policies=POLICIES,seeds=SEEDS,slots=N,cost_bps=COST,amplitude_bps=AMP,notional_yen=100000,cell_probability='1/4',sign_probability='1/2',fixed_rules=True,fit=False,gate=False,body_definition='absolute OHLC body/range; close change fixed +/-8 on artificial open 100',feature_source='R71 prefix with weak-body high/low edit, R68 freeze, R70 context; weak body outside R71 eligibility',market_adoption=False)
SHA=digest(PLAN)
def prefix(st,body,sg):
    p=B['prefix'](st,sg)
    if body=='weak':
        p=[dict(r,high=120,low=80) if r['symbol']=='X' and r['day']==B['DAY'] and r['slot']==B['SLOT'] else r for r in p]
    return p

def freeze(cid,p):
    c=B['context'](p,B['DAY'],B['SLOT'],B['CUT']); b=B['basefreeze'](cid,B['local_bars'](p,B['CUT']),3,1200); f=b['feature']; s=c['context']['short']; l=c['context']['long']
    if not f or any(x[k] is None for x in (s,l) for k in ('target','sector','outside','target_over_sector','sector_over_outside')) or F(f['gap'])!=0 or F(s['target'])<2 or F(f['volume_ratio'])<2: return None
    z=F(f['body_fraction']); body='strong' if abs(z)>=F(3,4) else 'weak' if 0<abs(z)<=F(1,4) else None
    if body is None:return None
    return dict(context='isolated' if F(s['target_over_sector'])>=2 else 'shared',body=body,sign=1 if z>0 else -1,base=b,context_sha=digest(c))
PROT={}
for st,body,sg in product(CONTEXTS,BODIES,SIGNS):
    f=freeze(f'R90:{st}:{body}:{sg}',prefix(st,body,sg))
    if f is None or (f['context'],f['body'],f['sign'])!=(st,body,sg):raise ValueError('prototype')
    PROT[st,body,sg]=f

def actions(st,body,sg):
    f=PROT[st,body,sg]; d=f['sign']; c=1 if f['context']=='isolated' else -1; b=1 if f['body']=='strong' else -1
    return dict(zip(POLICIES,(d,-d,d*c,d*b,d*c*b,-d*c*b,0)))
def inputs(seed):
    rng=random.Random(seed)
    return [(CELLS[rng.randrange(4)],SIGNS[rng.randrange(2)],rng.randrange(100)) for _ in range(N)]
def outcome(model,cell,sg,u):return sg*AMP*(1 if u<MODELS[model][CELLS.index(cell)] else -1)
def theory(model,policy):
    sel=F(0);hit=F(0);net=F(0)
    for cell,sg in product(CELLS,SIGNS):
        a=actions(*cell,sg)[policy];p=F(MODELS[model][CELLS.index(cell)],100)
        for rel,pr in ((1,p),(-1,1-p)):
            w=pr/8;r=sg*rel*AMP
            if a:sel+=w;hit+=w*(a*r>0);net+=w*(a*r-COST)*10
    return dict(selection=str(sel),accuracy=str(hit/sel) if sel else None,yen_per_opportunity=str(net),expected_total_yen=str(net*N))
def evaluate(model,seed):
    rows=inputs(seed); aa=[actions(*cell,sg) for cell,sg,u in rows]; rr=[outcome(model,*r) for r in rows];out={}
    for pol in POLICIES:
        a=[x[pol] for x in aa];cash=[(x*y-COST)*10 if x else 0 for x,y in zip(a,rr)];total=peak=dd=0
        for v in cash:total+=v;peak=max(peak,total);dd=max(dd,peak-total)
        out[pol]=dict(selected=sum(bool(x) for x in a),hits=sum(x*y>0 for x,y in zip(a,rr)),net_yen=total,max_dd_yen=dd)
    return out

def examples():
    summary=[]
    for model in MODELS:
        trials=[evaluate(model,s) for s in SEEDS]
        for pol in POLICIES:
            vv=[v[pol] for v in trials]; n=sum(v['selected'] for v in vv);h=sum(v['hits'] for v in vv)
            summary.append(dict(model=model,policy=pol,theory=theory(model,pol),selected=n,hits=h,accuracy=h/n if n else None,mean_net_yen=sum(v['net_yen'] for v in vv)/len(vv),positive_trials=sum(v['net_yen']>0 for v in vv),mean_max_dd_yen=sum(v['max_dd_yen'] for v in vv)/len(vv)))
    return dict(plan=PLAN,plan_sha=SHA,prototype_sha={':'.join(map(str,k)):digest(v) for k,v in PROT.items()},summary=summary)

def tests():
    counts={}
    def ck(k,v):
        if not v:raise AssertionError(k)
        counts[k]=counts.get(k,0)+1
    expected={'null':(-200,-200,-200,-200,-200,-200,0),'context_only':(-200,-200,300,-200,-200,-200,0),'body_only':(-200,-200,-200,300,-200,-200,0),'interaction':(-200,-200,-200,-200,300,-700,0),'opposite_interaction':(-200,-200,-200,-200,-700,300,0),'weak_interaction':(-200,-200,-200,-200,-100,-300,0)}
    # Fixed independent oracle: relative-to-signal directions in cell order.
    dirs=dict(zip(POLICIES,((1,1,1,1),(-1,-1,-1,-1),(1,1,-1,-1),(1,-1,1,-1),(1,-1,-1,1),(-1,1,1,-1),(0,0,0,0))))
    for model,pol in product(MODELS,POLICIES):
        t=theory(model,pol);ck('exact_EV',F(t['yen_per_opportunity'])==expected[model][POLICIES.index(pol)])
        v=[(dirs[pol][i],1 if u<MODELS[model][i] else -1) for i,sg,u in product(range(4),SIGNS,range(100))];n=sum(bool(a) for a,b in v);h=sum(a*b==1 for a,b in v)
        ck('enumerated_EV',F(sum(800 if a*b==1 else -1200 if a*b==-1 else 0 for a,b in v),800)==F(t['yen_per_opportunity']));ck('enumerated_accuracy',(str(F(h,n)) if n else None)==t['accuracy']);ck('enumerated_selection',F(n,800)==F(t['selection']))
    for model,seed in product(MODELS,SEEDS):
        rows=inputs(seed);actual=evaluate(model,seed)
        for pol in POLICIES:
            cash=[800 if z==1 else -1200 if z==-1 else 0 for cell,sg,u in rows for z in [dirs[pol][CELLS.index(cell)]*(1 if u<MODELS[model][CELLS.index(cell)] else -1)]];curve=[0]
            for c in cash:curve.append(curve[-1]+c)
            v=actual[pol];ck('net',v['net_yen']==sum(cash));ck('hits',v['hits']==cash.count(800));ck('selected',v['selected']==sum(bool(c) for c in cash));ck('drawdown',v['max_dd_yen']==max(max(curve[:i+1])-x for i,x in enumerate(curve)))
    for st,body,sg in product(CONTEXTS,BODIES,SIGNS):
        p=prefix(st,body,sg);f=PROT[st,body,sg];cid=f['base']['case_id'];ck('body_fraction',F(f['base']['feature']['body_fraction'])==sg*(F(4,5) if body=='strong' else F(1,5)));ck('same_close_change',F(f['base']['feature']['close_change'])==F(sg*8,100));ck('sign_symmetry',all(a==-actions(st,body,-sg)[k] for k,a in actions(st,body,sg).items()));ck('order',freeze(cid,p[::-1])==f)
        for rel in (-1,1):ck('future_mask',freeze(cid,p+B['tail'](p,sg,rel))==f)
        ck('missing_peer',freeze(cid,[r for r in p if not(r['symbol']=='S3' and r['day']==B['DAY'])]) is None)
        ck('old_eligibility',B['freeze'](cid,p)['eligible']==(body=='strong'))
    return dict(passed=sum(counts.values()),counts=counts)
if __name__=='__main__':
    p=argparse.ArgumentParser();g=p.add_mutually_exclusive_group(required=True);g.add_argument('--self-test',action='store_true');g.add_argument('--example',action='store_true');a=p.parse_args();print(json.dumps(tests() if a.self_test else examples(),indent=2,sort_keys=True))
