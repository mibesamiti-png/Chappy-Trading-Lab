"""R41: protected input binding + same-clock placebo windows, retrospective only.
Run: python Chappy_Trading_Baseline_Audit_v0.1.py NEW_OUTPUT_DIR
No orders, no post-cutoff inputs, no modification of previous experiments.
"""
import csv, json, hashlib, runpy, sys, zipfile
from pathlib import Path
from fractions import Fraction as F
from decimal import Decimal as D
from datetime import datetime, timedelta, date
from collections import defaultdict
from statistics import median
P=Path(__file__).resolve().parent
R=runpy.run_path(str(P/'Chappy_Trading_Foundation_Audit_v0.1.py'))
paths=R['paths']; read=R['read']; write=R['write']; sha=R['sha']; req=R['req']; ret=R['ret']; sign=R['sign']; fmt=R['fstr']
M=runpy.run_path(str(paths['code38'])); B=runpy.run_path(str(paths['code39']))
SYMS=('6501.T','6758.T','7203.T','7267.T','8058.T','8306.T')
CUTOFF='2026-11-24'
def string_rows(rows):return [{k:str(v) for k,v in r.items()} for r in rows]
def bound_compare(prices,indices,cons,peers,events,claimed):
    generated=M['evaluate'](indices,prices,cons)
    req(string_rows(generated)==claimed,'derived R38 input differs from regenerated raw inputs')
    return B['evaluate'](peers,events,generated)
def load_bars():
    bars=defaultdict(dict); daykeys=defaultdict(set)
    with zipfile.ZipFile(paths['archive']) as z:
        for n in z.namelist():
            s=Path(n).name.split('_')[0]
            if not n.endswith('.csv') or s not in SYMS:continue
            for r in csv.DictReader(z.read(n).decode('utf-8-sig').splitlines()):
                t=datetime.fromisoformat(r['datetime']);d=t.date().isoformat(); end=t+timedelta(minutes=5)
                if d>CUTOFF:continue
                req(t not in daykeys[s], 'duplicate bar');daykeys[s].add(t)
                o,h,l,c=(F(r[k]) for k in ('open','high','low','close'))
                req(0<l<=min(o,c)<=max(o,c)<=h and F(r['volume'])>0,'invalid bar')
                bars[s,d][end.strftime('%H:%M')]=c
    expected={f'{h:02}:{m:02}' for h,m in [(9,m) for m in range(15,60,5)]+[(10,m) for m in range(0,60,5)]+[(11,m) for m in range(0,31,5)]+[(12,m) for m in range(35,60,5)]+[(h,m) for h in (13,14) for m in range(0,60,5)]+[(15,m) for m in range(0,26,5)]}
    req(len(expected)==63,'clock grid')
    complete={k:v for k,v in bars.items() if set(v)==expected}
    dates=sorted(set.intersection(*[{d for k,d in complete if k==s} for s in SYMS]))
    return complete,dates

def study(bars,dates,cons):
    # Calendar uses all observed complete dates, plus the one partially present 11/06;
    # never join over a missing session. Explicit calendar for this bounded archive.
    calendar=[str(date(2026,10,26)+timedelta(days=i)) for i in range(30) if (date(2026,10,26)+timedelta(days=i)).weekday()<5 and str(date(2026,10,26)+timedelta(days=i)) not in ('2026-11-03','2026-11-23')]
    req(calendar[-1]==CUTOFF,'calendar cutoff')
    event={r['symbol']:r for r in cons if r['symbol'] in SYMS}
    req(set(event)==set(SYMS),'missing event')
    blocked={}
    for s,r in event.items():
        d=r['release_jst'][:10];i=calendar.index(d);blocked[s]={d,calendar[i+1]}
    def has(s,a,b):return not any(a<=x<=b for x in blocked[s])
    def change(s,a,b,t0,t1):return ret(bars[s,a][t0],bars[s,b][t1])
    def measure(s,peers,a,b,t0,t1):
        own=change(s,a,b,t0,t1);p=sum((change(k,a,b,t0,t1) for k in peers),F(0))/len(peers)
        return own,p,own-p
    rows=[];summary=[]
    for s in SYMS:
        r=event[s];t=datetime.fromisoformat(r['release_jst']);a=t.date().isoformat();i=calendar.index(a)
        if t.hour>=15:
            b=calendar[i+1];t0,t1='15:25','09:15';kind='TRIMMED_OVERNIGHT'
        else:
            b=a;t0=(t-timedelta(minutes=5)).strftime('%H:%M');t1=(t+timedelta(minutes=5)).strftime('%H:%M');kind='RELEASE_5M_STRICT_PRE'
        peers=tuple(k for k in SYMS if k!=s and has(k,a,b) and (k,a) in bars and (k,b) in bars)
        req(len(peers)>=2,'too few peers')
        own,p,v=measure(s,peers,a,b,t0,t1)
        sur=ret(r['reported_latest_consensus'],r['actual']) if r['reported_latest_consensus'] else None
        # Same names and same endpoints, exclude known release day+next for target and all controls.
        controls=[]
        for j,x in enumerate(calendar):
            if kind=='TRIMMED_OVERNIGHT' and j+1==len(calendar):continue
            y=calendar[j+1] if kind=='TRIMMED_OVERNIGHT' else x
            if not all(has(k,x,y) and (k,x) in bars and (k,y) in bars for k in (s,*peers)):continue
            u,q,w=measure(s,peers,x,y,t0,t1);prior=y<a
            controls.append((x,y,w,prior))
            rows.append(dict(symbol=s,kind=kind,peers=';'.join(peers),start_date=x,end_date=y,start_bar_end=t0,end_bar_end=t1,stock_pct=fmt(u),peer_pct=fmt(q),relative_pp=fmt(w),before_event=prior,known_earnings_excluded=True))
        pre=[w for x,y,w,p in controls if p];allv=[w for x,y,w,p in controls]
        summary.append(dict(symbol=s,name=r['name'],kind=kind,release_jst=r['release_jst'],start_date=a,end_date=b,start_bar_end=t0,end_bar_end=t1,peers=';'.join(peers),stock_pct=fmt(own),peer_pct=fmt(p),relative_pp=fmt(v),surprise_pct=fmt(sur) if sur is not None else '',direction_match=sign(v)==sign(sur) if sur is not None else '',prior_n=len(pre),prior_abs_ge=sum(abs(w)>=abs(v) for w in pre),prior_median_abs_pp=fmt(median(map(abs,pre))) if pre else '',all_n=len(allv),all_abs_ge=sum(abs(w)>=abs(v) for w in allv),all_median_abs_pp=fmt(median(map(abs,allv))) if allv else '',event_larger_than_all_prior=bool(pre) and all(abs(v)>abs(w) for w in pre)))
    return rows,summary

def main(out):
    expected=json.loads((P/'Trading_Round40_Foundation_Audit/manifest.json').read_text())['protected']
    before={k:sha(p) for k,p in paths.items()};req(before==expected,'R40 input digest changed')
    tests=[]
    def check(n,b):req(b,n);tests.append(dict(test=n,result='PASS'))
    src={k:read(paths[k]) for k in ('cons','prices','index','peers','events','r38','r39')}
    args=[src[k] for k in ('prices','index','cons','peers','events','r38')]
    check('R40 protected digests',before==expected)
    regenerated=bound_compare(*args);check('149 exact regenerated R39 rows',string_rows(regenerated)==src['r39'])
    for name,patch in [('surprise sign',{'surprise_pct':str(-D(src['r38'][0]['surprise_pct']))}),('price and return',{'stock_end':str(D(src['r38'][0]['stock_end'])*2),'stock_pct':str((D(src['r38'][0]['stock_end'])*2/D(src['r38'][0]['stock_start'])-1)*100)}),('window time',{'start_field':'open'}),('source label',{'name':'OTHER'}),('tradable flag',{'tradable':'True'})]:
        claimed=[dict(src['r38'][0],**patch)]+src['r38'][1:]
        try:bound_compare(*args[:-1],claimed)
        except ValueError:check('reject '+name,True)
        else:raise ValueError('accepted '+name)
    bars,dates=load_bars();check('19 common complete dates',len(dates)==19)
    rows,summ=study(bars,dates,src['cons']);check('six event windows',len(summ)==6)
    check('all control dates pre pilot',all(r['end_date']<=CUTOFF for r in rows+summ))
    check('nonempty matched controls',all(r['all_n']>0 for r in summ))
    for r in summ:
        q=[x for x in rows if x['symbol']==r['symbol']];check('counts and same basket '+r['symbol'],len(q)==r['all_n'] and sum(x['before_event'] for x in q)==r['prior_n'] and all(x['peers']==r['peers'] and x['start_bar_end']==r['start_bar_end'] and x['end_bar_end']==r['end_bar_end'] for x in q));
        v=abs(D(r['relative_pp']));check('absolute rank '+r['symbol'],sum(abs(D(x['relative_pp']))>=v for x in q)==r['all_abs_ge'] and sum(abs(D(x['relative_pp']))>=v and x['before_event'] for x in q)==r['prior_abs_ge'])
        # independent Decimal arithmetic, not relying on prior relative result
        a,b,t0,t1=(r[k] for k in ('start_date','end_date','start_bar_end','end_bar_end'));p=r['peers'].split(';')
        dec=lambda k:(D(fmt(bars[k,b][t1]))/D(fmt(bars[k,a][t0]))-1)*100
        check('independent event '+r['symbol'],abs(dec(r['symbol'])-sum(map(dec,p))/D(len(p))-D(r['relative_pp']))<D('1e-23'))
    check('unchanged protected inputs',before=={k:sha(p) for k,p in paths.items()})
    out.mkdir(exist_ok=False);write(out/'baseline_windows.csv',rows);write(out/'event_comparison.csv',summ);write(out/'tests.csv',tests)
    meta=dict(mode='RETROSPECTIVE_ONLY',protected=before,checks=len(tests),event_count=len(summ),control_windows=len(rows),common_complete_days=len(dates),note='Convenience selected six existing archive symbols; event-specific fixed basket, known six release day and next excluded for all constituents. Other news and corporate actions not checked. All-period controls may occur after event, descriptive only; prior samples small. No inference, trading, beta fitting or protected period usage. Overnight endpoints are trimmed 15:25 and 09:15, not exchange close/open.')
    (out/'manifest.json').write_text(json.dumps(meta,indent=2),encoding='utf8');print(json.dumps({k:v for k,v in meta.items() if k!='protected'},ensure_ascii=False));print(*summ,sep='\n')
if __name__=='__main__':main(Path(sys.argv[1]))
