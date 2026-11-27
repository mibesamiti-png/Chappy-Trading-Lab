"""Round 44: retrospective event windows only. No orders, no prospective data."""
import csv, json, hashlib, argparse, copy
from pathlib import Path
from datetime import date, datetime, time
from decimal import Decimal as D
from fractions import Fraction as F
ROOT=Path(__file__).resolve().parent
DATA=ROOT/'Trading_Round44_Cross_Sector'
LOCK=json.loads((ROOT/'Trading_Round43_Event_Bundle/results/manifest.json').read_text())['protected']
COHORT={'6857':('2026-10-28','2026-10-29','2026-10-30','2026-10-28T15:30'), '8035':('2026-10-30','2026-11-02','2026-11-04','2026-10-30T15:30'), '8316':('2026-11-12','2026-11-13','2026-11-16','2026-11-13T13:30'), '8411':('2026-11-13','2026-11-16','2026-11-17','2026-11-13T15:30'), '8001':('2026-11-02','2026-11-04','2026-11-05','2026-11-04T13:00'), '8031':('2026-11-02','2026-11-04','2026-11-05','2026-11-04T12:00')}
def require(ok,msg):
    if not ok: raise ValueError(msg)
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):
    with p.open(encoding='utf-8-sig',newline='') as f: return list(csv.DictReader(f))
def write(p,rows):
    with p.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
def number(v):
    x=D(v); require(x.is_finite(),'nonfinite'); return x
def pct(a,b):
    a,b=number(a),number(b); require(b>0,'nonpositive denominator'); return (a/b-1)*100
def compare(events,prices):
    require(len(events)==6 and {x['symbol'] for x in events}==set(COHORT),'cohort')
    expected={(s,d) for s,v in COHORT.items() for d in v[:3]}; lookup={}
    for p in prices:
        k=p['symbol'],p['date']; require(k in expected and k not in lookup,'unexpected or duplicate price')
        o,h,l,c,v=map(number,[p[x] for x in ('open','high','low','close','volume')]); require(0<l<=min(o,c)<=max(o,c)<=h and v>0 and v==v.to_integral_value(),'OHLCV')
        require(p['source'].startswith('https://'),'source'); lookup[k]=p
    require(set(lookup)==expected,'missing price')
    out=[]
    for e in events:
        s=e['symbol']; base,react,nxt,release=COHORT[s]; require(tuple(e[x] for x in ('base_day','reaction_day','next_day','release_jst'))==COHORT[s],'window')
        day=release[:10]; require(e['source'].startswith('https://') and e['h1_metric'] in ('税引前利益','経常利益'),'event source/metric'); number(e['h1_actual_m'])
        def expectation(actual,cons,stamp):
            require(bool(cons)==bool(stamp),'missing consensus metadata')
            if not cons: return ''
            require(date.fromisoformat(stamp)<date.fromisoformat(day),'consensus not dated before release')
            return pct(actual,cons)
        h1=expectation(e['h1_actual_m'],e['h1_consensus_m'],e['h1_consensus_date'])
        fy=''; rev=''
        if any(e[x] for x in ('fy_net_old_m','fy_net_new_m','fy_net_consensus_m','fy_consensus_date','fy_source')):
            require(all(e[x] for x in ('fy_net_old_m','fy_net_new_m','fy_net_consensus_m','fy_consensus_date','fy_source')) and e['fy_source'].startswith('https://'),'incomplete FY')
            fy=expectation(e['fy_net_new_m'],e['fy_net_consensus_m'],e['fy_consensus_date']);rev=pct(e['fy_net_new_m'],e['fy_net_old_m'])
        a,b,c=(lookup[s,d] for d in (base,react,nxt)); post=pct(b['close'],a['close']); gap=pct(b['open'],a['close']); intraday=pct(b['close'],b['open']); later=pct(c['close'],c['open'])
        out.append(dict(symbol=s,name=e['name'],sector=e['sector'],release_jst=release,h1_surprise_pct=h1,fy_net_revision_pct=rev,fy_net_surprise_pct=fy,first_reaction_pct=post,first_gap_pct=gap,first_intraday_pct=intraday,next_intraday_pct=later,window='AFTER_CLOSE_REFERENCE' if release.endswith('15:30') else 'MIXED_PRE_POST_RELEASE',receipt='UNVERIFIED',execution='DISABLED'))
    return out

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,default=DATA/'results'); args=ap.parse_args(); out=args.out;out.mkdir(parents=True,exist_ok=True)
    for p,h in LOCK.items():require(sha(ROOT/p)==h,'protected changed '+p)
    inputs={p:sha(DATA/p) for p in ('events.csv','prices.csv','source_review.md')}; ev=read(DATA/'events.csv'); px=read(DATA/'prices.csv'); rows=compare(ev,px); tests=[]
    def check(name,ok):require(ok,name);tests.append({'test':name,'result':'PASS'})
    def reject(name,e,p):
        try:compare(e,p)
        except (ValueError,ArithmeticError):check(name,True)
        else:raise ValueError('accepted '+name)
    check('six rows',len(rows)==6);check('four H1 pairs',sum(r['h1_surprise_pct']!='' for r in rows)==4);check('three FY pairs',sum(r['fy_net_surprise_pct']!='' for r in rows)==3); check('all disabled',all(r['execution']=='DISABLED' for r in rows))
    l={(p['symbol'],p['date']):p for p in px}
    for e,r in zip(ev,rows):
        a,b,c=(l[e['symbol'],e[k]] for k in ('base_day','reaction_day','next_day'))
        pairs={'first_reaction_pct':(b['close'],a['close']),'first_gap_pct':(b['open'],a['close']),'first_intraday_pct':(b['close'],b['open']),'next_intraday_pct':(c['close'],c['open'])}
        if r['h1_surprise_pct']!='':pairs['h1_surprise_pct']=(e['h1_actual_m'],e['h1_consensus_m'])
        if r['fy_net_surprise_pct']!='':pairs.update(fy_net_revision_pct=(e['fy_net_new_m'],e['fy_net_old_m']),fy_net_surprise_pct=(e['fy_net_new_m'],e['fy_net_consensus_m']))
        for k,(x,y) in pairs.items():check(e['symbol']+' '+k,abs(F(r[k])-(F(x)-F(y))*100/F(y))<F(1,10**23))
    reject('missing price',ev,px[:-1]);reject('duplicate price',ev,px+[px[0]])
    for field,value in [('date','2026-11-26'),('high','0'),('volume','0'),('close','NaN'),('source','')]:
        z=copy.deepcopy(px);z[0][field]=value;reject('bad price '+field,ev,z)
    for field,value in [('h1_consensus_date','2026-10-28'),('h1_consensus_m','0'),('h1_consensus_date',''),('fy_net_new_m',''),('reaction_day','2026-11-26'),('h1_metric','EPS')]:
        z=copy.deepcopy(ev);z[0][field]=value;reject('bad event '+field,z,px)
    check('order invariance',sorted(compare(ev[::-1],px[::-1]),key=lambda r:r['symbol'])==sorted(rows,key=lambda r:r['symbol']))
    pairs=[r for r in rows if r['h1_surprise_pct']!='']; sign=lambda x:(x>0)-(x<0)
    summary={'cohort':len(rows),'h1_pairs':len(pairs),'fy_pairs':sum(r['fy_net_surprise_pct']!='' for r in rows),'h1_first_match':sum(sign(r['h1_surprise_pct'])==sign(r['first_reaction_pct']) for r in pairs),'h1_next_match':sum(sign(r['h1_surprise_pct'])==sign(r['next_intraday_pct']) for r in pairs),'tests':len(tests),'mode':'RETROSPECTIVE_ONLY'}
    for p,h in LOCK.items():require(sha(ROOT/p)==h,'protected changed '+p)
    require(all(sha(DATA/p)==h for p,h in inputs.items()),'input changed');write(out/'comparison.csv',rows);write(out/'tests.csv',tests);(out/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8');(out/'manifest.json').write_text(json.dumps({'protected':LOCK,'inputs':inputs,'mode':'RETROSPECTIVE_ONLY','limits':'Convenience cohort, manual search excerpts, unverified receipt, mixed windows, no market adjustment, no orders'},indent=2),encoding='utf-8');print(json.dumps(summary,ensure_ascii=False))
if __name__=='__main__':main()
