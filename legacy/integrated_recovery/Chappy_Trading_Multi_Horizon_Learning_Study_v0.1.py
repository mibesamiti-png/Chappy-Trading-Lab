"""R162: fixed panels and horizons, synthetic only."""
import argparse,hashlib,json,runpy,math
from pathlib import Path
from collections import Counter
from fractions import Fraction as F
P=Path(__file__).parent
DEP='7aa917e673e3d289c58d2da30c09380d67d70d25e1d3b541b86666c008c0654b'
p=P/'Chappy_Trading_Multi_Horizon_Adapter_v0.1.py'
if hashlib.sha256(p.read_bytes()).hexdigest()!=DEP:raise ValueError('dependency')
M=runpy.run_path(str(p));A=M['A'];R=M['R'];T=tuple(tuple(map(int,t)) for t in M['C']['T']);HS=M['HS'];END=M['END'];SYMS=M['SYMS'];COMMON=M['COMMON'];H=8*86400
PANELS=('base','context','hybrid');MODES=('HOLD','BASE10','BASE_MULTI','ALL_MULTI')
PLAN=dict(round=162,dependency=DEP,days=8,train=5,audit=6,evaluation=7,seeds=list(range(162000,162004)),cases=['complete','delay','missing','zero'],fees=[20,40],panels={'base':'R157 state','context':'RSI rebound, peer condition, positive relative','hybrid':'positive momentum, RSI rebound, peer condition'},horizons=HS,schedule=COMMON,candidates='one WAIT then existing nonzero direction tables, panel order then horizon order then table id',cohort='same feature-ready opportunities all panels; training all three labels strictly matured before audit; audit selected labels all mature before evaluation',audit_rule='single frozen candidate, nonempty complete and positive net; no retry',capital='R161 settlement unchanged; fixed notional, full collateral, symbol lock; no observation fee',scope='synthetic only; no archive access, no statistical guarantee')
CANDS=[(None,None,0)]+[(p,h,j) for p in PANELS for h in HS for j in range(1,len(T))]
IDS={m:[i for i,(p,h,j) in enumerate(CANDS) if i==0 or m=='ALL_MULTI' or (p=='base' and (m=='BASE_MULTI' or m=='BASE10' and h==10))] if m!='HOLD' else [0] for m in MODES}
def observe(idx,sym,d,s):
 t=END(d,s);pre={k:v for k,v in idx.items() if v['received']<=t and END(k[1],k[2])<=t};z=R['freeze'](pre,sym,d,s) if (sym,d,s) in pre else dict(symbol=sym,day=d,slot=s,decision=t,state=None,momentum=0)
 a=A['observe'](idx,sym,d,s,t);states=None
 if z['state'] is not None and a['rebound'] is not None and a['peer_condition'] is not None and a['relative'] is not None:
  b=int(a['rebound']);q=int(a['peer_condition']);r=int(F(a['relative'])>0);states=dict(base=z['state'],context=4*b+2*q+r,hybrid=4*int(z['momentum']>0)+2*b+q)
 return z,states
def records(idx,ck):
 rows=[]
 for d in range(5,8):
  for s in COMMON:
   for sym in SYMS:
    z,states=observe(idx,sym,d,s);t=z['decision'];pre={k:v for k,v in idx.items() if v['received']<=t and END(k[1],k[2])<=t};ck('feature_prefix',observe(pre,sym,d,s)==(z,states))
    labs={h:M['label'](idx,z,h,H) for h in HS}
    for h,l in labs.items():ck('label_oracle',(l['reason'],l['gross'],l['mature'])==M['reference'](idx,z,h,H))
    rows.append(dict(key=(d,s,sym),t=t,states=states,labels=labs))
 return rows
def ready(l,t):return l['mature'] is not None and l['mature']<t
def action(r,i):
 p,h,j=CANDS[i];return 0 if i==0 or r['states'] is None else T[j][r['states'][p]]
def training(rows):return [r for r in rows if r['key'][0]==5 and r['states'] is not None and all(ready(l,6*86400) for l in r['labels'].values())]
def scores(rows,c):
 tr=training(rows);out=[F(0)]
 for p in PANELS:
  for h in HS:
   n=[0]*8;v=[F(0)]*8
   for r in tr:
    x=r['states'][p];n[x]+=1;v[x]+=F(r['labels'][h]['gross'])*10000
   den=math.lcm(*(x.denominator for x in v));iv=[int(x*den) for x in v];ic=[c*k*den for k in n]
   out.extend(F(sum(a*iv[x]-abs(a)*ic[x] for x,a in enumerate(t)),den) for t in T[1:])
 return out
def choose(rows,c,m):
 sc=scores(rows,c);return max(IDS[m],key=sc.__getitem__)
def ref_scores(rows,c):
 tr=training(rows);out=[F(0)]
 for p in PANELS:
  for h in HS:
   v={x:[F(r['labels'][h]['gross'])*10000 for r in tr if r['states'][p]==x] for x in range(8)}
   val=[sum(v[x],F(0)) for x in range(8)];pos=[val[x]-c*len(v[x]) for x in range(8)];neg=[-val[x]-c*len(v[x]) for x in range(8)];den=math.lcm(*(q.denominator for q in pos+neg));vv=[{1:int(pos[x]*den),-1:int(neg[x]*den),0:0} for x in range(8)]
   out.extend(F(sum(vv[x][a] for x,a in enumerate(t)),den) for t in T[1:])
 return out
def decide(rows,c,m,sc=None):
 i=choose(rows,c,m) if sc is None else max(IDS[m],key=sc.__getitem__);p,h,j=CANDS[i];audit=[r for r in rows if r['key'][0]==6 and action(r,i)];known=[r for r in audit if ready(r['labels'][h],7*86400)];net=sum((action(r,i)*F(r['labels'][h]['gross'])*10000-c for r in known),F(0));ok=bool(audit) and len(audit)==len(known) and net>0
 orders=[(r['key'],r['t'],action(r,i),r['labels'][h]) for r in rows if r['key'][0]==7 and ok and action(r,i)]
 return dict(candidate=i,selected=len(audit),mature=len(known),audit_net=str(net),admit=ok,orders=orders)
def identity(z):return {k:v for k,v in z.items() if k!='orders'}|{'intents':[x[:3] for x in z['orders']]}
def run():
 checks=Counter();cases=[];results={}
 def ck(k,b):
  if not b:raise AssertionError(k)
  checks[k]+=1
 ck('pool_size',len(T)==273 and not any(T[0]) and len(CANDS)==2449 and len(set(CANDS))==len(CANDS));ck('wait_tie',all(choose([],20,m)==0 for m in MODES))
 for case in PLAN['cases']:
  for seed in PLAN['seeds']:
   rows=records(M['fixture'](seed,case),ck);cover=dict(train_common=len(training(rows)),audit_features=sum(r['states'] is not None for r in rows if r['key'][0]==6),eval_features=sum(r['states'] is not None for r in rows if r['key'][0]==7))
   for c in PLAN['fees']:
    sc=scores(rows,c);oracle=ref_scores(rows,c);ck('score_oracle',sc==oracle)
    blank=lambda r:dict(r,labels={h:dict(l,gross=None,mature=None) for h,l in r['labels'].items()})
    evmask=[blank(r) if r['key'][0]==7 else r for r in rows];trmask=[blank(r) if r['key'][0]>=6 else r for r in rows];evsc=scores(evmask,c);trsc=scores(trmask,c)
    for m in MODES:
     z=decide(rows,c,m,sc);i=z['candidate'];p,h,j=CANDS[i];ck('selection_oracle',i==max(IDS[m],key=oracle.__getitem__));ar=[r for r in rows if r['key'][0]==6 and action(r,i)];ck('audit_oracle',z['admit']==(bool(ar) and all(ready(r['labels'][h],7*86400) for r in ar) and sum((action(r,i)*F(r['labels'][h]['gross'])*10000-c for r in ar),F(0))>0))
     blank=lambda r:dict(r,labels={h:dict(l,gross=None,mature=None) for h,l in r['labels'].items()})
     ck('eval_blind',identity(decide(evmask,c,m,evsc))==identity(z));ck('train_blind',max(IDS[m],key=trsc.__getitem__)==i)
     orders=z['orders'];a=M['settle'](orders,c,H);ck('cash_oracle',{k:v for k,v in a.items() if k!='events'}==M['cash_ref'](orders,c,H));ck('accounting',F(a['cash'])+a['reserved']==M['INITIAL']+F(a['gross'])-F(a['fees']));ck('one_time',len({q[0] for q in orders})==len(orders) and all(q[3]['horizon']==h for q in orders));ck('authority',z['admit'] or not orders);ck('partition',len(orders)==len(a['accepted'])+len(a['blocked']));ck('nonnegative',all(F(x[3])>=0 for x in a['events']))
     cases.append(dict(case=case,seed=seed,fee=c,mode=m,coverage=cover,panel=p,horizon=h,table=j,admit=z['admit'],audit_count=z['selected'],intents=len(orders),accepted=len(a['accepted']),blocked=len(a['blocked']),unresolved=a['unresolved'],net=a['net']))
 rr=[]
 for d in (5,6,7):
  for x in (0,7):
   for q in range(2):
    k=(d,q*2+int(x==7),SYMS[0]);t=d*86400+100+(q*2+int(x==7))*3600;rr.append(dict(key=k,t=t,states=dict(base=0,context=x,hybrid=0),labels={h:dict(horizon=h,gross=str(F((1 if x==7 else -1)*80,10000) if h==60 else F(0)),mature=t+300+h*60) for h in HS}))
 a=decide(rr,20,'ALL_MULTI');ck('dedicated_context_horizon',a['admit'] and CANDS[a['candidate']][:2]==('context',60) and len(a['orders'])==4);ck('dedicated_base_wait',choose(rr,20,'BASE_MULTI')==0);ac=M['settle'](a['orders'],20,H);ck('dedicated_positive_cash',F(ac['net'])==1200 and len(ac['accepted'])==2 and ac['unresolved']==0);ck('dedicated_cash_oracle',{k:v for k,v in ac.items() if k!='events'}==M['cash_ref'](a['orders'],20,H))
 missing=[dict(r,labels=dict(r['labels'])) for r in rr];r=next(r for r in missing if r['key'][0]==6);r['labels'][60]=dict(r['labels'][60],gross=None,mature=None);ck('dedicated_audit_missing',not decide(missing,20,'ALL_MULTI')['admit'])
 for case in PLAN['cases']:
  for c in PLAN['fees']:
   for m in MODES:
    q=[x for x in cases if (x['case'],x['fee'],x['mode'])==(case,c,m)];nets=[F(x['net']) for x in q if x['net'] is not None];results[f'{case}:{c}:{m}']=dict(admit=sum(x['admit'] for x in q),accepted=sum(x['accepted'] for x in q),unresolved=sum(x['unresolved'] for x in q),mean_net=None if len(nets)!=len(q) else round(float(sum(nets)/len(nets)),2),selection=dict(Counter(f"{x['panel']}:{x['horizon']}" for x in q)))
 return dict(plan=PLAN,candidates=len(CANDS),checks=dict(checks),passed=sum(checks.values()),summary=results,cases=cases,dedicated=dict(candidate=CANDS[a['candidate']],settled=ac['accepted'],net=ac['net']),limits=['synthetic only; small sample','matched cohort may discard valid short-horizon observations','point audit not statistical; training ignores capital contention','no refresh integration, live execution or real data'])
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--plan-only',action='store_true');p.add_argument('--output',required=True);a=p.parse_args();z=PLAN if a.plan_only else run()
 with open(a.output,'x') as f:json.dump(z,f,indent=2,sort_keys=True);f.write('\n')
