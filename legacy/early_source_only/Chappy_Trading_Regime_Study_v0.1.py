"""Known data only: descriptive regime diagnostics, not deployable strategies.
Usage: python Chappy_Trading_Regime_Study_v0.1.py CTRL.zip NEW_DIR
Uses Round21 MIXED / 15min / 2x results and independently reconstructed signals.
"""
import csv, hashlib, importlib.util, json, math, statistics as st, sys
from pathlib import Path
from collections import defaultdict
P=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('regime_hist',P/'Chappy_Trading_History_Study_v0.1.py');h=importlib.util.module_from_spec(s);sys.modules[s.name]=h;s.loader.exec_module(h)
m,r,ls=h.m,h.r,h.ls
FEATURES=('market_rms_5m_pct','market_mean_30m_pct','dispersion_30m_pp','mean_correlation','market_volume_ratio','own_volume_ratio','own_adverse_excursion_pct')
RULES=('LONG_REBOUND','SHORT_REVERSAL');LAG=900;COST=.001

def read(path):
    with path.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def clock(b):return (b.ts.hour*60+b.ts.minute-550)*60+300
def corr(a,b):
    ma,mb=st.mean(a),st.mean(b);x=[v-ma for v in a];y=[v-mb for v in b];den=math.sqrt(sum(v*v for v in x)*sum(v*v for v in y));return sum(u*v for u,v in zip(x,y))/den if den else None

def context(local,side):
    ret={k:[100*(b.c/a.c-1) for a,b in zip(v,v[1:])] for k,v in local.items()}
    ret30={k:100*(v[-1].c/v[0].c-1) for k,v in local.items()};ks=sorted(local)
    cs=[corr(ret[k],ret[j]) for i,k in enumerate(ks) for j in ks[i+1:]];cs=[x for x in cs if x is not None]
    market=dict(market_rms_5m_pct=math.sqrt(st.mean(x*x for v in ret.values() for x in v)),market_mean_30m_pct=st.mean(ret30.values()),dispersion_30m_pp=st.pstdev(ret30.values()),mean_correlation=st.mean(cs) if cs else None)
    own={k:dict(volume=sum(b.v for b in v[1:]),own_adverse_excursion_pct=100*(1-v[-1].c/max(b.h for b in v)) if side==1 else 100*(v[-1].c/min(b.l for b in v)-1)) for k,v in local.items()}
    return market,own,ret30

def main():
    data,dates=m.rel.load(Path(sys.argv[1]));out=Path(sys.argv[2]);out.mkdir(exist_ok=False)
    root=P/'Trading_Round21_History';protected={x:hashlib.sha256((P/x).read_bytes()).hexdigest() for x in ['Trading_Prospective_Plan_01.json','Chappy_Trading_Lab_v1.1.0-rc1.py','Chappy_Trading_Research_Lab_v0.5.0.py','Chappy_Trading_History_Study_v0.1.py','Trading_Round21_History/signals.csv','Trading_Round21_History/fills.csv','Trading_Round21_History/daily.csv']}
    old={(x['rule'],x['day'],int(x['end'])):x for x in read(root/'signals.csv') if x['mode']=='MIXED' and x['lag_min']=='15' and json.loads(x['candidate'])}
    raw={d:{k:{clock(b):b for b in data[k][d]} for k in m.SYMS} for d in dates}
    prior=defaultdict(list);signals=[];contexts=[];matched=set();prefix=0
    for d in dates:
        current=[]
        for a,z in r.WINDOWS:
            for t in range(a+2100,z-LAG-1,300):
                # All seven completed local bars observed by t+901; older session bars only if previously confirmed.
                local={k:[raw[d][k][u] for u in range(t-1800,t+1,300)] for k in m.SYMS}
                hist={k:[b for u,b in sorted(raw[d][k].items()) if u<=t and any(A<u<=Z and u+LAG+1<Z for A,Z in r.WINDOWS)] for k in m.SYMS}
                if min(map(len,hist.values()))<16:continue
                for rule,side in zip(RULES,(1,-1)):
                    market,own,ret=context(local,side)
                    prev=prior[rule,t];n=len(prev)
                    def ratio(k):
                        v=[p['own'][k]['volume'] for p in prev];return own[k]['volume']/st.median(v) if n>=5 else None
                    ratios={k:ratio(k) for k in m.SYMS};market['market_volume_ratio']=st.mean(ratios.values()) if n>=5 else None
                    ft={k:(h.independent([b.c for b in hist[k][:-1]]),local[k][-1].c/local[k][-2].c-1,st.mean(ret[j] for j in m.SYMS if j!=k),0,ret[k],sum(ret[j]>0 for j in m.SYMS if j!=k)) for k in m.SYMS}
                    chosen=ls.choose(ft,rule);key=(rule,d,t);assert bool(chosen)==(key in old),(key,chosen,old.get(key))
                    current.append((rule,t,dict(market=market,own=own)))
                    # independent prefix check: recompute from raw bar stream restricted to observation cutoff.
                    local2={k:[b for b in data[k][d] if t-1800<=clock(b)<=t and clock(b)+LAG+1<=t+LAG+1] for k in m.SYMS}
                    assert context(local2,side)==context(local,side);prefix+=1
                    if not chosen:continue
                    assert [list(x) for x in chosen]==json.loads(old[key]['candidate']);matched.add(key)
                    k=chosen[0][0];entry=t+LAG+300;exit=entry+1800
                    row=dict(rule=rule,day=d,end=t,received=t+LAG+1,symbol=k,side=side,prior_days=n,status=old[key]['status'],rsi=ft[k][0],**market,own_volume_ratio=ratios[k],own_adverse_excursion_pct=own[k]['own_adverse_excursion_pct'],own_30m_pct=ret[k],peer_30m_pct=ft[k][2],entry=entry,exit_30m=exit)
                    # Reference values only earlier days at the same clock; not fitted to returns.
                    for feat in FEATURES:
                        if feat=='own_volume_ratio' or feat=='market_volume_ratio':threshold=1 if n>=5 else None
                        elif feat=='own_adverse_excursion_pct':threshold=st.median(p['own'][k][feat] for p in prev) if n>=5 else None
                        else:
                            vs=[p['market'][feat] for p in prev if p['market'][feat] is not None];threshold=st.median(vs) if len(vs)>=5 else None
                        row[feat+'_reference']=threshold;row[feat+'_group']='UNKNOWN' if threshold is None or row[feat] is None else ('HIGH' if row[feat]>=threshold else 'LOW')
                    row['net_30m_pct']=None
                    if entry<z-r.EXIT_LEAD and exit<z-r.EXIT_LEAD and entry in raw[d][k] and exit in raw[d][k]:
                        a0=raw[d][k][entry].c;b0=raw[d][k][exit].c;ap=a0*(1+side*COST);bp=b0*(1-side*COST)
                        row['net_30m_pct']=100*(side*(bp-ap)-COST*(ap+bp)-(a0*.0002 if side==-1 else 0))/a0
                    signals.append(row)
        for rule,t,rec in current:prior[rule,t].append(rec)
    assert matched==set(old),(set(old)-matched,matched-set(old))
    # Link actual Round21 single-leg fills; no hypothetical filtering or capital reallocation.
    ff=[x for x in read(root/'fills.csv') if x['mode']=='MIXED' and x['lag_min']=='15' and x['cost']=='2'];lookup={(x['rule'],x['day'],x['symbol'],x['entry']):x for x in signals};active={};trades=[]
    for x in ff:
        key=x['rule'],x['day'];ts=int(x['ts']);k=x['symbol'];assert float(x['raw'])==raw[x['day']][k][ts].c
        if x['action']=='OPEN':assert key not in active;active[key]=x
        else:
            op=active.pop(key);assert op['symbol']==k and op['qty']==x['qty'] and op['side']==x['side'];row=lookup[(*key,k,int(op['ts']))];assert row['status']=='INTENT';pnl=float(x['delta'])+float(op['delta']);assert math.isclose(pnl,float(x['net']),abs_tol=1e-7);trades.append(dict(**row,actual_exit=ts,actual_pnl=pnl,actual_gross=float(x['gross']),actual_qty=int(x['qty'])))
    assert not active
    ds=[x for x in read(root/'daily.csv') if x['mode']=='MIXED' and x['lag_min']=='15' and x['cost']=='2']
    for x in ds:assert math.isclose(sum(t['actual_pnl'] for t in trades if t['day']==x['day'] and t['rule']==x['rule']),float(x['pnl']),abs_tol=1e-7)
    summary=[]
    for rule in RULES:
        for cohort,col in ((signals,'net_30m_pct'),(trades,'actual_pnl')):
            for feat in ('ALL',*FEATURES):
                for group in (('ALL',) if feat=='ALL' else ('HIGH','LOW','UNKNOWN')):
                    xs=[x for x in cohort if x['rule']==rule and x[col] is not None and (feat=='ALL' or x[feat+'_group']==group)]
                    if not xs:continue
                    per=defaultdict(list)
                    for x in xs:per[x['day']].append(x[col])
                    avg=st.mean(x[col] for x in xs);davg=st.mean(st.mean(v) for v in per.values());loo=[st.mean(st.mean(v) for k,v in per.items() if k!=d) for d in per if len(per)>1]
                    summary.append(dict(rule=rule,cohort=col,feature=feat,group=group,n=len(xs),days=len(per),mean=avg,total=sum(x[col] for x in xs),day_equal_mean=davg,worst_leave_day_mean=min(loo) if loo else None,without_nov4_sum=sum(x[col] for x in xs if x['day']!='2026-11-04')))
    for name,rows in [('signals',signals),('trades',trades),('summary',summary)]:m.write(out/(name+'.csv'),rows)
    assert protected=={x:hashlib.sha256((P/x).read_bytes()).hexdigest() for x in protected}
    report=dict(signal_matches=len(matched),prefix_checks=prefix,actual_trades=len(trades),daily_checks=len(ds),fixed_30m_events=sum(x['net_30m_pct'] is not None for x in signals),protected_sha=protected,notes='Exploratory descriptors only. Prior reference same clock from >=5 earlier known dates; volume ratios against prior median; correlation six 5m returns, noisy. Market only six symbols. OHLC extrema assumed available with delayed bar. Actual subset accounting is not a filtered portfolio replay; fixed horizon events overlap. No threshold fitting, unknown dates, or new trades.')
    (out/'manifest.json').write_text(json.dumps(report,indent=2));print(report)
if __name__=='__main__':main()
