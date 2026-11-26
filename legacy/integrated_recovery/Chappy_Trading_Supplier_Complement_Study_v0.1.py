"""R140: supplier coverage, same canonical observations; synthetic only."""
import argparse, hashlib, json, runpy
from pathlib import Path
from collections import Counter
from fractions import Fraction as F
import numpy as np
ROOT=Path(__file__).parent
PARENT='Chappy_Trading_External_Audit_Ledger_Study_v0.1.py'
SHA='11c001f0e58de01272662cdad13500f9abb071df3ad2907cdb2708fa5267d8f6'
if hashlib.sha256((ROOT/PARENT).read_bytes()).hexdigest()!=SHA:raise ValueError('parent')
P=runpy.run_path(str(ROOT/PARENT)); Ledger=P['Ledger']; A=P['A']; H=P['H']; K=P['K']; R=P['R']; digest=P['digest']
SEEDS=range(140000,140032)
MODES=('single','copy','independent','complement','common_outage','conflict')
PLAN=dict(parent=SHA,seeds=list(SEEDS),modes=MODES,coverage='80% marginal per supplier; common_outage has batch-level common 20% failure; conflict uses independent coverage and B flips 2% of received values',cost=100,delay=0,prior=.5,scope='same 32 canonical slots, fixed audit, no post-admission monitoring, synthetic only')
def masks(mode,u,v,b):
    a=u<80
    if mode=='single':return a,None
    if mode=='copy':return a,a.copy()
    if mode in ('independent','conflict'):return a,v<80
    if mode=='complement':return a,u>=20
    if mode=='common_outage':return np.full(len(A),b<80),np.full(len(A),b<80)
    raise ValueError(mode)
def study():
    c=Counter(); z={}; fixtures={}; theory={}
    def ck(k,b):
        if not b:raise AssertionError(k)
        c[k]+=1
    def replay(mode,y,a,b,flip):
        l=Ledger(); two=b is not None; ck('open',l.open({'A':100,'B':100} if two else {'A':100},0)); w=y[np.array(A)-1]; oracle={}; conflict=False; nreports=0
        for i,t in enumerate(A):
            ck('advance',l.advance(t))
            vals=[]
            if a[i]:vals.append(('A',int(w[i])))
            if two and b[i]:vals.append(('B',int(w[i])^int(mode=='conflict' and flip[i])))
            for p,x in vals:ck('receive',l.receive(p,t,x));nreports+=1
            if vals:oracle[t]=vals[0][1]
            if len(vals)==2 and vals[0][1]!=vals[1][1]:conflict=True
        ck('finalize',l.finalize()); ck('end',l.advance(H)); passes=not conflict and sum(oracle.values())>=K
        ck('conflict_oracle',l.conflict==conflict);ck('pass_oracle',bool(l.entry and l.entry['passed'])==passes);ck('unique',l.values==oracle);ck('cost',l.cost==3200*(1+two) and l.cash==100000-l.cost);ck('look',l.spent==34+int(not conflict));ck('provenance',len(l.reports)==nreports)
        if l.entry:
            ck('rows',l.entry['rows']==[[['synthetic',t],oracle.get(t)] for t in A]);ck('digest',l.entry['evidence_sha']==digest(l.entry['rows']));ck('claim_n',l.entry['n']==32)
        acts=[l.permit(t) for t in range(1,H+1)];ck('authority',acts==[passes and t>288 for t in range(1,H+1)])
        gross=int(sum((800 if x else -1200) for x,on in zip(y,acts) if on));ck('account',gross==(2000*int(y[288:].sum())-1200*(H-288) if passes else 0))
        return dict(coverage=len(oracle),reports=nreports,passes=int(passes),conflicts=int(conflict),net=gross-H-200-l.cost,look=l.spent-34,claim=l.entry['claim_sha'] if l.entry else None)
    for seed in SEEDS:
        _,ys=R['R']['world'](seed); rng=np.random.default_rng(seed+2000000); u=rng.integers(0,100,len(A));v=rng.integers(0,100,len(A));b=int(rng.integers(0,100));flip=rng.integers(0,100,len(A))<2
        for world,y in ys.items():
            if world not in ('good','bad'):continue
            results={}
            for mode in MODES:
                a,bb=masks(mode,u,v,b); q=replay(mode,y,a,bb,flip); results[mode]=q; row=z.setdefault((mode,world),Counter());row.update({k:v for k,v in q.items() if k!='claim'})
            s=results['single']; cp=results['copy']; ck('copy_claim',s['claim']==cp['claim']);ck('copy_cost',s['net']-cp['net']==3200)
            for m in ('independent','complement'):
                ck('coverage_monotone',results[m]['coverage']>=s['coverage']);ck('pass_monotone',results[m]['passes']>=s['passes'])
            ck('full_complement',results['complement']['coverage']==32)
    # Analytic pass probabilities, exact under iid outcomes and specified receipt laws.
    for mode,r in [('single',F(4,5)),('copy',F(4,5)),('independent',F(24,25)),('complement',F(1)),('common_outage',F(1))]:
        probs={}
        for world,p in [('good',F(9,10)),('bad',F(3,10))]:
            pr=R['exact'](p,r);ck('dp_exact',pr==R['oracle'](p,r));pr*=F(4,5) if mode=='common_outage' else 1;probs[world]=pr
        gross=(H-288)*600*(probs['good']-probs['bad'])/2
        cost=3200*(1 if mode=='single' else 2)
        theory[mode]=dict(good_pass=float(probs['good']),bad_pass=float(probs['bad']),increment_vs_hold=float(gross-cost),gross=float(gross))
    for mode in theory:theory[mode]['increment_vs_single']=theory[mode]['increment_vs_hold']-theory['single']['increment_vs_hold'];theory[mode]['max_second_supplier_per_observation']=float((theory[mode]['gross']-theory['single']['gross'])/32) if mode in ('copy','independent','complement') else None
    # Deterministic complement: each provider has 16 wins, union has 32, duplicate not a vote.
    y=np.ones(H,dtype=int); a=np.arange(32)<16; b=~a; f=np.zeros(32,dtype=bool)
    for mode,aa,bb in [('single',a,None),('copy',a,a),('complement',a,b)]:fixtures[mode]=replay(mode,y,aa,bb,f)
    ck('fixture_complement',fixtures['single']['passes']==0 and fixtures['copy']['passes']==0 and fixtures['complement']['passes']==1)
    # Same-time conflict before finalize: regardless of receipt order, never qualifies.
    for order in [('A','B'),('B','A')]:
        l=Ledger();ck('fixture_open',l.open({'A':100,'B':100},0));ck('fixture_advance',l.advance(288))
        for t in A:
            for p in order:ck('fixture_receive',l.receive(p,t,0 if p=='B' and t==A[0] else 1))
        ck('fixture_finalize',l.finalize());ck('fixture_conflict',l.conflict and l.entry is None and l.spent==34 and l.cost==6400 and not l.permit(289))
    summary={f'{m}_{w}':{**{k:(v if k in ('passes','conflicts') else v/len(SEEDS)) for k,v in q.items()},'trials':len(SEEDS)} for (m,w),q in z.items()}
    return dict(passed=sum(c.values()),checks=dict(c)),dict(plan=PLAN,plan_sha=digest(PLAN),summary=summary,theory=theory,fixtures=fixtures)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',default='.');a=p.parse_args();t,e=study();o=Path(a.out);o.mkdir(parents=True,exist_ok=True)
    for n,z in [('tests',t),('examples',e)]:(o/f'Trading_Round140_{n}.json').write_text(json.dumps(z,sort_keys=True,indent=2)+'\n')
    print(t)
