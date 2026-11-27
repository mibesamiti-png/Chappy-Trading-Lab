# -*- coding: utf-8 -*-
"""Known-period event study only. No strategies, orders, or prospective data.
Usage: python Chappy_Trading_Signal_Study_v0.1.py CTRL.zip output_dir
Requires Research Lab v0.5.0 and its RC1 dependency beside this file.
"""
import argparse, csv, hashlib, importlib.util, json, math, statistics as st, sys, tempfile, zipfile
from collections import defaultdict
from pathlib import Path
R=Path(__file__).with_name('Chappy_Trading_Research_Lab_v0.5.0.py')
spec=importlib.util.spec_from_file_location('research05',R); r=importlib.util.module_from_spec(spec);sys.modules[spec.name]=r;spec.loader.exec_module(r)
CUTOFF='2026-11-25'; HORIZONS=(3,6,12)
RULES=('rsi_low','rsi_high','rsi_rebound','rsi_rollover','momentum_down','momentum_up','high_volume','wide_range','close_near_low','close_near_high','breadth_down','breadth_up','relative_weak','relative_strong','rebound_breadth_up','rebound_breadth_down')
def session(b): return 'AM' if b.ts.hour<12 else 'PM'
def features(series,i):
    # All inputs stop at decision bar i. Shared timestamps verified by caller.
    ret={k:v[i].c/v[i-6].c-1 for k,v in series.items()}; breadth=sum(x>0 for x in ret.values()); med=st.median(ret.values()); out={}
    for k,v in series.items():
        b=v[i]; rr=r.core.rsi([x.c for x in v[:i+1]],14); prev=rr[-2]; now=rr[-1]; ch=b.c/v[i-1].c-1
        avgvol=st.mean(x.v for x in v[i-10:i]); avgspan=st.mean((x.h-x.l)/x.c for x in v[i-10:i]); span=(b.h-b.l)/b.c
        loc=(b.c-b.l)/(b.h-b.l) if b.h>b.l else .5
        rebound=prev<30 and ch>0
        out[k]=dict(zip(RULES,(now<30,now>70,rebound,prev>70 and ch<0,ret[k]<-.003,ret[k]>.003,b.v>1.5*avgvol,span>1.5*avgspan,loc<.2,loc>.8,breadth<=2,breadth>=5,ret[k]<med-.002,ret[k]>med+.002,rebound and breadth>=5,rebound and breadth<=2)))
    return out

def observations(data,dates):
    rows=[]; tested=0
    for d in dates:
        series={k:v[d] for k,v in data.items()}; first=next(iter(series.values())); stamps=[b.ts for b in first]
        assert all([b.ts for b in v]==stamps for v in series.values())
        for i in range(15,len(first)-1):
            # No return across lunch for momentum, entry, or measurement horizon.
            if session(first[i-6])!=session(first[i]):continue
            hs=[h for h in HORIZONS if i+1+h<len(first) and session(first[i])==session(first[i+1+h])]
            if not hs:continue
            f=features(series,i); assert f==features({k:v[:i+1] for k,v in series.items()},i); tested+=len(series)
            for k,v in series.items():
                for h in hs:
                    a,b=v[i+1].c,v[i+1+h].c; gross=b/a-1
                    # Exact proportional round-trip model, no lot sizing or portfolio simulation.
                    net=lambda c: b*(1-c)**2/(a*(1+c)**2)-1
                    rows.append(dict(day=d,symbol=k,session=session(v[i]),decision=v[i].ts.isoformat(),entry=v[i+1].ts.isoformat(),exit=v[i+1+h].ts.isoformat(),horizon=h,gross_pct=100*gross,net_pct=100*net(.0005),stress_pct=100*net(.001),**f[k]))
    return rows,tested

def summarize(rows,dates):
    blocks={'all':set(dates),'early':set(dates[:6]),'middle':set(dates[6:12]),'late':set(dates[12:])}; out=[]; daily=[]
    for h in HORIZONS:
        hh=[x for x in rows if x['horizon']==h]; groups=defaultdict(list)
        for x in hh:groups[(x['day'],x['symbol'],x['session'])].append(x['net_pct'])
        base={k:st.mean(v) for k,v in groups.items()}
        for rule in ('ALL',)+RULES:
            matched=[x for x in hh if rule=='ALL' or x[rule]]
            for period,ds in blocks.items():
                sub=[x for x in matched if x['day'] in ds]; day=defaultdict(list)
                for x in sub:day[x['day']].append(x)
                if not sub:continue
                gross=st.mean(x['gross_pct'] for x in sub); net=st.mean(x['net_pct'] for x in sub); stress=st.mean(x['stress_pct'] for x in sub)
                exc={d:st.mean(x['net_pct']-base[(x['day'],x['symbol'],x['session'])] for x in v) for d,v in day.items()}
                dn={d:st.mean(x['net_pct'] for x in v) for d,v in day.items()}
                out.append(dict(rule=rule,horizon=h,period=period,n=len(sub),days=len(day),symbols=len(set(x['symbol'] for x in sub)),gross_pct=gross,net_pct=net,stress_pct=stress,positive_pct=100*sum(x['net_pct']>0 for x in sub)/len(sub),matched_excess_pct=st.mean(x['net_pct']-base[(x['day'],x['symbol'],x['session'])] for x in sub),equal_day_net_pct=st.mean(dn.values()),equal_day_excess_pct=st.mean(exc.values()),positive_days=sum(x>0 for x in dn.values()),positive_excess_days=sum(x>0 for x in exc.values()),worst_leave_day_net_pct=min((st.mean(v for k,v in dn.items() if k!=d) for d in dn),default=None) if len(dn)>1 else None))
                if period=='all':
                    daily.extend(dict(rule=rule,horizon=h,day=d,n=len(day[d]),net_pct=dn[d],matched_excess_pct=exc[d]) for d in day)
    return out,daily

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('archive',type=Path);p.add_argument('output',type=Path);args=p.parse_args()
    # Read only the six CSV/metadata pairs, never execute archive content.
    with tempfile.TemporaryDirectory() as tmp,zipfile.ZipFile(args.archive) as z:
        files=[n for n in z.namelist() if n.startswith('market_') and n.count('/')==1 and n.endswith('.csv')];assert len(files)==6
        reports=[n for n in z.namelist() if n.endswith('/acquisition_report.json')]; assert len(reports)==1
        report=json.loads(z.read(reports[0])); hashes={e['csv']:e['sha256'] for e in report['entries'] if e['status']=='ok'}; paths=[]
        for n in files:
            dest=Path(tmp)/Path(n).name; raw=z.read(n)
            if hashlib.sha256(raw).hexdigest()!=hashes.get(dest.name):raise ValueError('取得報告とのハッシュ不一致: '+dest.name)
            dest.write_bytes(raw);dest.with_suffix('.json').write_bytes(z.read(n[:-4]+'.json'));paths.append(dest)
        data=r.market_inputs(paths)
    if any(d>CUTOFF for v in data.values() for d in v):raise ValueError('固定対戦期間のデータは探索に使用しない')
    dates=sorted(set.intersection(*(set(v) for v in data.values())))
    if len(dates)!=19 or tuple(sorted(data))!=r.PILOT_SYMBOLS:raise ValueError('第1回既知データ6銘柄19日のみ対応')
    rows,tests=observations(data,dates); summary,daily=summarize(rows,dates)
    common_keys={(x['symbol'],x['decision']) for x in rows if x['horizon']==max(HORIZONS)}
    common=[x for x in rows if (x['symbol'],x['decision']) in common_keys]; common_summary,_=summarize(common,dates)
    assert len(common)==len(common_keys)*len(HORIZONS)
    assert len({(x['symbol'],x['decision'],x['horizon']) for x in rows})==len(rows)
    assert all(x['stress_pct']<x['net_pct']<x['gross_pct'] for x in rows)
    args.output.mkdir(exist_ok=False)
    for name,items in [('events.csv',rows),('summary.csv',summary),('daily.csv',daily),('common_horizon_summary.csv',common_summary)]:r.core.write_new_csv(args.output/name,list(items[0]),items)
    manifest=dict(mode='KNOWN_EVENT_STUDY_ONLY',dates=dates,horizons=HORIZONS,rules=RULES,archive_sha256=hashlib.sha256(args.archive.read_bytes()).hexdigest(),data_fingerprints={k:r.core.fingerprint([b for d in dates for b in v[d]]) for k,v in data.items()},pilot_plan_sha256=r.pilot_plan_hash(),observations=len(rows),common_horizon_observations=len(common),common_decisions=len(common_keys),prefix_checks=tests,notes='Overlapping hypothetical returns, not independent trades. Baseline matched by day/symbol/session uses future outcomes only for descriptive analysis. No capital allocation or trade execution. No prospective evaluation.')
    (args.output/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(manifest,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
