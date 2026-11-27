"""R40: independent foundation audit. Read-only inputs, no orders or pilot evaluation."""
import csv, json, hashlib, zipfile, runpy, sys
from pathlib import Path
from fractions import Fraction as F
from decimal import Decimal as D
from collections import defaultdict
P=Path(__file__).resolve().parent
paths={k:P/v for k,v in dict(archive='CTRL.zip',plan='Trading_Prospective_Plan_01.json',research='Chappy_Trading_Research_Lab_v0.5.0.py',rc='Chappy_Trading_Lab_v1.1.0-rc1.py',cons='Trading_Round26_Consensus/consensus_events.csv',prices='Trading_Round37_Daily_Event/daily_prices.csv',index='Trading_Round38_Market_Context/benchmarks.csv',peers='Trading_Round39_Peer_Context/peer_prices.csv',events='Trading_Round39_Peer_Context/peer_events.csv',r38='Trading_Round38_Market_Context/results/windows.csv',r39='Trading_Round39_Peer_Context/results/windows.csv',code37='Chappy_Trading_Daily_Event_Study_v0.1.py',code38='Chappy_Trading_Market_Context_Study_v0.1.py',code39='Chappy_Trading_Peer_Context_Study_v0.1.py').items()}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):
    with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def write(p,rows):
    with p.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def fstr(x):return str(D(x.numerator)/D(x.denominator))
def ret(a,b):return (F(b)/F(a)-1)*100
def sign(x):return (x>0)-(x<0)
def req(b,n):
    if not b:raise ValueError(n)
def main(out):
    before={k:sha(p) for k,p in paths.items()};tests=[]; findings=[]
    def check(n,b):req(b,n);tests.append(dict(test=n,result='PASS'))
    check('original archive unchanged from R1',before['archive']=='b8bd4e8d9aacbba177c9d7380310b81ac31b9d245d6d1ceecfb9e495b2b493c6')
    check('original pilot unchanged',before['plan']=='3311941f206b44220374d38e7cef86900cdb1bd480c111d0d2403ad73d1589cb')
    check('original research code unchanged',before['research']=='bef9720f6649951c8bfec5dbb0c53dd8eda478a8fa5c6bf10d59861a52a704e1')
    source={k:read(paths[k]) for k in ('cons','prices','index','peers','events','r38','r39')}
    check('all price dates before protected pilot',all(r['date']<'2026-11-26' for k in ('prices','index','peers') for r in source[k]))
    # Cross-resolution overlap: compare contained OHLCV, never assume endpoints match.
    bars=defaultdict(list)
    with zipfile.ZipFile(paths['archive']) as z:
        for n in z.namelist():
            if n.endswith('.csv') and any(s in n for s in ('7203.T','7267.T')):
                s=Path(n).name.split('_')[0]
                for r in csv.DictReader(z.read(n).decode('utf-8-sig').splitlines()):
                    if r['datetime'][:10]<'2026-11-26':bars[s,r['datetime'][:10]].append(r)
    overlap=[]
    for r in source['peers']:
        k=r['symbol'],r['date']; x=sorted(bars.get(k,[]),key=lambda q:q['datetime'])
        if not x:continue
        check('contained session '+str(k),len(x)==63 and x[0]['datetime'].endswith('09:10:00') and x[-1]['datetime'].endswith('15:20:00') and F(r['low'])<=min(F(v['low']) for v in x) and F(r['high'])>=max(F(v['high']) for v in x) and F(r['volume'])>=sum(F(v['volume']) for v in x))
        overlap.append(dict(symbol=k[0],date=k[1],daily_open=r['open'],trimmed_first_open=x[0]['open'],daily_close=r['close'],trimmed_last_close=x[-1]['close'],open_equal=F(r['open'])==F(x[0]['open']),close_equal=F(r['close'])==F(x[-1]['close']),close_difference_pct=fstr(ret(x[-1]['close'],r['close'])),trimmed_volume=str(sum(F(v['volume']) for v in x)),daily_volume=r['volume']))
    check('14 overlapping days',len(overlap)==14)
    # Rebuild each R38/R39 row from raw inputs, not prior computed returns.
    stock={(r['symbol'],r['date']):r for r in source['prices']}; idx={(r['index'],r['date']):r for r in source['index']}; peers={(r['symbol'],r['date']):r for r in source['peers']}; cons={r['symbol']:r for r in source['cons']}; events={r['symbol']:(r['earnings_date'],r['next_session']) for r in source['events']}
    windows={}; tol=F(1,10**22)
    for r in source['r38']:
        s,a,b,af,bf=[r[k] for k in ('symbol','start_date','end_date','start_field','end_field')]; raw=ret(stock[s,a][af],stock[s,b][bf]); m=ret(idx['TOPIX',a][af],idx['TOPIX',b][bf]); g=ret(idx['TRANSPORT',a][af],idx['TRANSPORT',b][bf]); e=cons[s]; sur=ret(e['reported_latest_consensus'],e['actual']); key=s,r['window']; req(key not in windows,'duplicate window'); windows[key]=(a,b,af,bf,raw,m,g,sur)
        check('raw R38 '+str(key),all(abs(F(r[k])-v)<tol for k,v in [('stock_pct',raw),('topix_pct',m),('sector_pct',g),('stock_minus_sector_pp',raw-g),('surprise_pct',sur)]))
    for r in source['r39']:
        s,w=r['symbol'],r['window'];a,b,af,bf,raw,m,g,sur=windows[s,w];p=r['peers'].split(';'); clean=[k for k,v in events.items() if not any(a<=d<=b for d in v)]; mode=r['mode']; expected= list(events)[:2] if mode=='PARTS_ONLY' else list(events) if mode=='ALL_UNFILTERED' else clean if mode=='EARNINGS_EXCLUDED' else [k for k in clean if k!=mode.removeprefix('EXCLUDE_')]
        avg=sum(ret(peers[k,a][af],peers[k,b][bf]) for k in p)/len(p)
        check('raw R39 '+s+' '+w+' '+mode,set(p)==set(expected) and len(p)==len(set(p)) and abs(F(r['relative_pp'])-(raw-avg))<tol and int(r['match'])==(sign(raw-avg)==sign(sur)))
    # Timing diagnostic, separately pre-announcement and post-announcement.
    phases=[]
    for s in stock:
        pass
    for s in sorted({k[0] for k in stock}):
        e=cons[s]; initial=windows[s,'INITIAL']; overnight=windows[s,'REACTION_OVERNIGHT']; day=windows[s,'REACTION_OPEN_CLOSE']; after=e['release_jst'][11:] >= '15:30'; a,b,af,bf,raw,m,g,sur=overnight
        peer=next(r for r in source['r39'] if r['symbol']==s and r['window']=='REACTION_OVERNIGHT' and r['mode']=='EARNINGS_EXCLUDED'); daypeer=next(r for r in source['r39'] if r['symbol']==s and r['window']=='REACTION_OPEN_CLOSE' and r['mode']=='EARNINGS_EXCLUDED')
        phases.append(dict(symbol=s,name=e['name'],release_jst=e['release_jst'],reaction_date=b,surprise_pct=fstr(sur),gap_phase='POST_RELEASE' if after else 'PRE_RELEASE',gap_sector_pp=fstr(raw-g),gap_sector_match=sign(raw-g)==sign(sur),gap_peer_pp=peer['relative_pp'],gap_peer_match=bool(int(peer['match'])),day_phase='POST_RELEASE' if after else 'MIXED_PRE_POST',day_sector_pp=fstr(day[4]-day[6]),day_peer_pp=daypeer['relative_pp'],day_peer_match=bool(int(daypeer['match'])),initial_sector_match=sign(initial[4]-initial[6])==sign(sur),consensus_snapshot_verified=bool(e['consensus_snapshot_date']),receipt_verified=bool(e['receipt_jst'])))
    check('six timing cases',len(phases)==6);check('four distinct reaction dates',len({r['reaction_date'] for r in phases})==4)
    # Demonstrate actual validation gaps in old R39: internally consistent forged derived fields are accepted.
    old=runpy.run_path(str(paths['code39']));base=source['r38'];x=base[0]; orig=old['evaluate'](source['peers'],source['events'],base)
    for name,new in [('SURPRISE_SIGN_CHANGED',dict(x,surprise_pct=str(-D(x['surprise_pct'])))),('PRICE_AND_RETURN_CHANGED',dict(x,stock_end=str(D(x['stock_end'])*2),stock_pct=str((D(x['stock_end'])*2/D(x['stock_start'])-1)*100)))]:
        mutated=[new]+base[1:]
        try:result=old['evaluate'](source['peers'],source['events'],mutated)
        except ValueError: accepted=False
        else:accepted=result!=orig
        check('reproduce known input-validation gap '+name,accepted)
        findings.append(dict(issue=name,old_r39='ACCEPTED_CHANGED_DERIVED_INPUT',independent_audit='REJECT_BY_RAW_SOURCE_RECOMPUTATION',status='OPEN_R39_UNCHANGED'))
    check('all protected input hashes unchanged',before=={k:sha(p) for k,p in paths.items()})
    out.mkdir(exist_ok=False);write(out/'session_overlap.csv',overlap);write(out/'timing_audit.csv',phases);write(out/'validation_gaps.csv',findings);write(out/'tests.csv',tests)
    summary=dict(mode='RETROSPECTIVE_AUDIT_ONLY',checks=len(tests),r38_rows=len(source['r38']),r39_rows=len(source['r39']),session_overlap=len(overlap),open_differences=sum(not r['open_equal'] for r in overlap),close_differences=sum(not r['close_equal'] for r in overlap),max_abs_close_diff_pct=max(abs(float(r['close_difference_pct'])) for r in overlap),reaction_dates=len({r['reaction_date'] for r in phases}),pre_consensus_snapshots=sum(r['consensus_snapshot_verified'] for r in phases),verified_receipts=sum(r['receipt_verified'] for r in phases),timing_groups={g:dict(n=len(q),sector_gap_match=sum(r['gap_sector_match'] for r in q),peer_gap_match=sum(r['gap_peer_match'] for r in q),peer_day_match=sum(r['day_peer_match'] for r in q)) for g in ('PRE_RELEASE','POST_RELEASE') for q in [[r for r in phases if r['gap_phase']==g]]},protected=before,validation_gaps=len(findings),notes='Tests reproducing known weaknesses are not product passes. No corporate-action history verified, no new prices or trades, no parameter fitting.')
    (out/'manifest.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps({k:v for k,v in summary.items() if k!='protected'},ensure_ascii=False,indent=2))
if __name__=='__main__':main(Path(sys.argv[1]))
