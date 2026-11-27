# -*- coding: utf-8 -*-
"""Known-data single-position portfolio experiment; no live orders or prospective evaluation.
Usage: python Chappy_Trading_Portfolio_Study_v0.1.py CTRL.zip output_dir
Requires Relative Study v0.1 and its dependencies in the same folder.
"""
import argparse, importlib.util, sys, json, math, statistics as st, hashlib
from pathlib import Path
p=Path(__file__).with_name('Chappy_Trading_Relative_Study_v0.1.py')
spec=importlib.util.spec_from_file_location('relative01',p); rel=importlib.util.module_from_spec(spec);sys.modules[spec.name]=rel;spec.loader.exec_module(rel)
r=rel.r
RULES=('NO_TRADE','ALL_MOMENTUM','REBOUND_LOW_RSI','REBOUND_PEER_UP','REBOUND_PEER_UP_RELATIVE','REBOUND_PEER_UP_BREADTH')
CAPITAL=1_000_000.; LOT=100; HOLD=12

def features(series,i):
    ret={k:100*(v[i].c/v[i-6].c-1) for k,v in series.items()};out={}
    for k,v in series.items():
        prev=r.core.rsi([b.c for b in v[:i]],14)[-1]; ch=v[i].c/v[i-1].c-1; peer=rel.peer_mean(ret,k)
        out[k]=(prev,ch,peer,ret[k]-peer,ret[k],sum(x>0 for a,x in ret.items() if a!=k))
    return out

def select(f,rule):
    if rule=='NO_TRADE':return None
    if rule=='ALL_MOMENTUM':return min(f,key=lambda k:(-f[k][4],k))
    candidates=[k for k,(prev,ch,peer,excess,mom,breadth) in f.items() if prev<30 and ch>0 and (rule=='REBOUND_LOW_RSI' or peer>0) and (rule!='REBOUND_PEER_UP_BREADTH' or breadth>=3)]
    if not candidates:return None
    if rule=='REBOUND_PEER_UP_RELATIVE':return min(candidates,key=lambda k:(-f[k][3],k))
    return min(candidates,key=lambda k:(f[k][0],k))

def prepare(data,dates):
    cache={}; checks=0
    for d in dates:
        series={k:v[d] for k,v in data.items()}; first=next(iter(series.values())); stamps=[b.ts for b in first]
        assert all([b.ts for b in v]==stamps for v in series.values()); eligible={}
        for i in range(15,len(first)-HOLD-2):
            # Identical eligible decision times for both execution models; no lunch crossing.
            if rel.s.session(first[i-6])!=rel.s.session(first[i+2+HOLD]):continue
            f=features(series,i);assert f==features({k:v[:i+1] for k,v in series.items()},i);checks+=len(f)
            eligible[i]=f
        cache[d]=(series,eligible)
    return cache,checks

def simulate(cache,dates,rule,mult,delay):
    cash=CAPITAL; daily=[]; trades=[]; dd=0.; peak=cash; cost=.0005*mult
    for d in dates:
        series,eligible=cache[d]; before=cash; next_allowed=-1; position=None; pending=None; first=next(iter(series.values())); n=0
        for i in range(len(first)):
            if pending is not None and i==pending[1]:
                k,entry,exit,qty,decision=pending;pending=None
                buy=series[k][i].c;spent=qty*buy*(1+cost)**2
                if spent<=cash:
                    cash-=spent;position=(k,entry,exit,qty,buy,spent,decision);next_allowed=exit
            if position is not None:
                k,entry,exit,qty,buy,spent,decision=position
                if entry<=i<=exit:
                    mark=series[k][i].c*(1-cost)**2*qty
                    equity=cash+mark;peak=max(peak,equity);dd=max(dd,1-equity/peak)
                if i==exit:
                    raw_sell=series[k][i].c; received=raw_sell*(1-cost)**2*qty;cash+=received
                    raw_buy=series[k][entry].c; gross=(raw_sell-raw_buy)*qty
                    trades.append(dict(rule=rule,mult=mult,delay=delay,day=d,symbol=k,decision=first[decision].ts.isoformat(),entry=first[entry].ts.isoformat(),exit=first[exit].ts.isoformat(),qty=qty,raw_buy=raw_buy,raw_sell=raw_sell,spent=spent,received=received,gross=gross,cost=gross-(received-spent),net=received-spent,cash=cash));position=None;n+=1
            if position is None and pending is None and i>=next_allowed and i in eligible:
                k=select(eligible[i],rule)
                if k is not None:
                    entry=i+1+delay;exit=entry+HOLD
                    # Size is fixed using known decision price with 1% cash buffer; if actual fill is unaffordable, skip rather than look ahead to pick another stock.
                    qty=math.floor(cash*.99/(series[k][i].c*(1+cost)**2)/LOT)*LOT
                    if qty>0:
                        next_allowed=entry+1
                        pending=(k,entry,exit,qty,i)
            assert cash>=-1e-7
        assert position is None and pending is None
        daily.append(dict(rule=rule,mult=mult,delay=delay,day=d,opening=before,closing=cash,net=cash-before,trades=n))
    assert math.isclose(cash-CAPITAL,sum(t['net'] for t in trades),abs_tol=1e-6)
    assert all(t['entry']>t['decision'] and t['exit']>t['entry'] and t['cost']>0 and t['qty']%LOT==0 for t in trades)
    assert all(a['exit']<b['entry'] for a,b in zip(trades,trades[1:]))
    return dict(rule=rule,mult=mult,delay=delay,pnl=cash-CAPITAL,return_pct=(cash/CAPITAL-1)*100,max_dd_pct=dd*100,trades=len(trades),wins=sum(t['net']>0 for t in trades),positive_days=sum(t['net']>0 for t in daily),gross=sum(t['gross'] for t in trades),cost=sum(t['cost'] for t in trades)),daily,trades

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('archive',type=Path);parser.add_argument('output',type=Path);a=parser.parse_args();data,dates=rel.load(a.archive);cache,checks=prepare(data,dates)
    summary=[];daily=[];trades=[];leave=[]
    for rule in RULES:
        for mult in (1,2):
            for delay in (0,1):
                res,ds,ts=simulate(cache,dates,rule,mult,delay);summary.append(res);daily+=ds;trades+=ts
                if mult==2 and delay==0:
                    for d in dates:
                        other,_,_=simulate(cache,[x for x in dates if x!=d],rule,mult,delay);leave.append(dict(rule=rule,omitted=d,pnl=other['pnl']))
    assert all(x['pnl']==0 and x['trades']==0 for x in summary if x['rule']=='NO_TRADE')
    assert all(math.isclose(x['pnl'],x['gross']-x['cost'],abs_tol=1e-6) for x in summary)
    a.output.mkdir(exist_ok=False)
    for name,rows in [('summary.csv',summary),('daily.csv',daily),('trades.csv',trades),('leave_one_day.csv',leave)]:r.core.write_new_csv(a.output/name,list(rows[0]),rows)
    manifest=dict(mode='KNOWN_PORTFOLIO_EXPLORATION_ONLY',dates=dates,archive_sha256=rel.ARCHIVE,pilot_plan_sha256=rel.PLAN,capital=CAPITAL,lot=LOT,holding_bars=HOLD,prefix_checks=checks,eligible_decisions=sum(len(v[1]) for v in cache.values()),rules=RULES,notes='Single long position, fixed 60-minute hold, no lunch crossing. Decision-time sizing with 1% buffer, unaffordable fills skipped. Ideal next-bar close or one extra bar delay; no real execution, no live orders, no prospective evaluation. Known data only.')
    (a.output/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8');print(json.dumps(manifest,indent=2))
if __name__=='__main__':main()
