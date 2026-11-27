"""R37 retrospective daily diagnostics only. No orders or pilot changes.
Usage: python script.py input_prices.csv NEW_OUTPUT_DIR
Input prices manually transcribed from cited web search results, not live receipts.
"""
import csv, json, hashlib, sys
from datetime import date, datetime, time, timedelta
from decimal import Decimal as D
from pathlib import Path
P=Path(__file__).resolve().parent
C=P/'Trading_Round26_Consensus/consensus_events.csv'
Q=P/'Trading_Round26_Consensus/acquisition_queue.csv'
DATES={'7261.T':('2026-11-06','2026-11-09','2026-11-10'),'7270.T':('2026-11-09','2026-11-10','2026-11-11'),'7201.T':('2026-11-11','2026-11-12','2026-11-13'),'7269.T':('2026-11-09','2026-11-10','2026-11-11'),'7211.T':('2026-11-06','2026-11-09','2026-11-10'),'7202.T':('2026-11-05','2026-11-06','2026-11-09')}
CUTOFF=date(2026,11,24)
def require(x,msg):
    if not x: raise ValueError(msg)
def read(p):
    with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def write(p,rows):
    with p.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def sign(x):return (x>0)-(x<0)
def pct(a,b):return (a/b-1)*100
def next_session(s):
    # Only specified November 5–13 window; no Japanese holidays within this range.
    d=date.fromisoformat(s)+timedelta(days=1)
    while d.weekday()>=5:d+=timedelta(days=1)
    return str(d)
def evaluate(prices,events):
    table={}; rows=[]
    for r in prices:
        k=r['symbol'],r['date'];require(k not in table,'duplicate')
        require(k[0] in DATES and k[1] in DATES[k[0]] and date.fromisoformat(k[1])<=CUTOFF,'unapproved date/symbol')
        o,h,l,c=[D(r[x]) for x in ('open','high','low','close')]
        require(all(x.is_finite() and x>0 for x in (o,h,l,c)) and l<=min(o,c)<=max(o,c)<=h,'OHLC invalid')
        require(int(r['volume'])>0 and r['source'].startswith('https://'),'volume/source invalid')
        table[k]=r
    require(set(table)=={(s,d) for s,ds in DATES.items() for d in ds},'missing rows')
    by={r['symbol']:r for r in events};require(len(by)==len(events),'duplicate event')
    for s,ds in DATES.items():
        e=by[s];t=datetime.fromisoformat(e['release_jst']);in_session=t.time()<time(15,30)
        require(ds[1]==(str(t.date()) if in_session else next_session(str(t.date()))) and next_session(ds[0])==ds[1] and next_session(ds[1])==ds[2],'event window mismatch')
        require(e['receipt_jst']=='' and e['live_eligible']=='False','unexpected receipt status')
        a,b,c=(table[s,d] for d in ds)
        surprise=pct(D(e['actual']),D(e['reported_latest_consensus']))
        require(abs(surprise-D(e['consensus_gap_pct']))<D('1e-10'),'consensus mismatch')
        reaction=pct(D(b['close']),D(a['close']));later=pct(D(c['close']),D(c['open']))
        # Signs only, no execution assumption, all retrospective.
        rows.append(dict(symbol=s,name=e['name'],release_jst=e['release_jst'],release_class='IN_SESSION' if in_session else 'AT_OR_AFTER_CLOSE',pre_date=ds[0],reaction_date=ds[1],later_date=ds[2],pre_close=a['close'],reaction_close=b['close'],later_open=c['open'],later_close=c['close'],surprise_pct=str(surprise),reaction_pct=str(reaction),later_open_close_pct=str(later),surprise_reaction_match=sign(surprise)==sign(reaction),price_follow_match=sign(reaction)==sign(later),consensus_follow_match=sign(surprise)==sign(later),agreement=sign(reaction)==sign(surprise),receipt_verified=False,tradable=False,consensus_source=e['source'],pre_source=a['source'],reaction_source=b['source'],later_source=c['source']))
    return rows

def main():
    src=Path(sys.argv[1]);out=Path(sys.argv[2]);protected={n:sha(P/n) for n in ('CTRL.zip','Trading_Prospective_Plan_01.json','Chappy_Trading_Research_Lab_v0.5.0.py','Chappy_Trading_Lab_v1.1.0-rc1.py','Trading_Round26_Consensus/consensus_events.csv','Trading_Round26_Consensus/acquisition_queue.csv')}
    prices=read(src);events=read(C);rows=evaluate(prices,events);tests=[]
    def check(name,cond):require(cond,name);tests.append(dict(test=name,result='PASS'))
    check('all six extra events',len(rows)==6);check('no receipt verified',all(not r['receipt_verified'] and not r['tradable'] for r in rows));check('row order independent',rows==evaluate(list(reversed(prices)),events))
    for r in rows:
        # independent cross multiplication for direction labels
        check(r['symbol']+' price sign',r['price_follow_match']==((D(r['reaction_close'])-D(r['pre_close']))*(D(r['later_close'])-D(r['later_open']))>0))
    for name,bad in [('missing',prices[:-1]),('duplicate',prices+[prices[0]]),('future',[dict(prices[0],date='2026-11-26')]+prices[1:]),('invalid OHLC',[dict(prices[0],high='1')]+prices[1:]),('zero volume',[dict(prices[0],volume='0')]+prices[1:])]:
        try:evaluate(bad,events)
        except ValueError:check(name,True)
        else:raise RuntimeError(name)
    check('protected unchanged',protected=={n:sha(P/n) for n in protected})
    out.mkdir(exist_ok=False);write(out/'events.csv',rows);write(out/'tests.csv',tests)
    summary=[]
    for label,subset in [('ALL',rows),('IN_SESSION',[r for r in rows if r['release_class']=='IN_SESSION']),('AT_OR_AFTER_CLOSE',[r for r in rows if r['release_class']=='AT_OR_AFTER_CLOSE']),('AGREEMENT',[r for r in rows if r['agreement']])]:
        for field in ('surprise_reaction_match','price_follow_match','consensus_follow_match'):
            summary.append(dict(group=label,metric=field,n=len(subset),matches=sum(r[field] for r in subset)))
    write(out/'summary.csv',summary)
    (out/'manifest.json').write_text(json.dumps(dict(input_sha256=sha(src),protected=protected,events=len(rows),price_rows=len(prices),tests=len(tests),mode='RETROSPECTIVE_ONLY',notes='First post-announcement close vs preceding close includes pre-release moves for in-session events. Subsequent full-session open-to-close is a descriptive outcome, no executable return or confirmed receipt. Manual search-result transcription; not independently verified exchange feed. No pilot dates.'),indent=2),encoding='utf-8')
if __name__=='__main__':main()
