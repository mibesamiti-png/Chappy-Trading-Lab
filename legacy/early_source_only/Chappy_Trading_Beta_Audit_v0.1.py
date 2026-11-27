"""R42 historical-only pilot. Displayed closes, no trades; no prospective data."""
import csv, json, hashlib, math, statistics as st, argparse
from pathlib import Path
from datetime import date,timedelta
from decimal import Decimal as D
ROOT=Path(__file__).resolve().parent
IN=ROOT/'Trading_Round42_Beta_Audit'
KEYS=('7203.T','7267.T','TOPIX')
HOL={date(2026,9,d) for d in (21,22,23)}|{date(2026,10,12)}
START=date(2026,9,1); END=date(2026,10,26)
DATES=[(START+timedelta(days=i)).isoformat() for i in range((END-START).days+1) if (START+timedelta(days=i)).weekday()<5 and START+timedelta(days=i) not in HOL]
PROTECTED={'CTRL.zip':'b8bd4e8d9aacbba177c9d7380310b81ac31b9d245d6d1ceecfb9e495b2b493c6','Trading_Prospective_Plan_01.json':'3311941f206b44220374d38e7cef86900cdb1bd480c111d0d2403ad73d1589cb','Chappy_Trading_Research_Lab_v0.5.0.py':'bef9720f6649951c8bfec5dbb0c53dd8eda478a8fa5c6bf10d59861a52a704e1','Trading_Round39_Peer_Context/peer_prices.csv':'436498fb8b4becfb95e9211b348083aa723e6af3c9aed28df381368bff752648','Trading_Round38_Market_Context/benchmarks.csv':'a505ce48874ee7085b21a3dd05d336d7fc72c9565a0eb5c961ef844893ba088c'}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):
 with p.open(newline='',encoding='utf-8-sig') as f:return list(csv.DictReader(f))
def write(p,rs):
 with p.open('w',newline='',encoding='utf-8') as f:
  w=csv.DictWriter(f,fieldnames=list(rs[0]));w.writeheader();w.writerows(rs)
def require(ok,msg):
 if not ok:raise ValueError(msg)
def load(rows):
 out={}
 for r in rows:
  key=(r['symbol'],r['date']);require(key[0] in KEYS and key[1] in DATES and key not in out,'invalid key/calendar/duplicate')
  v=D(r['close']);require(v.is_finite() and v>0 and r['source'].startswith('https://') and r['basis']=='DISPLAYED_PRICE_CLOSE','invalid price/source/basis');out[key]=v
 require(set(out)=={(k,d) for k in KEYS for d in DATES},'missing date')
 return out
def ret(a,b):return 100*(b/a-1)
def pairs(p,k):
 # Exclude the ex-dividend transition and subsequent transition; do not bridge the gap.
 return [(b,float(ret(p['TOPIX',a],p['TOPIX',b])),float(ret(p[k,a],p[k,b]))) for a,b in zip(DATES,DATES[1:]) if b not in ('2026-09-29','2026-09-30')]
def fit(rs):
 require(len(rs)>=10,'insufficient');x=[r[1] for r in rs];y=[r[2] for r in rs];xm=st.mean(x);ym=st.mean(y);sxx=sum((v-xm)**2 for v in x);require(sxx>0,'constant market');beta=sum((a-xm)*(b-ym) for a,b in zip(x,y))/sxx;alpha=ym-beta*xm;err=[b-alpha-beta*a for a,b in zip(x,y)];sse=sum(v*v for v in err);syy=sum((v-ym)**2 for v in y);se=math.sqrt(sse/(len(x)-2)/sxx);return alpha,beta,se,1-sse/syy if syy else None

def main(out):
 out.mkdir(parents=True,exist_ok=True);tests=[]
 def check(n,c):require(c,n);tests.append(dict(test=n,result='PASS'))
 def reject(n,fn):
  try:fn()
  except (ValueError,ArithmeticError):check(n,True);return
  raise RuntimeError(n)
 for f,h in PROTECTED.items():check('protected '+f,sha(ROOT/f)==h)
 rows=read(IN/'prices.csv');p=load(rows);check('exact calendar and 108 closes',len(p)==108 and len(DATES)==36)
 for field,value in [('date','2026-09-23'),('date','2026-11-26'),('close','NaN'),('close','0'),('basis','ADJUSTED_TOTAL_RETURN'),('source','')]:
  reject('reject '+field+' '+value,lambda field=field,value=value:load([dict(rows[0],**{field:value})]+rows[1:]))
 reject('duplicate',lambda:load(rows+[rows[0]]));reject('missing',lambda:load(rows[1:]));reject('constant market',lambda:fit([(str(i),1.,float(i)) for i in range(12)]));reject('too short',lambda:fit([('x',1.,2.)]))
 # Exact synthetic y=2+3x and independent covariance implementation.
 a,b,_,_=fit([(str(i),float(i),2+3.*i) for i in range(12)]);check('synthetic OLS',abs(a-2)<1e-10 and abs(b-3)<1e-10)
 ev={}
 for r in read(ROOT/'Trading_Round39_Peer_Context/peer_prices.csv'):ev[r['symbol'],r['date']]=D(r['close'])
 for r in read(ROOT/'Trading_Round38_Market_Context/benchmarks.csv'):
  if r['index']=='TOPIX':ev['TOPIX',r['date']]=D(r['close'])
 for r in read(IN/'event_extra.csv'):ev[r['symbol'],r['date']]=D(r['close'])
 results=[];returns=[];events=[]
 for k,ed,bd in [('7203.T','2026-11-05','2026-11-04'),('7267.T','2026-11-11','2026-11-10')]:
  rs=pairs(p,k);check(k+' 33 valid returns',len(rs)==33 and all(d not in ('2026-09-29','2026-09-30') for d,_,_ in rs));check(k+' strictly pre event',all(d<bd for d,_,_ in rs))
  for d,x,y in rs:returns.append(dict(symbol=k,date=d,market_pct=x,stock_pct=y))
  fits={}
  for label,r in [('FULL',rs),('SEP',[v for v in rs if v[0][5:7]=='09']),('OCT',[v for v in rs if v[0][5:7]=='10'])]:
   a,b,se,r2=fit(r);x=[v[1] for v in r];y=[v[2] for v in r];ind=st.covariance(x,y)/st.variance(x);check(k+' '+label+' independent beta',abs(b-ind)<1e-12);fits[label]=(a,b)
   results.append(dict(symbol=k,period=label,n=len(r),alpha_pct=a,beta=b,ols_se=se,r2=r2,status='EXPLORATORY_ONLY' if len(r)<60 else 'REVIEW_REQUIRED'))
  x=float(ret(ev['TOPIX',bd],ev['TOPIX',ed]));y=float(ret(ev[k,bd],ev[k,ed]));a,b=fits['FULL'];events.append(dict(symbol=k,start=bd,end=ed,stock_pct=y,market_pct=x,beta1_relative_pp=y-x,model_expected_pct=a+b*x,model_residual_pp=y-a-b*x,sep_residual_pp=y-fits['SEP'][0]-fits['SEP'][1]*x,oct_residual_pp=y-fits['OCT'][0]-fits['OCT'][1]*x,status='RETROSPECTIVE_ONLY'))
  # September fit tested on October, without tuning.
  a,b=fits['SEP'];o=[r for r in rs if r[0][5:7]=='10'];results.append(dict(symbol=k,period='SEP_FIT_OCT_CHECK',n=len(o),alpha_pct=a,beta=b,ols_se='',r2='',status=f'MAE_MODEL={st.mean(abs(y-a-b*x) for _,x,y in o):.6f}; MAE_BETA1={st.mean(abs(y-x) for _,x,y in o):.6f}'))
 for f,h in PROTECTED.items():check('unchanged '+f,sha(ROOT/f)==h)
 for f,r in [('tests.csv',tests),('returns.csv',returns),('beta.csv',results),('event_residuals.csv',events)]:write(out/f,r)
 (out/'manifest.json').write_text(json.dumps(dict(mode='RETROSPECTIVE_ONLY',checks=len(tests),input_hashes={f:sha(IN/f) for f in ('prices.csv','event_extra.csv','rights_review.csv')},protected=PROTECTED,formal_minimum=60,formal_eligible=0,limitations='Convenience sample two stocks; manual public snippets, no complete corporate action history; price returns not total returns; calendar excludes holidays; ex-date and next transition removed; descriptive OLS; no actual receipt evidence or trading.'),indent=2),encoding='utf-8')
 print(len(tests), 'checks passed')
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,default=IN/'results');main(ap.parse_args().out)
