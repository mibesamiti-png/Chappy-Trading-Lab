# -*- coding: utf-8 -*-
"""Known-data relative return diagnostics; no orders, ranking for deployment or pilot evaluation.
Usage: python Chappy_Trading_Relative_Study_v0.1.py CTRL.zip output_dir
Requires Signal Study v0.1, Research Lab v0.5.0 and RC1 beside this file.
"""
import argparse, csv, hashlib, importlib.util, json, math, statistics as st, sys, tempfile, zipfile
from collections import defaultdict
from pathlib import Path
P=Path(__file__).with_name('Chappy_Trading_Signal_Study_v0.1.py')
spec=importlib.util.spec_from_file_location('signal01',P); s=importlib.util.module_from_spec(spec);sys.modules[spec.name]=s;spec.loader.exec_module(s)
r=s.r
PLAN='d8aa0763f62a091742dba1cfbbb2d7b9ec19dd66c857d0f2a846536ea3aacac8'
ARCHIVE='b8bd4e8d9aacbba177c9d7380310b81ac31b9d245d6d1ceecfb9e495b2b493c6'
RULES=('ALL','rsi_rebound','momentum_up','relative_weak_loo','relative_strong_loo','rebound_weak','rebound_neutral','rebound_strong','rebound_peer_up','rebound_peer_nonup')
def load(path):
    if hashlib.sha256(path.read_bytes()).hexdigest()!=ARCHIVE:raise ValueError('Only the frozen known archive is accepted')
    with tempfile.TemporaryDirectory() as tmp,zipfile.ZipFile(path) as z:
        files=[n for n in z.namelist() if n.startswith('market_') and n.count('/')==1 and n.endswith('.csv')]
        report=json.loads(z.read(next(n for n in z.namelist() if n.endswith('/acquisition_report.json')))); hashes={e['csv']:e['sha256'] for e in report['entries'] if e['status']=='ok'}; paths=[]
        for n in files:
            dest=Path(tmp)/Path(n).name; raw=z.read(n)
            if hashlib.sha256(raw).hexdigest()!=hashes.get(dest.name):raise ValueError('CSV hash mismatch')
            dest.write_bytes(raw);dest.with_suffix('.json').write_bytes(z.read(n[:-4]+'.json'));paths.append(dest)
        data=r.market_inputs(paths)
    dates=sorted(set.intersection(*(set(v) for v in data.values())))
    if len(dates)!=19 or tuple(sorted(data))!=r.PILOT_SYMBOLS or any(d>= '2026-11-26' for v in data.values() for d in v):raise ValueError('Known dataset only')
    if r.pilot_plan_hash()!=PLAN:raise ValueError('Frozen pilot plan changed')
    return data,dates

def peer_mean(values,k):
    peers=[v for sym,v in values.items() if sym!=k]
    if len(peers)!=5:raise ValueError('Exactly five peers required')
    return st.mean(peers)

def enrich(data,dates):
    rows,checks=s.observations(data,dates); group=defaultdict(list)
    common={(x['symbol'],x['decision']) for x in rows if x['horizon']==12}
    # Every stock has the same 60-minute feasible timestamps; retain identical cohorts for all horizons.
    for x in rows:
        if (x['symbol'],x['decision']) in common:group[(x['decision'],x['horizon'])].append(x)
    past={}
    for d in dates:
        ser={k:v[d] for k,v in data.items()}; first=next(iter(ser.values()))
        for i in range(6,len(first)):
            ts=first[i].ts.isoformat()
            if (next(iter(ser)),ts) in common:
                ret={k:100*(v[i].c/v[i-6].c-1) for k,v in ser.items()}
                past[ts]=ret
    out=[]; prefix_checks=0
    for (ts,h),items in sorted(group.items()):
        assert len(items)==6 and len({x['symbol'] for x in items})==6
        assert len({(x['entry'],x['exit']) for x in items})==1
        gross={x['symbol']:x['gross_pct'] for x in items}; net={x['symbol']:x['net_pct'] for x in items}; stress={x['symbol']:x['stress_pct'] for x in items}
        assert abs(sum(gross[k]-peer_mean(gross,k) for k in gross))<1e-10
        for x in items:
            k=x['symbol']; p=past[ts]; peer_p=peer_mean(p,k); rel=p[k]-peer_p
            # All rule features use historical returns only; peer future returns are descriptive outcome labels.
            weak=rel<-.2; strong=rel>.2; reb=x['rsi_rebound']
            flags=dict(relative_weak_loo=weak,relative_strong_loo=strong,rebound_weak=reb and weak,rebound_neutral=reb and not weak and not strong,rebound_strong=reb and strong,rebound_peer_up=reb and peer_p>0,rebound_peer_nonup=reb and peer_p<=0)
            assert sum(flags[a] for a in ('rebound_weak','rebound_neutral','rebound_strong'))==int(reb)
            assert sum(flags[a] for a in ('rebound_peer_up','rebound_peer_nonup'))==int(reb)
            peer_g=peer_mean(gross,k); peer_n=peer_mean(net,k); peer_s=peer_mean(stress,k)
            y=dict(**x,past_own_pct=p[k],past_peer_pct=peer_p,past_relative_pct=rel,peer_gross_pct=peer_g,peer_net_pct=peer_n,peer_stress_pct=peer_s,excess_gross_pct=x['gross_pct']-peer_g,excess_net_pct=x['net_pct']-peer_n,excess_stress_pct=x['stress_pct']-peer_s,**flags)
            assert math.isclose(y['net_pct'],peer_n+y['excess_net_pct'],abs_tol=1e-10)
            out.append(y)
    # Independent past-feature reconstruction using explicit prefixes; future changes cannot affect flags.
    for ts,p in past.items():
        d=ts[:10]
        for k,ds in data.items():
            v=[b for b in ds[d] if b.ts.isoformat()<=ts]
            assert len(v)>=7 and abs(p[k]-100*(v[-1].c/v[-7].c-1))<1e-10
            prefix_checks+=1
    return out,checks,prefix_checks

def summarize(rows,dates):
    blocks={'all':set(dates),'early':set(dates[:6]),'middle':set(dates[6:12]),'late':set(dates[12:])};out=[]; daily=[]
    for h in s.HORIZONS:
        for rule in RULES:
            for period,ds in blocks.items():
                sub=[x for x in rows if x['horizon']==h and x['day'] in ds and (rule=='ALL' or x[rule])]
                if not sub:continue
                days=defaultdict(list)
                for x in sub:days[x['day']].append(x)
                keys=('gross_pct','net_pct','stress_pct','peer_net_pct','excess_net_pct')
                av=lambda a,key:st.mean(x[key] for x in a)
                dn={d:{key:av(v,key) for key in keys} for d,v in days.items()}
                def worst(key):return min((st.mean(v[key] for k,v in dn.items() if k!=d) for d in dn),default=None) if len(dn)>1 else None
                out.append(dict(rule=rule,horizon=h,period=period,n=len(sub),days=len(days),symbols=len({x['symbol'] for x in sub}),**{key:av(sub,key) for key in keys},beat_peer_pct=100*sum(x['excess_net_pct']>0 for x in sub)/len(sub),equal_day_net_pct=st.mean(v['net_pct'] for v in dn.values()),equal_day_excess_pct=st.mean(v['excess_net_pct'] for v in dn.values()),worst_leave_day_net_pct=worst('net_pct'),worst_leave_day_excess_pct=worst('excess_net_pct')))
                if period=='all':daily.extend(dict(rule=rule,horizon=h,day=d,n=len(days[d]),**v) for d,v in dn.items())
    return out,daily

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('archive',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
    assert peer_mean(dict.fromkeys('abcdef',2.0),'a')==2 and peer_mean(dict(a=100,b=1,c=1,d=1,e=1,f=1),'a')==1
    data,dates=load(a.archive);rows,checks,prefix=enrich(data,dates);summary,daily=summarize(rows,dates)
    assert len(rows)==5472 and prefix==1824
    a.output.mkdir(exist_ok=False)
    for name,v in [('relative_events.csv',rows),('relative_summary.csv',summary),('relative_daily.csv',daily)]:r.core.write_new_csv(a.output/name,list(v[0]),v)
    m=dict(mode='KNOWN_RELATIVE_DIAGNOSTIC_ONLY',archive_sha256=ARCHIVE,pilot_plan_sha256=PLAN,dates=dates,observations=len(rows),original_prefix_checks=checks,relative_prefix_checks=prefix,benchmark='equal-weight five other stocks, same entry/exit; not market index or tradable hedge',notes='Future peer returns are labels only. Overlapping events; no independent-trade or live-performance claims. No strategy changes.')
    (a.output/'manifest.json').write_text(json.dumps(m,indent=2),encoding='utf-8')
    print(json.dumps(m,indent=2))
if __name__=='__main__':main()
