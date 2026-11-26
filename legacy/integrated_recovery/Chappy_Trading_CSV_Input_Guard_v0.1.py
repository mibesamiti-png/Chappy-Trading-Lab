"""R152: normalized CSV gateway, known development only. No network/order API.
Not a broker CSV converter; slots and logical reception delays must be normalized externally.
"""
import argparse,csv,hashlib,io,json,runpy,re,tempfile
from datetime import date,timedelta
from pathlib import Path
from collections import Counter
from fractions import Fraction
ROOT=Path(__file__).parent
P=ROOT/'Chappy_Trading_OHLCV_Refresh_Study_v0.1.py'
SHA='dd25cb1de68a2db67cfb9455d74ab7389561967fdc220eb7c912f35b868cf4d3'
if hashlib.sha256(P.read_bytes()).hexdigest()!=SHA:raise ValueError('dependency hash')
L=runpy.run_path(str(P)); R=L['R']; B=L['B']; end=L['end']
CUTOFF='2026-11-26'; FIRST='2026-10-26'; LAST='2026-11-24'; SYMS=['6501','6758','7203','7267','8058','8306']; SLOTS=[s for a,b in R['PLAN']['segments'] for s in range(a,b+1)]
FIELDS=['date','symbol','slot','open','high','low','close','volume','logical_delay_seconds']
PLAN=dict(dependency=SHA,cutoff=CUTOFF,known_range=[FIRST,LAST],known_count=19,known_symbols=SYMS,slots=SLOTS,price='positive decimal yen, <=3 decimals; integer milliyen internally',reception='normalized logical delay, not original wall-clock arrival; within logical day',synthetic_seeds=[152000,152001],cases=['stable','reversal','null','missing'],modes=L['PLAN']['modes'],costs=L['PLAN']['costs'])
def fail(msg):raise ValueError(msg)
def iso(x):
 if not isinstance(x,str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}',x):fail('date format')
 try:d=date.fromisoformat(x)
 except ValueError:fail('date format')
 if x>=CUTOFF:fail('protected or later date')
 return d

def preflight(m):
 if not isinstance(m,dict) or set(m)!={'purpose','dates','symbols','sha256','source','clock'}:fail('manifest fields')
 if m['purpose'] not in ('synthetic','known_development'):fail('purpose')
 if m['clock']!='normalized_logical_v1':fail('clock')
 if not isinstance(m['source'],str) or not m['source'].strip():fail('source')
 if not isinstance(m['sha256'],str) or not re.fullmatch('[0-9a-f]{64}',m['sha256']):fail('sha256')
 ds=m['dates'];sy=m['symbols']
 if not isinstance(ds,list) or not ds:fail('dates')
 for d in ds:iso(d)
 if ds!=sorted(set(ds)):fail('date order or duplicate')
 if m['purpose']=='known_development':
  if len(ds)!=19 or ds[0]!=FIRST or ds[-1]!=LAST or any(not FIRST<=d<=LAST or iso(d).weekday()>=5 or d=='2026-11-06' for d in ds) or sy!=SYMS:fail('known cohort mismatch')
 else:
  if len(ds)!=32 or sy!=['X','Y'] or any(d>='2026-01-01' for d in ds):fail('synthetic cohort mismatch')
 return {d:i for i,d in enumerate(ds)}
def uint(x):
 if not re.fullmatch(r'0|[1-9][0-9]*',x):fail('unsigned integer')
 return int(x)
def price(x):
 if not re.fullmatch(r'(?:0|[1-9][0-9]*)(?:\.[0-9]{1,3})?',x):fail('price decimal')
 v=Fraction(x)*1000
 if v<=0 or v.denominator!=1:fail('price scale')
 return int(v)
def load(path,m):
 days=preflight(m)  # before opening the CSV
 raw=Path(path).read_bytes()
 if hashlib.sha256(raw).hexdigest()!=m['sha256']:fail('hash mismatch')
 reader=csv.reader(io.StringIO(raw.decode('utf-8-sig'),newline=''),strict=True)
 if next(reader,None)!=FIELDS:fail('header')
 records=list(reader)
 if not records:fail('empty input')
 seen=set(); meta=[]
 # First validate dates, identities, and slot boundaries of ALL rows, before parsing any price.
 for a in records:
  if len(a)!=len(FIELDS):fail('column count')
  iso(a[0]); s=uint(a[2]); k=(a[0],a[1],s)
  if a[0] not in days or a[1] not in m['symbols'] or s not in SLOTS:fail('undeclared identity or slot')
  if k in seen:fail('duplicate bar')
  seen.add(k);meta.append((days[a[0]],a[1],s))
 rows=[]
 for a,(d,sym,s) in zip(records,meta):
  o,h,l,c=map(price,a[3:7]);v=uint(a[7]);delay=uint(a[8]);t=end(d,s)+delay
  if t>=(d+1)*86400:fail('cross-day logical receipt unsupported')
  rows.append(B['row'](d,s,v,received=t,symbol=sym,o=o,h=h,l=l,c=c))
 R['validate'](rows)
 return sorted(rows,key=lambda r:(r['day'],r['slot'],r['symbol'])),dict(rows=len(rows),missing=len(days)*len(m['symbols'])*len(SLOTS)-len(rows),zero_volume=sum(r['volume']==0 for r in rows),declared_days=len(days),sha256=m['sha256'],purpose=m['purpose'])
def encode(rows,dates):
 b=io.StringIO(newline='');w=csv.writer(b,lineterminator='\n');w.writerow(FIELDS)
 for r in rows:w.writerow([dates[r['day']],r['symbol'],r['slot'],*[str(r[k]) for k in ('open','high','low','close')],r['volume'],r['received']-end(r['day'],r['slot'])])
 return b.getvalue().encode()
def manifest(raw,dates,syms,purpose='synthetic'):
 return dict(purpose=purpose,dates=dates,symbols=syms,sha256=hashlib.sha256(raw).hexdigest(),source='artificial fixture' if purpose=='synthetic' else 'declared historical source; not authenticated',clock='normalized_logical_v1')
def study():
 checks=Counter();report={}; dates=[str(date(2025,1,1)+timedelta(days=i)) for i in range(32)]
 def ck(k,b):
  if not b:raise AssertionError(k)
  checks[k]+=1
 def reject(k,fn,expected):
  try:fn()
  except ValueError as e:ck(k,str(e)==expected);return
  raise AssertionError(k)
 with tempfile.TemporaryDirectory() as tmp:
  p=Path(tmp)/'test.csv'; absent=Path(tmp)/'nonexistent.csv'
  for case in PLAN['cases']:
   counts=Counter()
   for seed in PLAN['synthetic_seeds']:
    rows=L['fixture'](seed,case);raw=encode(rows,dates);m=manifest(raw,dates,['X','Y']);p.write_bytes(raw);rr,q=load(p,m);counts.update(rows=q['rows'],missing=q['missing'],zero_volume=q['zero_volume']);ck('coverage',q['rows']+q['missing']==32*2*24)
    norm=lambda a:sorted([dict(r,**{k:r[k]*1000 for k in ('open','high','low','close')}) for r in a],key=lambda r:(r['day'],r['slot'],r['symbol']))
    ck('roundtrip',rr==norm(rows));original=L['records'](rows);new=L['records'](rr)
    for (a,b),(c,d) in zip(original,new):ck('feature_label', {k:v for k,v in a.items() if k!='feature_sha'}=={k:v for k,v in c.items() if k!='feature_sha'} and b==d)
    for fee in PLAN['costs']:
     for mode in PLAN['modes']:
      ev,o,re=L['simulate'](original,fee,mode);ee,oo,rrr=L['simulate'](new,fee,mode);ck('lifecycle',(ev,o,re)==(ee,oo,rrr));ck('capital',L['settle'](o,fee)==L['settle'](oo,fee));counts['comparisons']+=1
   report[case]=dict(counts)
  # All invalid tests use synthetic strings, never protected-market data.
  rows=L['fixture'](152000,'stable');raw=encode(rows,dates);m=manifest(raw,dates,['X','Y']);p.write_bytes(raw)
  for d in ['2026-11-26','2026-12-09','2026-12-10']:
   reject('preopen_protected',lambda d=d:load(absent,dict(m,dates=dates[:-1]+[d])),'protected or later date')
  reject('preopen_bad_date',lambda:load(absent,dict(m,dates=dates[:-1]+['2025-02-30'])),'date format');reject('preopen_clock',lambda:load(absent,dict(m,clock='broker')),'clock');reject('preopen_duplicates',lambda:load(absent,dict(m,dates=dates[:-1]+[dates[-2]])),'date order or duplicate');reject('preopen_cohort',lambda:load(absent,dict(m,symbols=['X'])),'synthetic cohort mismatch');reject('hash',lambda:load(p,dict(m,sha256='0'*64)),'hash mismatch')
  lines=raw.decode().splitlines(); first=lines[1].split(',')
  def change(col,val,expected):
   a=first.copy();a[col]=val;data=('\n'.join([lines[0],','.join(a)]+lines[2:])+'\n').encode();p.write_bytes(data);reject('row_reject',lambda:load(p,manifest(data,dates,['X','Y'])),expected)
  change(0,'2026-11-26','protected or later date');change(0,'2025-03-01','undeclared identity or slot');change(1,'Z','undeclared identity or slot');change(2,'12','undeclared identity or slot');change(3,'NaN','price decimal');change(3,'1.0001','price decimal');change(3,'0','price scale');change(7,'-1','unsigned integer');change(8,'86400','cross-day logical receipt unsupported');change(4,'1','row')
  data=raw+lines[1].encode()+b'\n';p.write_bytes(data);reject('duplicate_row',lambda:load(p,manifest(data,dates,['X','Y'])),'duplicate bar')
  # Historical profile uses 19 declared dates but no claim of authoritative exchange calendar.
  known=[str(date(2026,10,26)+timedelta(days=i)) for i in range(30) if (date(2026,10,26)+timedelta(days=i)).weekday()<5 and str(date(2026,10,26)+timedelta(days=i)) not in ('2026-11-06','2026-11-03','2026-11-23')];data=b'date,symbol,slot,open,high,low,close,volume,logical_delay_seconds\n2026-10-26,6501,0,100.125,101,99,100.5,0,0\n';p.write_bytes(data);km=manifest(data,known,SYMS,'known_development');r,q=load(p,km);ck('historical_schema_synthetic_values',r[0]['open']==100125 and r[0]['close']==100500 and q['missing']==19*6*24-1 and q['zero_volume']==1);reject('known_bad_cohort',lambda:load(absent,dict(km,dates=known[:-1])),'known cohort mismatch');reject('known_nov25',lambda:load(absent,dict(km,dates=known[:-1]+['2026-11-25'])),'known cohort mismatch');reject('known_excluded_day',lambda:load(absent,dict(km,dates=sorted(known[:5]+['2026-11-06']+known[6:]))),'known cohort mismatch')
 return dict(plan=PLAN,plan_sha=R['digest'](PLAN),checks=dict(checks),passed=sum(checks.values()),report=report,limits=['normalized subset CSV only; raw broker timestamps/calendar and source authenticity not validated','known-development schema tested with invented values only; real data unavailable','manifest hash is integrity not proof of provenance; protected date metadata rejected before opening, row dates before parsing prices','synthetic 32-day lifecycle only; real 19-day lifecycle not connected','same logical day receipt only; no real orders or fixed evaluation data'])
if __name__=='__main__':
 a=argparse.ArgumentParser();g=a.add_mutually_exclusive_group(required=True);g.add_argument('--self-test',action='store_true');g.add_argument('--csv');a.add_argument('--manifest');x=a.parse_args()
 if x.self_test:z=study()
 else:
  if not x.manifest:a.error('--manifest required')
  _,z=load(x.csv,json.loads(Path(x.manifest).read_text(encoding='utf-8')))
 print(json.dumps(z,sort_keys=True,indent=2))
