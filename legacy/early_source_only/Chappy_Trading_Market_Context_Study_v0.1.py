"""R38: retrospective matched-window market/sector diagnostics. No orders.
Usage: python Chappy_Trading_Market_Context_Study_v0.1.py benchmark.csv output_dir
The benchmark inputs are manual transcriptions from public historical tables.
"""
import csv, json, hashlib, sys, runpy
from pathlib import Path
from decimal import Decimal as D
from fractions import Fraction as F
P=Path(__file__).resolve().parent
R=runpy.run_path(str(P/'Chappy_Trading_Daily_Event_Study_v0.1.py'))
read,write,require,sha,pct,sign=(R[x] for x in ('read','write','require','sha','pct','sign'))
DATES={d for ds in R['DATES'].values() for d in ds}
INDICES=('TOPIX','TRANSPORT')
def evaluate(bench,prices,consensus):
    t={}
    for r in bench:
        k=r['index'],r['date'];require(k[0] in INDICES and k[1] in DATES and k not in t,'unexpected or duplicate index/date')
        o,h,l,c=[D(r[x]) for x in ('open','high','low','close')]
        require(all(x.is_finite() and x>0 for x in (o,h,l,c)) and l<=min(o,c)<=max(o,c)<=h,'invalid OHLC')
        require(r['source'].startswith('https://'),'missing source');t[k]=r
    require(set(t)=={(i,d) for i in INDICES for d in DATES},'missing benchmark')
    events=R['evaluate'](prices,consensus); stock={(r['symbol'],r['date']):r for r in prices};rows=[]
    for r in events:
        a,b,c=[r[k] for k in ('pre_date','reaction_date','later_date')];s=r['symbol'];A,B,C=[stock[s,d] for d in (a,b,c)]
        for window,first,last,stock_a,stock_b in [('INITIAL',a,b,A['close'],B['close']),('NEXT_OPEN_CLOSE',c,c,C['open'],C['close']),('REACTION_OVERNIGHT',a,b,A['close'],B['open']),('REACTION_OPEN_CLOSE',b,b,B['open'],B['close'])]:
            first_field='open' if window in ('NEXT_OPEN_CLOSE','REACTION_OPEN_CLOSE') else 'close';last_field='open' if window=='REACTION_OVERNIGHT' else 'close'
            raw=pct(D(stock_b),D(stock_a));val={}
            for i in INDICES:
                x,y=t[i,first][first_field],t[i,last][last_field];val[i]=pct(D(y),D(x))
                # Independent rational calculation, checks each matched-window return.
                exact=(F(y)/F(x)-1)*100;require(abs(val[i]-D(exact.numerator)/D(exact.denominator))<D('1e-24'),'benchmark arithmetic mismatch')
            m,g=val['TOPIX'],val['TRANSPORT'];rel=raw-g
            require(abs(raw-(m+(g-m)+rel))<D('1e-24'),'decomposition mismatch')
            rows.append(dict(symbol=s,name=r['name'],release_jst=r['release_jst'],release_class=r['release_class'],window=window,start_date=first,end_date=last,start_field=first_field,end_field=last_field,stock_start=stock_a,stock_end=stock_b,topix_start=t['TOPIX',first][first_field],topix_end=t['TOPIX',last][last_field],sector_start=t['TRANSPORT',first][first_field],sector_end=t['TRANSPORT',last][last_field],surprise_pct=r['surprise_pct'],stock_pct=str(raw),topix_pct=str(m),sector_pct=str(g),stock_minus_topix_pp=str(raw-m),sector_minus_topix_pp=str(g-m),stock_minus_sector_pp=str(rel),receipt_verified=False,tradable=False))
    return rows

def main():
    bpath=Path(sys.argv[1]);out=Path(sys.argv[2]);p=P/'Trading_Round37_Daily_Event/daily_prices.csv';c=P/'Trading_Round26_Consensus/consensus_events.csv'
    protected={str(x):sha(x) for x in (P/'CTRL.zip',P/'Trading_Prospective_Plan_01.json',P/'Chappy_Trading_Research_Lab_v0.5.0.py',P/'Chappy_Trading_Lab_v1.1.0-rc1.py',P/'Chappy_Trading_Daily_Event_Study_v0.1.py',p,c)}
    b,prices,cons=map(read,(bpath,p,c));rows=evaluate(b,prices,cons);tests=[]
    def check(n,v):require(v,n);tests.append(dict(test=n,result='PASS'))
    check('24 matched windows',len(rows)==24);check('14 index records',len(b)==14);check('input order invariant',rows==evaluate(b[::-1],prices[::-1],cons[::-1]));check('retrospective only',all(not r['tradable'] and not r['receipt_verified'] for r in rows))
    for r in rows:
        # independent rational calculation of each stock and relative return
        a=(F(r['stock_end'])/F(r['stock_start'])-1)*100;m=(F(r['topix_end'])/F(r['topix_start'])-1)*100;g=(F(r['sector_end'])/F(r['sector_start'])-1)*100
        check(r['symbol']+' '+r['window'],all(abs(D(r[k])-D(v.numerator)/D(v.denominator))<D('1e-24') for k,v in [('stock_pct',a),('stock_minus_topix_pp',a-m),('stock_minus_sector_pp',a-g)]))
    for name,bad in [('missing',b[:-1]),('duplicate',b+[b[0]]),('future',[dict(b[0],date='2026-11-26')]+b[1:]),('wrong index',[dict(b[0],index='FUTURES')]+b[1:]),('bad OHLC',[dict(b[0],low='9000')]+b[1:]),('nonfinite',[dict(b[0],close='NaN')]+b[1:])]:
        try:evaluate(bad,prices,cons)
        except ValueError:check(name,True)
        else:raise RuntimeError(name)
    initial={r['symbol']:r for r in rows if r['window']=='INITIAL'};later={r['symbol']:r for r in rows if r['window']=='NEXT_OPEN_CLOSE'}
    summary=[]
    for k in ('stock_pct','stock_minus_topix_pp','stock_minus_sector_pp'):
        for label,keys in [('ALL',list(initial)),('IN_SESSION',[s for s,r in initial.items() if r['release_class']=='IN_SESSION']),('AFTER_CLOSE',[s for s,r in initial.items() if r['release_class']=='AT_OR_AFTER_CLOSE'])]:
            a=[initial[s] for s in keys];n=[later[s] for s in keys];match=lambda x,y:sign(D(x))==sign(D(y))
            summary.append(dict(group=label,measure=k,n=len(a),initial_surprise_matches=sum(match(r[k],r['surprise_pct']) for r in a),next_surprise_matches=sum(match(r[k],r['surprise_pct']) for r in n),initial_next_matches=sum(match(x[k],y[k]) for x,y in zip(a,n))))
    check('protected unchanged',all(sha(Path(k))==v for k,v in protected.items()));out.mkdir(exist_ok=False);write(out/'windows.csv',rows);write(out/'summary.csv',summary);write(out/'tests.csv',tests)
    (out/'manifest.json').write_text(json.dumps(dict(benchmark_sha256=sha(bpath),protected=protected,windows=len(rows),tests=len(tests),mode='RETROSPECTIVE_ONLY',limitations='Unit-beta descriptive return differences, not causal effects or tradable hedge. Indices contain event stocks. Index opens may be asynchronous. No verified historical receipt, no future data, no parameter fitting.'),indent=2),encoding='utf8')
if __name__=='__main__':main()
