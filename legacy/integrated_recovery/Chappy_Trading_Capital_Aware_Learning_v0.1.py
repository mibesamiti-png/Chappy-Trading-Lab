"""R165 synthetic-only capital-aware selection; reuse R162 and R161."""
import argparse,hashlib,json,runpy
from pathlib import Path
from fractions import Fraction as F
from collections import Counter
P=Path(__file__).parent
p=P/'Chappy_Trading_Multi_Horizon_Learning_Study_v0.1.py'
DEP='4e92b34c34ddbda5fca8bfb77efc43b653f50944e2f16e1e70755d772f57eb49'
if hashlib.sha256(p.read_bytes()).hexdigest()!=DEP:raise ValueError('dependency')
L=runpy.run_path(str(p));M=L['M'];C=L['CANDS'];IDS=L['IDS'];HS=L['HS'];H=L['H'];SYMS=L['SYMS'];action=L['action'];ready=L['ready']
PLAN=dict(round=165,dependency=DEP,scope='synthetic only',seeds=[165000,165001],cases=['complete','delay','missing','zero'],fees=[20,40],modes=L['MODES'],methods=['INTENT','CAPITAL'],candidates=len(C),train=5,audit=6,evaluation=7,initial=M['INITIAL'],notional=M['N'],cohort='R162 common mature training and strictly mature all audit intents',capital='R161 unchanged settlement; independent initial capital each phase',selection='maximum account net, WAIT first, frozen candidate, no retry',limits='point audit, no statistical guarantee or refresh')
def orders(rows,i):
 h=C[i][1];return [(r['key'],r['t'],action(r,i),r['labels'][h]) for r in rows if action(r,i)]
def masked(q,t):return [(k,d,a,l if ready(l,t) else dict(l,gross=None,mature=None)) for k,d,a,l in q]
def account(q,c,t,ck):
 z=M['settle'](q,c,t);ck('cash_oracle',{k:v for k,v in z.items() if k!='events'}==M['cash_ref'](q,c,t));ck('accounting',F(z['cash'])+z['reserved']==M['INITIAL']+F(z['gross'])-F(z['fees']));return z
def scores(rows,c,ck):
 tr=L['training'](rows);cache={};out=[]
 for i in range(len(C)):
  q=orders(tr,i);k=tuple((k,t,a,l['horizon'],l['gross'],l['mature']) for k,t,a,l in q)
  if k not in cache:
   z=account(q,c,6*86400-1,ck);ck('training_complete',z['net'] is not None);cache[k]=F(z['net'])
  out.append(cache[k])
 return out,len(cache)
def decide(rows,c,m,method,sc,ck):
 i=max(IDS[m],key=sc.__getitem__);q=orders([r for r in rows if r['key'][0]==6],i);known=all(ready(x[3],7*86400) for x in q)
 z=account(masked(q,7*86400),c,7*86400-1,ck);net=sum((a*F(l['gross'])*M['N']-F(M['N']*c,10000) for k,t,a,l in q if ready(l,7*86400)),F(0))
 ok=bool(q) and known and (net>0 if method=='INTENT' else z['net'] is not None and F(z['net'])>0)
 return i,ok,z,net,orders([r for r in rows if r['key'][0]==7],i) if ok else []
def run():
 checks=Counter();cases=[]
 def ck(k,b):
  if not b:raise AssertionError(k)
  checks[k]+=1
 def test(rows,c,case,seed):
  cap,n=scores(rows,c,ck);intent=L['scores'](rows,c);ck('pool',len(cap)==len(intent)==2449 and cap[0]==intent[0]==0)
  blank=lambda r:dict(r,labels={h:dict(l,gross=None,mature=None) for h,l in r['labels'].items()})
  trmask=[blank(r) if r['key'][0]>=6 else r for r in rows];evmask=[blank(r) if r['key'][0]==7 else r for r in rows]
  # Exact training cohort identity implies candidate orders and scores unchanged.
  ck('training_blind',L['training'](trmask)==L['training'](rows) and L['scores'](trmask,c)==intent)
  for method,sc in [('INTENT',intent),('CAPITAL',cap)]:
   for m in L['MODES']:
    i,ok,audit,net,ev=decide(rows,c,m,method,sc,ck);v=decide(evmask,c,m,method,sc,ck);ck('eval_blind',(i,ok,[x[:3] for x in ev])==(v[0],v[1],[x[:3] for x in v[-1]]));ck('wait_priority',sc[i]>0 or i==0)
    if method=='INTENT':
     old=L['decide'](rows,c,m,sc);ck('legacy_identity',(i,ok,ev)==(old['candidate'],old['admit'],old['orders']))
    z=account(ev,c,H,ck);ck('partition',len(ev)==len(z['accepted'])+len(z['blocked']));ck('authority',ok or not ev)
    for cut in [7*86400+10*3600,7*86400+14*3600]:
     pre=M['settle'](masked([x for x in ev if x[1]<cut],cut),c,cut-1);ck('cash_prefix',[x for x in z['events'] if x[2]<cut]==[x for x in pre['events'] if x[2]<cut])
    cases.append(dict(case=case,seed=seed,fee=c,mode=m,method=method,candidate=i,definition=C[i],train_n=len(L['training'](rows)),unique_streams=n,training_capital=str(cap[i]),audit_intent_net=str(net),audit_capital_net=audit['net'],admit=ok,intents=len(ev),accepted=len(z['accepted']),blocked=len(z['blocked']),unresolved=z['unresolved'],net=z['net']))
 for case in PLAN['cases']:
  for seed in PLAN['seeds']:
   rows=L['records'](M['fixture'](seed,case),ck)
   for c in PLAN['fees']:test(rows,c,case,seed)
 rows=[]
 for d in (5,6,7):
  for j,g in enumerate((F(-1,100),F(2,100))):
   t=d*86400+36000;rows.append(dict(key=(d,3,SYMS[j]),t=t,states=dict(base=7*j,context=7*j,hybrid=7*j),labels={h:dict(horizon=h,gross=str(g),mature=t+300+h*60) for h in HS}))
 test(rows,20,'capital_conflict',0);sel=[x for x in cases if x['case']=='capital_conflict' and x['mode']=='ALL_MULTI'];a,b=sel
 ck('conflict_improvement',a['method']=='INTENT' and b['method']=='CAPITAL' and F(a['net'])==800 and F(b['net'])==1800 and a['candidate']!=b['candidate'])
 sc,_=scores(rows,20,ck)
 for label,change in [('audit_no_retry',lambda l:dict(l,gross=str(-F(l['gross'])))),('audit_boundary',lambda l:dict(l,mature=7*86400))]:
  bad=[dict(r,labels={h:change(l) for h,l in r['labels'].items()}) if r['key'][0]==6 and r['key'][2]==SYMS[1] else r for r in rows];i,ok,z,net,ev=decide(bad,20,'ALL_MULTI','CAPITAL',sc,ck);ck(label,i==b['candidate'] and not ok and not ev)
 return dict(plan=PLAN,checks=dict(checks),passed=sum(checks.values()),cases=cases,dedicated=sel)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--plan-only',action='store_true');p.add_argument('--output',required=True);a=p.parse_args();r=PLAN if a.plan_only else run()
 with open(a.output,'x') as f:json.dump(r,f,indent=2,sort_keys=True);f.write('\n')
