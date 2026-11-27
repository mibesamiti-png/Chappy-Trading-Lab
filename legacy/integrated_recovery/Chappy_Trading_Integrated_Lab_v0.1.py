"""R169 offline integrated entrypoint; accepts fixed demo or pinned known archive only."""
import argparse, hashlib, json, runpy, tempfile
from pathlib import Path
from collections import Counter
from fractions import Fraction as F
P=Path(__file__).resolve().parent
PIN='7f60c306ccfc648570e6cdce4914fb70c88f6a1c3c24b16c7648451e11faedf9'
ARCHIVE='b8bd4e8d9aacbba177c9d7380310b81ac31b9d245d6d1ceecfb9e495b2b493c6'
NORMALIZED='fcc5dd6f7a56935d225d05953c53b355dd86faca24df4aebad72011e001269a9'
def sha(b):return hashlib.sha256(b).hexdigest()
source=P/'Chappy_Trading_Data_Safety_Adapter_v0.1.py'
if sha(source.read_bytes())!=PIN:raise ValueError('R168 dependency mismatch')
S=runpy.run_path(str(source)); R=S['R']; L=S['L']; M=S['M']; END=S['END']; H=S['H']; D=S['D']
PLAN=dict(round=169,scope='offline research only; fixed synthetic demos or explicitly authorized known development archive; no live orders or new data',adapter_sha=PIN,archive_sha=ARCHIVE,normalized_sha=NORMALIZED,dates=list(L['R']['days']),symbols=list(S['SYMS']),schedule=list(S['COMMON']),horizons=list(S['HS']),split=dict(prep=[0,5],train=[5,8],audit=[8,10],evaluation=[10,19]),fees=[20,40],modes=['FROZEN','STOP','REFRESH'],candidate_count=len(R['C']),capital=200000,notional=100000,clock='ideal bar end, strict label maturity',authority='terminal DATA stop; no automatic data recovery',output='exclusive create, full retrospective ledger, no executable orders')
def known(path):
 # Snapshot the exact approved archive before parsing; never parse unapproved bytes.
 with open(path,'rb') as f:raw=f.read(1_000_001)
 if sha(raw)!=ARCHIVE:raise ValueError('unapproved archive; only pinned known CTRL permitted')
 with tempfile.TemporaryDirectory() as tmp:
  p=Path(tmp)/'known.zip';p.write_bytes(raw);idx,meta=L['R']['load'](p)
 if meta['normalized_sha256']!=NORMALIZED or list(meta['dates'])!=PLAN['dates']:raise ValueError('provenance mismatch')
 return idx,dict(kind='known_development',archive_sha256=ARCHIVE,normalized_sha256=NORMALIZED,dates=PLAN['dates'],ideal_receipt=True)
def evaluate(idx,meta):
 checks=Counter();rows=S['rows_from'](idx);cases=[]
 def ck(k,v):
  if not v:raise ValueError('verification failed: '+k)
  checks[k]+=1
 for r in rows:
  d,s,sym=r['key'];t=r['t'];ck('scheduled_clock',t==END(d,s));z,states=L['observe'](idx,sym,d,s);ck('feature_match',states==r['states'])
  for h,l in r['labels'].items():ck('label_oracle',(l['reason'],l['gross'],l['mature'])==M['reference'](idx,z,h,H));ck('strict_maturity',l['mature'] is None or l['mature']>t and not R['ready'](l,l['mature']))
 for c in PLAN['fees']:
  for mode in PLAN['modes']:
   z=S['simulate'](rows,c,mode,ck,True);a=z['account'];q=z['orders'];ck('partition',len(q)==len(a['accepted'])+len(a['blocked']));ck('independent_final_account',{k:v for k,v in a.items() if k!='events'}==M['cash_ref'](q,c,H-1));ck('single_order',len({x[0] for x in q})==len(q));ck('unresolved_consistency',(a['net'] is None)==bool(a['unresolved']));ck('data_authority',z['data_stop'] is None or all(t<z['data_stop'] for _,t,_,_ in q));cases.append(dict(fee=c,mode=mode,**z))
 return dict(status='OFFLINE_RESEARCH_ONLY',plan=PLAN,provenance=meta,coverage=dict(bars=len(idx),opportunities=len(rows),features=sum(r['states'] is not None for r in rows)),checks=dict(checks),passed=sum(checks.values()),cases=cases,limits=['known data is development only; no independent profitability claim','ideal receipt, fixed collateral, no actual fills, lots or borrow','point audit, shadow-intent economic monitor','offline structural validation, no live feed or recovery','not a frozen package or full historical regression'])
def demo(case):return evaluate(S['fixture'](case),dict(kind='synthetic',fixture=case,ideal_receipt=True))
def main():
 p=argparse.ArgumentParser(description=__doc__);g=p.add_mutually_exclusive_group(required=True);g.add_argument('--demo',choices=['stable','reversal','missing']);g.add_argument('--known-archive',type=Path);g.add_argument('--plan-only',action='store_true');p.add_argument('--output',required=True,type=Path);a=p.parse_args()
 if a.output.exists() or a.output.is_symlink():p.error('output exists; overwrite forbidden')
 try:
  if a.plan_only:z=PLAN
  elif a.demo:z=demo(a.demo)
  else:z=evaluate(*known(a.known_archive))
  data=json.dumps(z,sort_keys=True,indent=2,allow_nan=False)+'\n'
  with a.output.open('x',encoding='utf-8',newline='\n') as f:f.write(data)
 except (ValueError,OSError) as e:p.error(str(e))
if __name__=='__main__':main()
