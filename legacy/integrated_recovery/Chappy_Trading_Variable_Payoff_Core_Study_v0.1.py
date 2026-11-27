"""R149: offline variable-payoff policy-selection adapter. No market prices/orders."""
import hashlib,json,runpy
from pathlib import Path
from fractions import Fraction as F
from collections import Counter
ROOT=Path(__file__).parent
DEPS={'OHLCV_Input_Study':'58542626c20308885b0257483ff955db6838c431280ef52aafea1f8d2d103d12','Selective_Hypothesis_Study':'da45cbba59a269bc24379e0fffa7060562fdd1e0ed5e3c0681552cecb8dd1854','Expected_Value_Study':'d2bfc1892be0a1893ddc9e86956c8d9654834728782b08b679dbf71e6ad2fa95'}
def load(k):
 p=ROOT/f'Chappy_Trading_{k}_v0.1.py'
 if hashlib.sha256(p.read_bytes()).hexdigest()!=DEPS[k]:raise ValueError(k+' hash')
 return runpy.run_path(str(p))
R=load('OHLCV_Input_Study'); S=load('Selective_Hypothesis_Study'); E=load('Expected_Value_Study'); T=[tuple(map(int,t)) for t in S['T']]
MODES=('HOLD','CHASE','FADE','HIT','PAY','PAY_AUDIT')
PLAN=dict(synthetic_only=True,seeds=list(range(149000,149016)),cases=R['PLAN']['cases'],costs=[20,40],modes=MODES,train_day=5,audit_day=6,test_day=7,selection='HIT signed hit margin, PAY sum signed gross less cost; WAIT first tie',audit='single descriptive positive net on all selected feature-ready audit observations, all matured before test; no statistical qualification',notional=100000,dependencies=DEPS,limits='8 scheduled opportunities per day per seed; shadow fixed notional, no portfolio or fill model')
def records(rows):
 idx=R['validate'](rows);cut=R['end'](8,0)
 return [(z,R['label'](z,idx,cut)) for d in (5,6,7) for s in R['PLAN']['signals'] for sym in R['PLAN']['symbols'] for z in [R['freeze'](rows,d,s,sym)]]
def available(rs,day,cut):
 return [(d['state'],F(l['gross'])*10000) for d,l in rs if d['day']==day and d['state'] is not None and l['mature'] is not None and l['mature']<cut]
def score(samples,t,c,hit):
 return sum((a*((v>0)-(v<0)) if hit else a*v-c) for x,v in samples if (a:=t[x]))
def select(samples,c,hit):
 # aggregate by state, exact rational arithmetic
 n=[0]*8; v=[F(0)]*8
 for x,y in samples:n[x]+=1;v[x]+=((y>0)-(y<0)) if hit else y
 scores=[sum(a*v[x]-(0 if hit else abs(a)*c*n[x]) for x,a in enumerate(t)) for t in T]
 return max(range(len(T)),key=scores.__getitem__)
def audit(rs,j,c,cut):
 selected=[(d,l) for d,l in rs if d['day']==6 and d['state'] is not None and T[j][d['state']]]
 vals=[T[j][d['state']]*F(l['gross'])*10000 for d,l in selected if l['mature'] is not None and l['mature']<cut]
 net=sum(v-c for v in vals);complete=len(vals)==len(selected)
 # R74 diagnostic is descriptive; it can be undefined even when point sum positive.
 diag=E['estimate'](vals,c)
 return dict(selected=len(selected),mature=len(vals),net_bps=str(net),pass_point=bool(selected and complete and net>0),r74_estimate=diag)
def actions(rs,c):
 samples=available(rs,5,R['end'](6,0)); hit=select(samples,c,True); pay=select(samples,c,False); a=audit(rs,pay,c,R['end'](7,0)); out={m:[] for m in MODES}
 for d,l in rs:
  if d['day']!=7:continue
  x=d['state']; k=(d['symbol'],d['day'],d['slot']); mom=d['momentum'] if x is not None else 0
  aa=[0,mom,-mom,T[hit][x] if x is not None else 0,T[pay][x] if x is not None else 0,T[pay][x] if x is not None and a['pass_point'] else 0]
  for m,v in zip(MODES,aa):out[m].append((k,v))
 return dict(hit=hit,pay=pay,train_n=len(samples),audit=a,actions=out)
def evaluate(rs,acts,c):
 idx={(d['symbol'],d['day'],d['slot']):(d,l) for d,l in rs}; out={}
 for m,aa in acts.items():
  n=unknown=w=flat=0; gross=F(0)
  for k,a in aa:
   if not a:continue
   n+=1;d,l=idx[k]
   if l['gross'] is None:unknown+=1;continue
   g=a*F(l['gross'])*10000;gross+=g;w+=g>0;flat+=g==0
  net=10*(gross-c*(n-unknown));out[m]=dict(intended=n,resolved=n-unknown,unknown=unknown,wins=w,flat=flat,net=str(net),all_net=None if unknown else str(net))
 return out

def study():
 checks=Counter(); report={}
 def ck(k,v):
  if not v:raise AssertionError(k)
  checks[k]+=1
 for case in PLAN['cases']:
  for c in PLAN['costs']:
   counts=Counter(); totals={m:Counter() for m in MODES}; nets={m:F(0) for m in MODES}
   for seed in PLAN['seeds']:
    rs=records(R['fixture'](seed,case)); z=actions(rs,c); ev=evaluate(rs,z['actions'],c)
    samples=available(rs,5,R['end'](6,0));counts['train_n']+=len(samples);counts['different_candidate']+=z['hit']!=z['pay'];counts['audit_pass']+=z['audit']['pass_point'];counts['audit_selected']+=z['audit']['selected'];counts['audit_mature']+=z['audit']['mature']
    for hit,k in [(True,'hit'),(False,'pay')]:
     scores=[score(samples,t,c,hit) for t in T];ck('candidate_oracle',z[k]==scores.index(max(scores)))
    j=z['pay']; ar=[(d,l) for d,l in rs if d['day']==6 and d['state'] is not None and T[j][d['state']]]; ok=bool(ar) and all(l['mature'] is not None and l['mature']<R['end'](7,0) for d,l in ar)
    ck('audit_oracle',z['audit']['pass_point']==(ok and sum(T[j][d['state']]*F(l['gross'])*10000-c for d,l in ar)>0))
    mask=[(d,dict(l,gross=None,mature=None,direction=None)) if d['day']==7 else (d,l) for d,l in rs];ck('evaluation_label_blind',actions(mask,c)==z)
    mask=[(d,dict(l,gross=None,mature=None,direction=None)) if d['day']>=6 or (l['mature'] is not None and l['mature']>=R['end'](6,0)) else (d,l) for d,l in rs]; zz=actions(mask,c);ck('training_label_blind',(zz['hit'],zz['pay'])==(z['hit'],z['pay']))
    idx={(d['symbol'],d['day'],d['slot']):(d,l) for d,l in rs}
    for m,aa in z['actions'].items():
     vals=[10*(a*F(idx[k][1]['gross'])*10000-c) for k,a in aa if a and idx[k][1]['gross'] is not None]; n=sum(bool(a) for k,a in aa);v=ev[m];ck('accounting',F(v['net'])==sum(vals));ck('unknown_total',v['all_net']==(None if n!=len(vals) else str(sum(vals))));ck('coverage',v['resolved']+v['unknown']==n);ck('feature_authority',all(not a or idx[k][0]['state'] is not None for k,a in aa));ck('audit_authority',m!='PAY_AUDIT' or z['audit']['pass_point'] or n==0)
     totals[m].update({k:v[k] for k in ('intended','resolved','unknown','wins','flat')});nets[m]+=F(v['net'])
   report[f'{case}:{c}']=dict(counts=dict(counts),modes={m:dict(totals[m],observed_net_yen=round(float(nets[m]),2),all_selected_net_yen=None if totals[m]['unknown'] else round(float(nets[m]),2)) for m in MODES})
 # Magnitude reversal: three small wins and one big loss. Fixed state only.
 a=[(0,F(30))]*3+[(0,F(-300))]; h=select(a,20,True);p=select(a,20,False);ck('magnitude_direction',T[h][0]==1 and T[p][0]==-1);ck('magnitude_net',score(a,T[h],20,False)==-290 and score(a,T[p],20,False)==130)
 flat=[(0,F(0))]*4;ck('flat_wait',select(flat,20,False)==0 and select(flat,20,True)==0);ck('empty_wait',select([],20,False)==0)
 return dict(plan=PLAN,plan_sha=R['digest'](PLAN),checks=dict(checks),passed=sum(checks.values()),report=report,dedicated=dict(hit_net_yen=-2900,pay_net_yen=1300),limits=['independent time slices, not proven statistically independent; point audit not certification','same days across synthetic symbols, tiny samples, no statistical alpha guarantee','no live prices, real fill, capital, observation fees or refresh; shadow fixed notional','unknown evaluation selected totals remain unknown; observed net is complete-case only'])
if __name__=='__main__':print(json.dumps(study(),sort_keys=True,indent=2))
