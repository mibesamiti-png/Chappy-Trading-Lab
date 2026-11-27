"""R39 retrospective peer comparison; no trades or future data. Standard library only."""
import csv,json,hashlib,sys
from pathlib import Path
from fractions import Fraction as F
from decimal import Decimal as D
P=Path(__file__).resolve().parent
ROOT=P/'Trading_Round39_Peer_Context'
DATES=tuple('2026-11-'+x for x in ('05','06','09','10','11','12','13'))
PEERS=('6902.T','7259.T','7203.T','7267.T')
PARTS=PEERS[:2]
EVENTS={'6902.T':('2026-10-29','2026-10-30'),'7259.T':('2026-10-29','2026-10-30'),'7203.T':(DATES[0],DATES[1]),'7267.T':(DATES[3],DATES[4])}
TARGETS=('7261.T','7270.T','7201.T','7269.T','7211.T','7202.T')
WINDOWS=('INITIAL','NEXT_OPEN_CLOSE','REACTION_OVERNIGHT','REACTION_OPEN_CLOSE')
def req(x,msg):
    if not x:raise ValueError(msg)
def read(p):
    with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def write(p,rows):
    with p.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def fmt(x):return str(D(x.numerator)/D(x.denominator))
def ret(x,y):return (F(y)/F(x)-1)*100
def sg(x):return (x>0)-(x<0)
def evaluate(prices,events,windows):
    idx={};dates={}
    for r in prices:
        k=r['symbol'],r['date'];req(k[0] in PEERS and k[1] in DATES and k not in idx,'bad price key')
        o,h,l,c=map(F,[r[x] for x in ('open','high','low','close')]);req(0<l<=min(o,c)<=max(o,c)<=h and int(r['volume'])>0 and r['source'].startswith('https://'),'bad price')
        idx[k]=r
    req(set(idx)=={(s,d) for s in PEERS for d in DATES},'missing price')
    for r in events:
        s=r['symbol'];v=r['earnings_date'],r['next_session'];req(s in EVENTS and s not in dates and v==EVENTS[s] and r['source'].startswith('https://'),'unverified event')
        dates[s]=v
    req(set(dates)==set(PEERS),'missing event')
    rows=[];seen=set()
    for r in sorted(windows,key=lambda x:(x['symbol'],x['window'])):
        s,w=r['symbol'],r['window'];a,b=r['start_date'],r['end_date'];af,bf=r['start_field'],r['end_field'];k=s,w
        req(s in TARGETS and w in WINDOWS and k not in seen and a in DATES and b in DATES and a<=b and af in ('open','close') and bf in ('open','close'),'bad window');seen.add(k)
        raw=ret(r['stock_start'],r['stock_end']);sur=F(r['surprise_pct']);req(abs(raw-F(r['stock_pct']))<F(1,10**23),'stock return mismatch')
        clean=tuple(p for p in PEERS if not any(a<=d<=b for d in dates[p]))
        rr={p:ret(idx[p,a][af],idx[p,b][bf]) for p in PEERS}
        for mode,peers in [('PARTS_ONLY',PARTS),('ALL_UNFILTERED',PEERS),('EARNINGS_EXCLUDED',clean)]+[('EXCLUDE_'+p,tuple(q for q in clean if q!=p)) for p in clean]:
            req(peers and s not in peers,'invalid controls');m=sum((rr[p] for p in peers),F(0))/len(peers);rel=raw-m
            # independent decimal verification of peer returns and aggregate
            m2=sum((100*(D(idx[p,b][bf])/D(idx[p,a][af])-1) for p in peers),D(0))/D(len(peers))
            req(abs(D(fmt(m))-m2)<D('1e-23'),'arithmetic mismatch')
            rows.append(dict(symbol=s,name=r['name'],window=w,start_date=a,end_date=b,mode=mode,peers=';'.join(peers),n=len(peers),excluded=';'.join(p for p in PEERS if p not in clean),stock_pct=fmt(raw),peer_pct=fmt(m),relative_pp=fmt(rel),surprise_pct=r['surprise_pct'],match=int(sg(rel)==sg(sur)),tradable=False))
    req(seen=={(s,w) for s in TARGETS for w in WINDOWS},'missing windows')
    return rows

def main():
    out=Path(sys.argv[1]);paths=[ROOT/'peer_prices.csv',ROOT/'peer_events.csv',P/'Trading_Round38_Market_Context/results/windows.csv'];protected={str(p):sha(p) for p in paths+[P/'Trading_Prospective_Plan_01.json',P/'CTRL.zip',P/'Chappy_Trading_Lab_v1.1.0-rc1.py',P/'Chappy_Trading_Research_Lab_v0.5.0.py',P/'Chappy_Trading_Market_Context_Study_v0.1.py']}
    prices,events,windows=map(read,paths);rows=evaluate(prices,events,windows);tests=[]
    def check(name,x):req(x,name);tests.append(dict(test=name,result='PASS'))
    check('28 price rows',len(prices)==28);check('24 windows',len(windows)==24);check('input order invariant',rows==evaluate(prices[::-1],events[::-1],windows[::-1]));check('research only',all(not r['tradable'] for r in rows))
    for r in rows:
        if r['mode']=='EARNINGS_EXCLUDED':
            pp=r['peers'].split(';');check(r['symbol']+' '+r['window'],all(not any(r['start_date']<=d<=r['end_date'] for d in EVENTS[p]) for p in pp) and len(pp)>=2)
    for n,args in [('missing',(prices[:-1],events,windows)),('duplicate',(prices+[prices[0]],events,windows)),('unknown date',([dict(prices[0],date='2026-11-26')]+prices[1:],events,windows)),('bad OHLC',([dict(prices[0],low='99999')]+prices[1:],events,windows)),('missing event',(prices,events[:-1],windows)),('wrong event',(prices,[dict(events[0],earnings_date='2026-11-05')]+events[1:],windows)),('missing window',(prices,events,windows[:-1]))]:
        try:evaluate(*args)
        except ValueError:check(n,True)
        else:raise RuntimeError(n)
    summary=[]
    for mode in ('PARTS_ONLY','ALL_UNFILTERED','EARNINGS_EXCLUDED'):
        a={r['symbol']:r for r in rows if r['mode']==mode and r['window']=='INITIAL'};b={r['symbol']:r for r in rows if r['mode']==mode and r['window']=='NEXT_OPEN_CLOSE'}
        summary.append(dict(mode=mode,n=len(a),initial_matches=sum(r['match'] for r in a.values()),later_matches=sum(r['match'] for r in b.values()),initial_later_matches=sum(sg(F(r['relative_pp']))==sg(F(b[s]['relative_pp'])) for s,r in a.items())))
    sensitivity=[]
    for s in TARGETS:
        for w in ('INITIAL','NEXT_OPEN_CLOSE'):
            a=next(r for r in rows if r['symbol']==s and r['window']==w and r['mode']=='EARNINGS_EXCLUDED');b=[r for r in rows if r['symbol']==s and r['window']==w and r['mode'].startswith('EXCLUDE_')];v=[F(r['relative_pp']) for r in b];sensitivity.append(dict(symbol=s,name=a['name'],window=w,base_pp=a['relative_pp'],min_pp=fmt(min(v)),max_pp=fmt(max(v)),sign_stable=all(sg(q)==sg(F(a['relative_pp'])) for q in v),all_match=all(r['match'] for r in b)))
    check('protected unchanged',all(sha(Path(p))==v for p,v in protected.items()));out.mkdir(exist_ok=False);write(out/'windows.csv',rows);write(out/'summary.csv',summary);write(out/'sensitivity.csv',sensitivity);write(out/'tests.csv',tests);(out/'manifest.json').write_text(json.dumps(dict(mode='RETROSPECTIVE_ONLY',protected=protected,tests=len(tests),rows=len(rows),notes='Four convenience-selected peers; excludes known quarterly release day and next trading day if either endpoint touches; no comprehensive material news exclusion. Parts suppliers not pure OEM controls. No causal or predictive claim; no actual receipts.'),indent=2),encoding='utf8')
if __name__=='__main__':main()
