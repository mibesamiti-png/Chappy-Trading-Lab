"""R164: fixed candidate diagnostic, no new selection or trading permissions."""
import argparse, hashlib, json, runpy
from pathlib import Path
from fractions import Fraction as F
from collections import Counter
P=Path(__file__).parent
FILES={'Chappy_Trading_Multi_Horizon_CTRL_Evaluation_v0.1.py':'efb8400db58fd940790b599e10efb7566f4b759bb3b353825399fa85246546a5','Trading_Round163_results.json':'2f0d49898ed23a54c796d09790e83ebcaefa8deadada00858dd6e6e6632a8645'}
ARCH='b8bd4e8d9aacbba177c9d7380310b81ac31b9d245d6d1ceecfb9e495b2b493c6'
PLAN=dict(round=164,candidate=756,fees=[0,20,40],phases={'train':[5,8],'audit':[8,10],'evaluation':[10,19]},archive_sha=ARCH,dependencies=FILES,scope='fixed candidate only, known development; each phase independently starts with 200000 yen; 100000 notional; zero-fee replay separately; no new candidate or permission; rejected outcomes for retrospective accounting only')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def run(path):
 checks=Counter()
 def ck(k,b):
  if not b:raise AssertionError(k)
  checks[k]+=1
 for n,h in FILES.items():ck('dependency',sha(P/n)==h)
 ck('archive',sha(path)==ARCH)
 E=runpy.run_path(str(P/next(iter(FILES))));L=E['L'];M=E['M'];R=E['R'];N=M['N'];i=PLAN['candidate'];p,h,j=E['CANDS'][i];old=json.loads((P/'Trading_Round163_results.json').read_text());ck('fixed_candidate',(p,h,j)==('base',60,212));idx,meta=R['load'](path);ck('normalized',meta['normalized_sha256']==old['normalized_sha']);rows=[]
 for d in range(5,19):
  for s in E['COMMON']:
   for sym in E['SYMS']:
    z,states=L['observe'](idx,sym,d,s);t=E['END'](d,s);lab=M['label'](idx,z,h,E['H']);ck('label_oracle',(lab['reason'],lab['gross'],lab['mature'])==M['reference'](idx,z,h,E['H']));rows.append(dict(key=(d,s,sym),t=t,states=states,labels={h:lab}))
 def stats(q,c):
  g=sum((a*F(l['gross'])*N for k,t,a,l in q),F(0));fee=F(N*c,10000)*len(q);return dict(n=len(q),gross=str(g),fees=str(fee),net=str(g-fee),mean_bps=None if not q else float(g*10000/N/len(q)),wins=sum(a*F(l['gross'])*N>F(N*c,10000) for k,t,a,l in q))
 result={}
 for phase,(lo,hi) in PLAN['phases'].items():
  rr=[r for r in rows if lo<=r['key'][0]<hi and E['action'](r,i)];q=[(r['key'],r['t'],E['action'](r,i),r['labels'][h]) for r in rr];ck('coverage',len(q)==old['coverage'][phase]['all_mature']);ck('maturity',all(L['ready'](l,hi*86400) for k,t,a,l in q));out={}
  for c in PLAN['fees']:
   b=M['settle'](q,c,hi*86400);ck('cash_oracle',{k:v for k,v in b.items() if k!='events'}==M['cash_ref'](q,c,hi*86400));taken=set(b['accepted']);blocked=dict(b['blocked']);a=[x for x in q if x[0] in taken];r=[x for x in q if x[0] in blocked];full,yes,no=stats(q,c),stats(a,c),stats(r,c);ck('partition',len(a)+len(r)==len(q) and not taken.intersection(blocked));ck('net_partition',F(full['net'])==F(yes['net'])+F(no['net']));ck('gross_partition',F(full['gross'])==F(yes['gross'])+F(no['gross']));ck('accounting',b['unresolved']==0 and F(b['net'])==F(yes['net']));ck('fee',F(b['fees'])==F(yes['fees']));ck('nonnegative',all(F(e[3])>=0 for e in b['events']));ck('past_only',all(l['mature']>t for k,t,d,l in q));days={str(day):{'all':stats([x for x in q if x[0][0]==day],c),'accepted':stats([x for x in a if x[0][0]==day],c)} for day in range(lo,hi)}
   out[str(c)]=dict(all_intents=full,accepted=yes,rejected=no,rejection_reasons=dict(Counter(blocked.values())),daily=days,account=b)
   if c in (20,40):
    prev=old['results'][f'{c}:ALL_MULTI'];ck('saved_candidate',prev['candidate']==i)
    if phase in ('train','audit'):ck('saved_score',round(float(F(full['net'])),2)==prev['training_net_yen' if phase=='train' else 'audit_net_yen'])
    if phase=='evaluation' and c==20:ck('saved_account',json.loads(json.dumps(b))==prev['account'])
  result[phase]=out
 ck('archive_unchanged',sha(path)==ARCH)
 return dict(plan=PLAN,direction_table=L['T'][j],results=result,checks=dict(checks),passed=sum(checks.values()),limits=['all-intent sums are not accounts; rejected results are hindsight only','fees=0 alters permitted positions and is a separate counterfactual; fixed accepted gross is the direct cost comparison','phase accounts reset independently; 40bps audit rejects candidate in actual R163','no causal attribution of future regime or portfolio optimization; no unknown data'])
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('archive',type=Path);a.add_argument('--plan-only',action='store_true');a.add_argument('--output',required=True);q=a.parse_args();z=PLAN if q.plan_only else run(q.archive)
 with open(q.output,'x') as f:json.dump(z,f,sort_keys=True,indent=2);f.write('\n')
