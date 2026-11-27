"""R156: frozen known-development archive intake; no network, trading or evaluation.
Original bar start labels preserved, close availability is an idealized timestamp only.
"""
import argparse,csv,hashlib,io,json,re,zipfile
from collections import Counter
from datetime import datetime,timedelta,date
from decimal import Decimal,InvalidOperation
from pathlib import Path
from fractions import Fraction
SHA='b8bd4e8d9aacbba177c9d7380310b81ac31b9d245d6d1ceecfb9e495b2b493c6'
SYMS=('6501.T','6758.T','7203.T','7267.T','8058.T','8306.T')
CUTOFF='2026-11-26'
DAYS=tuple(str(date(2026,10,26)+timedelta(days=i)) for i in range(30) if (date(2026,10,26)+timedelta(days=i)).weekday()<5 and str(date(2026,10,26)+timedelta(days=i)) not in ('2026-11-03','2026-11-06','2026-11-23'))
ALL=tuple(sorted(DAYS+('2026-11-06',)))
SLOTS=tuple(f'{m//60:02}:{m%60:02}:00' for a,b in ((550,690),(750,925)) for m in range(a,b,5))
FIELDS=['datetime','open','high','low','close','volume']
def need(ok,msg):
 if not ok:raise ValueError(msg)
def sha(b):return hashlib.sha256(b).hexdigest()
def timestamp(s):
 need(bool(re.fullmatch(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}',s)),'timestamp syntax')
 t=datetime.fromisoformat(s);d=s[:10];need(d<CUTOFF,'protected date');need(d in ALL,'unexpected day');need(s[11:] in SLOTS,'unexpected slot');return t
def number(s,scale):
 need(bool(re.fullmatch(r'[0-9]+(?:\.[0-9]+)?',s)),'number syntax');x=Decimal(s);v=Fraction(x)*scale;need(v.denominator==1,'precision');return int(v)
def parse(raw,sym,checks):
 reader=csv.reader(io.StringIO(raw.decode('utf-8-sig'),newline=''),strict=True);need(next(reader,None)==FIELDS,'header');rs=list(reader);seen=set();meta=[]
 for r in rs:
  need(len(r)==6,'columns');t=timestamp(r[0]);need(t not in seen,'duplicate');seen.add(t);meta.append(t);checks['timestamp']+=1
 need(meta==sorted(meta),'order')
 expected=DAYS if sym=='6501.T' else ALL
 need(set(t.date().isoformat() for t in meta)==set(expected),'date cohort')
 for d in expected:need({t.strftime('%H:%M:%S') for t in meta if str(t.date())==d}==set(SLOTS),'slot coverage');checks['symbol_day']+=1
 out=[]
 for r,t in zip(rs,meta):
  o,h,l,c=(number(x,1000) for x in r[1:5]);v=number(r[5],1);need(0<l<=min(o,c)<=max(o,c)<=h and v>=0,'OHLCV');checks['numeric']+=1
  need(all(Fraction(x)==Fraction(n,1000) for x,n in zip(r[1:5],(o,h,l,c))) and Fraction(r[5])==v,'exact conversion');checks['exact_conversion']+=1
  close=t+timedelta(minutes=5);need(close.date()==t.date() and close.time()<=datetime.strptime('15:25:00','%H:%M:%S').time(),'close boundary');checks['close_time']+=1
  if str(t.date()) in DAYS:out.append((sym,t.isoformat(),close.isoformat(),o,h,l,c,v))
 return out,len(rs)
def intake(path):
 raw=Path(path).read_bytes();need(sha(raw)==SHA,'unapproved archive hash');checks=Counter(archive_hash=1);result=[];details={}
 with zipfile.ZipFile(io.BytesIO(raw)) as z:
  ns=z.namelist();need(len(ns)==len(set(ns)),'duplicate archive member');need(z.testzip() is None,'CRC');checks['zip_crc']+=1
  reports=[n for n in ns if n.endswith('/acquisition_report.json')];need(len(reports)==1,'report count');prefix=reports[0].rsplit('/',1)[0]+'/';r=json.loads(z.read(reports[0]));need(sorted(r['requested'])==list(SYMS) and r['all_requested_ok'] and r['ready'],'acquisition manifest')
  need(tuple(r['preflight']['split']['train']+r['preflight']['split']['validation']+r['preflight']['split']['holdout'])==DAYS,'report day cohort');checks['reported_dates']+=1
  entries=r['entries'];need(sorted(e['symbol'] for e in entries)==list(SYMS),'entry cohort')
  for e in sorted(entries,key=lambda a:a['symbol']):
   s=e['symbol'];name=e['csv'];need(e['status']=='ok' and '/' not in name and '\\' not in name,'entry');data=z.read(prefix+name);m=json.loads(z.read(prefix+name[:-4]+'.json'));need(sha(data)==e['sha256']==m['sha256'],'CSV hash');checks['csv_sha256']+=1
   need(m['symbol']==s and m['interval']=='5m' and m['timezone']=='Asia/Tokyo' and m['quality']['expected_bars_per_day']==63 and m['quality']['dropped_days']==e['dropped_days'],'metadata mismatch');checks['metadata']+=1
   rows,n=parse(data,s,checks);need(m['quality']['accepted_bars']==n==63*e['accepted_days'],'bar count');checks['metadata_count']+=1
   result.extend(rows);details[s]={'raw_bars':n,'common_bars':len(rows),'sha256':sha(data),'source':m['source'],'excluded_days':e['dropped_days'],'zero_volume_common':sum(a[-1]==0 for a in rows)}
 need(len(result)==19*6*63 and len({(a[0],a[1]) for a in result})==len(result),'common count');checks['common_count']+=1
 result.sort(key=lambda a:(a[1],a[0]));digest=sha(json.dumps(result,separators=(',',':')).encode())
 # Rejections use invented values only, not the reserved evaluation period.
 for s in ['2026-11-26 09:10:00','2026-12-09 09:10:00','2026-11-25 09:10:00','2026-10-26 11:30:00','2026-10-26 15:25:00']:
  try:timestamp(s)
  except ValueError:checks['reject_timestamp']+=1
  else:raise AssertionError('timestamp rejection')
 for s,sc in [('NaN',1000),('1.0001',1000),('1.1',1),('-1',1)]:
  try:number(s,sc)
  except ValueError:checks['reject_number']+=1
  else:raise AssertionError('numeric rejection')
 return dict(status='KNOWN_DEVELOPMENT_INTAKE_ONLY',archive_sha256=sha(raw),archive_bytes=len(raw),dates=DAYS,symbols=details,raw_bars=sum(v['raw_bars'] for v in details.values()),common_bars=len(result),excluded_bars=sum(v['raw_bars'] for v in details.values())-len(result),slot_count=len(SLOTS),slots=SLOTS,normalized_sha256=digest,checks=dict(checks),passed=sum(checks.values()),limits=['archive hash pinned on current receipt, historical external hash unavailable','same-archive hash and metadata do not authenticate provider','close availability assumes bar end, actual receipt absent','full 63-slot mapping not yet connected to R155 artificial 24-slot runtime','known development only; no profitability evaluation or live orders'])
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('archive');a.add_argument('--output',required=True);x=a.parse_args();r=intake(x.archive)
 with open(x.output,'x',encoding='utf-8') as f:json.dump(r,f,ensure_ascii=False,sort_keys=True,indent=2);f.write('\n')
 print(r['passed'],r['raw_bars'],r['common_bars'],r['normalized_sha256'])
