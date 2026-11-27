# -*- coding: utf-8 -*-
"""Known-data long/short research only. No brokerage, no live trading.
Usage: python Chappy_Trading_LongShort_Study_v0.1.py CTRL.zip output_dir
Requires Portfolio/Relative/Signal Study v0.1, Research v0.5.0 and RC1 alongside.
"""
import argparse, csv, hashlib, importlib.util, json, math, sys
from dataclasses import dataclass
from decimal import Decimal as D
from pathlib import Path
p=Path(__file__).with_name('Chappy_Trading_Portfolio_Study_v0.1.py')
spec=importlib.util.spec_from_file_location('portfolio01',p); port=importlib.util.module_from_spec(spec);sys.modules[spec.name]=port;spec.loader.exec_module(port)
CAP=1_000_000.; LOT=100; HOLD=12; GROSS=.9; MAINT=.30
RULES=('NO_TRADE','LONG_REBOUND','SHORT_REVERSAL','DIRECTION','HEDGE_FOLLOW','HEDGE_REVERSE','HEDGE_PARTIAL','DIRECT_FOLLOW','DIRECT_REVERSE','ASYMMETRIC','FLIP','PAIR','DIVERSIFIED','ADAPTIVE')
@dataclass
class Leg:
    symbol:str; side:int; qty:int; raw:float; basis:float; borrow:float
class Book:
    def __init__(self,mult=1,capital=CAP):
        self.cash=capital;self.initial=capital;self.rate=.0005*mult;self.borrow_rate=.0001*mult;self.legs={};self.fills=[];self.peak=capital;self.dd=0.;self.margin_calls=0;self.rejections=0
    def equity(self,px):
        return self.cash+sum(l.qty*px[l.symbol]*((1-self.rate)**2 if l.side==1 else -(1+self.rate)**2) for l in self.legs.values())
    def exposure(self,px):return sum(l.qty*px[l.symbol] for l in self.legs.values())
    def mark(self,px):
        eq=self.equity(px); self.peak=max(self.peak,eq);self.dd=max(self.dd,1-eq/self.peak);return eq
    def enter(self,orders,px,ts,reason):
        # Atomic batch; short proceeds cannot fund extra gross exposure.
        if not orders:return False
        if any((k,s) in self.legs or s not in (-1,1) or q<=0 or q%LOT for k,s,q in orders) or len({(k,s) for k,s,q in orders})!=len(orders):raise ValueError('invalid orders')
        eq=self.equity(px); added=sum(px[k]*q for k,s,q in orders)
        if eq<=0 or self.exposure(px)+added>GROSS*eq+1e-7:
            self.rejections+=1;return False
        # Upfront hypothetical borrow charge, one day minimum, no intraday prorating.
        for k,s,q in orders:
            raw=px[k];fill=raw*(1+self.rate*s);fee=fill*q*self.rate;borrow=raw*q*self.borrow_rate if s==-1 else 0.
            delta=-s*fill*q-fee-borrow;self.cash+=delta
            self.legs[k,s]=Leg(k,s,q,raw,delta,borrow)
            self.fills.append(dict(ts=ts,action='OPEN',symbol=k,side=s,qty=q,raw=raw,fill=fill,fee=fee,borrow=borrow,delta=delta,cash=self.cash,net=0.,gross=0.,reason=reason))
        return True
    def close(self,key,q,px,ts,reason):
        l=self.legs[key];assert 0<q<=l.qty and q%LOT==0
        ratio=q/l.qty;raw=px[l.symbol];fill=raw*(1-self.rate*l.side);fee=fill*q*self.rate;delta=l.side*fill*q-fee;self.cash+=delta;net=delta+l.basis*ratio;gross=l.side*(raw-l.raw)*q
        self.fills.append(dict(ts=ts,action='CLOSE',symbol=l.symbol,side=l.side,qty=q,raw=raw,fill=fill,fee=fee,borrow=0.,delta=delta,cash=self.cash,net=net,gross=gross,reason=reason))
        l.basis*=1-ratio;l.borrow*=1-ratio;l.qty-=q
        if not l.qty:del self.legs[key]
    def flatten(self,px,ts,reason):
        for key,l in list(self.legs.items()):self.close(key,l.qty,px,ts,reason)
    def margin_breach(self,px):return bool(self.legs) and self.equity(px)<MAINT*self.exposure(px)

def choose(f,rule):
    lo=[k for k,v in f.items() if v[0]<30 and v[1]>0 and v[2]>0 and v[5]>=3]
    sh=[k for k,v in f.items() if v[0]>70 and v[1]<0 and v[2]<0 and v[5]<=2]
    long=min(lo,key=lambda k:(f[k][0],k)) if lo else None
    short=max(sh,key=lambda k:(f[k][0],k)) if sh else None
    strongest=min(f,key=lambda k:(-f[k][4],k)); weakest=min(f,key=lambda k:(f[k][4],k))
    if rule=='NO_TRADE':return []
    if rule=='LONG_REBOUND':return [(long,1,1)] if long else []
    if rule=='SHORT_REVERSAL':return [(short,-1,1)] if short else []
    if rule in ('DIRECTION','FLIP','ADAPTIVE'):
        if long and short:return []
        if long:return [(long,1,1)]
        if short:return [(short,-1,1)]
        if rule=='ADAPTIVE' and f[strongest][4]-f[weakest][4]>.6:return [(strongest,1,.5),(weakest,-1,.5)]
        return []
    if rule=='PAIR':return [(strongest,1,.5),(weakest,-1,.5)] if f[strongest][4]-f[weakest][4]>.3 else []
    if rule=='DIVERSIFIED':
        ks=sorted(f,key=lambda k:(f[k][4],k));return [(k,-1,.25) for k in ks[:2]]+[(k,1,.25) for k in ks[-2:]] if f[ks[-1]][4]-f[ks[0]][4]>.3 else []
    # Match entry times and sizing for symmetric hedge and direct controls; only rebound/short signals initiate a cycle.
    k=long or short
    if not k:return []
    if rule=='ASYMMETRIC':return [(k,1,.7 if long else .3),(k,-1,.3 if long else .7)]
    return [(k,1,.5),(k,-1,.5)]

def size(orders,px,equity):
    return [(k,s,q) for k,s,w in orders if (q:=math.floor(max(0,equity)*GROSS*.98*w/px[k]/LOT)*LOT)>0]

def simulate(cache,dates,rule,mult,delay,threshold=.003):
    b=Book(mult);daily=[];cycles=0;size_skips=0;is_hedge=rule in ('HEDGE_FOLLOW','HEDGE_REVERSE','HEDGE_PARTIAL','DIRECT_FOLLOW','DIRECT_REVERSE','ASYMMETRIC');direct=rule in ('DIRECT_FOLLOW','DIRECT_REVERSE');blocked=False
    for d in dates:
        series,eligible=cache[d]; first=next(iter(series.values()));start=b.cash;pending=None;cycle=None;forced=None;stage=None;last_fill=len(b.fills)
        for i in range(len(first)):
            px={k:v[i].c for k,v in series.items()};ts=first[i].ts.isoformat()
            if forced==i:
                b.flatten(px,ts,'MARGIN');forced=None;cycle=None;pending=None;stage=None;blocked=True
            if pending and pending[0]==i:
                _,orders,end=pending;pending=None
                if direct or b.enter(orders,px,ts,'ENTRY'):
                    cycles+=1;cycle=dict(orders=orders,base=px[orders[0][0]],end=end,acted=False,entry=i)
            if cycle and i==cycle['end']:
                b.flatten(px,ts,'TIME_EXIT');cycle=None;stage=None;forced=None
            if cycle and stage and i==stage[0]:
                _,side,kind=stage;stage=None;k=cycle['orders'][0][0]
                if kind=='FLIP':
                    key=next(iter(b.legs),None)
                    if key:
                        q=b.legs[key].qty;b.flatten(px,ts,'FLIP_CLOSE');b.enter([(k,-key[1],q)],px,ts,'FLIP_OPEN')
                elif direct:
                    q=next(q for a,s,q in cycle['orders'] if s==side);b.enter([(k,side,q)],px,ts,'DIRECT_TRIGGER')
                else:
                    key=k,-side
                    if key in b.legs:
                        q=b.legs[key].qty
                        if kind=='PARTIAL':q=max(LOT,(q//LOT//2)*LOT)
                        b.close(key,q,px,ts,kind)
            eq=b.mark(px)
            if b.margin_breach(px) and forced is None:
                b.margin_calls+=1;stage=None;forced=min(i+1,cycle['end'] if cycle else i+1)
            if cycle and not cycle['acted'] and stage is None and forced is None and i>cycle['entry'] and i+1+delay<cycle['end']:
                k=cycle['orders'][0][0];move=px[k]/cycle['base']-1
                if abs(move)>=threshold and (is_hedge or rule=='FLIP'):
                    direction=1 if move>0 else -1
                    if rule=='FLIP':
                        if b.legs and direction!=next(iter(b.legs))[1]:stage=(i+1+delay,direction,'FLIP');cycle['acted']=True
                    else:
                        keep=-direction if rule.endswith('REVERSE') else direction
                        stage=(i+1+delay,keep,'PARTIAL' if rule=='HEDGE_PARTIAL' else 'RELEASE');cycle['acted']=True
            if not blocked and cycle is None and pending is None and forced is None and i in eligible:
                chosen=choose(eligible[i],rule);orders=size(chosen,px,eq)
                # Never silently turn an intended multi-leg hedge into a single leg because of lot size.
                if chosen and len(orders)!=len(chosen):size_skips+=1
                if orders and len(orders)==len(chosen):
                    entry=i+1+delay;pending=(entry,orders,entry+HOLD)
        assert not b.legs and pending is None and cycle is None and forced is None
        daily.append(dict(day=d,opening=start,closing=b.cash,net=b.cash-start,fills=len(b.fills)-last_fill))
    assert math.isclose(b.cash-CAP,sum(x['net'] for x in b.fills),abs_tol=1e-6)
    audit(b)
    closes=[x for x in b.fills if x['action']=='CLOSE'];gross=sum(x['gross'] for x in closes)
    return dict(rule=rule,mult=mult,delay=delay,pnl=b.cash-CAP,return_pct=(b.cash/CAP-1)*100,max_dd_pct=b.dd*100,cycles=cycles,closed_legs=len(closes),wins=sum(x['net']>0 for x in closes),gross=gross,cost=gross-(b.cash-CAP),borrow=sum(x['borrow'] for x in b.fills),margin_calls=b.margin_calls,rejections=b.rejections,size_skips=size_skips),daily,b.fills

def audit(b):
    # Independent decimal replay from raw prices and side; checks cash at every event and proportional entry cost allocation.
    cash=D(str(b.initial));rate=D(str(b.rate));br=D(str(b.borrow_rate));positions={}
    for x in b.fills:
        k=x['symbol'],x['side'];s=D(x['side']);q=D(x['qty']);raw=D(str(x['raw']));opening=x['action']=='OPEN';fill=raw*(1+(s if opening else -s)*rate);fee=fill*q*rate;borrow=raw*q*br if opening and s==-1 else D(0);delta=(-s if opening else s)*fill*q-fee-borrow;cash+=delta
        if opening:assert k not in positions;positions[k]=(q,delta)
        else:
            prev,basis=positions[k];net=delta+basis*q/prev;assert abs(net-D(str(x['net'])))<D('0.000001');positions[k]=(prev-q,basis*(prev-q)/prev)
            if prev==q:del positions[k]
        assert abs(cash-D(str(x['cash'])))<D('0.000001')
    assert not positions and abs(cash-D(str(b.cash)))<D('0.000001')

def selftest():
    # equal-size hedge loses costs only irrespective of price, partial close and adverse short mark.
    for end in (800.,1000.,1200.):
        b=Book();assert b.enter([('A',1,400),('A',-1,400)],{'A':1000},'0','TEST');b.close(('A',1),200,{'A':end},'1','PART');b.flatten({'A':end},'2','END');audit(b);assert b.cash<CAP and abs(sum(f['gross'] for f in b.fills))<1e-6
    b=Book();assert b.enter([('A',-1,800)],{'A':1000},'0','TEST');assert not b.enter([('B',1,200)],{'A':1000,'B':1000},'1','TEST');assert b.margin_breach({'A':2500});b.flatten({'A':2500},'2','MARGIN');assert b.cash<0;audit(b)
    for side in (1,-1):
        b=Book();assert b.enter([('A',side,400)],{'A':1000},'0','TEST');b.flatten({'A':1000+100*side},'1','TEST');assert b.cash>CAP;audit(b)
    # Same quantities and same release/exit prices: gross equivalence, extra hedge costs.
    for trigger in (900.,1100.):
        for keep in (-1,1):
            h=Book();direct=Book();assert h.enter([('A',1,400),('A',-1,400)],{'A':1000},'0','TEST')
            h.close(('A',-keep),400,{'A':trigger},'1','RELEASE');assert direct.enter([('A',keep,400)],{'A':trigger},'1','DIRECT')
            for b in (h,direct):b.flatten({'A':1050},'2','END');audit(b)
            assert sum(f['gross'] for f in h.fills)==sum(f['gross'] for f in direct.fills) and h.cash<direct.cash
    # End-to-end margin exit on a short gap; do not hide negative equity or resume trades.
    from types import SimpleNamespace
    from datetime import datetime,timedelta
    start=datetime(2026,1,5,9,10)
    bars=[SimpleNamespace(c=1000. if i<2 else 3000.,ts=start+timedelta(minutes=5*i)) for i in range(20)]
    cache={'test':({'A':bars},{0:{'A':(80,-.01,-1.,0.,-1.,0)},5:{'A':(80,-.01,-1.,0.,-1.,0)}})}
    result,_,fills=simulate(cache,['test'],'SHORT_REVERSAL',1,0)
    assert result['margin_calls']==1 and result['cycles']==1 and result['pnl']<-CAP and fills[-1]['reason']=='MARGIN' and fills[-1]['ts']==bars[3].ts.isoformat()
    return 11

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('archive',type=Path);p.add_argument('output',type=Path);a=p.parse_args();tests=selftest();data,dates=port.rel.load(a.archive);cache,checks=port.prepare(data,dates)
    summary=[];daily=[];fills=[];leave=[]
    for rule in RULES:
        for mult in (1,2):
            for delay in (0,1):
                res,ds,fs=simulate(cache,dates,rule,mult,delay);summary.append(res);daily.extend(dict(rule=rule,mult=mult,delay=delay,**x) for x in ds);fills.extend(dict(rule=rule,mult=mult,delay=delay,**x) for x in fs)
                if mult==2 and delay==0:
                    for d in dates:
                        other,_,_=simulate(cache,[x for x in dates if x!=d],rule,mult,delay);leave.append(dict(rule=rule,omitted=d,pnl=other['pnl']))
    assert all(x['closed_legs']==0 and x['pnl']==0 for x in summary if x['rule']=='NO_TRADE')
    assert all(x['closed_legs']>0 for x in summary if x['rule']=='DIRECTION')
    a.output.mkdir(exist_ok=False)
    for name,rows in [('summary.csv',summary),('daily.csv',daily),('fills.csv',fills),('leave_one_day.csv',leave)]:
        with (a.output/name).open('x',newline='',encoding='utf-8-sig') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    manifest=dict(mode='KNOWN_EXPLORATION_ONLY',archive_sha256=port.rel.ARCHIVE,pilot_plan_sha256=port.rel.PLAN,dates=dates,rules=RULES,capital=CAP,lot=LOT,gross_limit=GROSS,maintenance=MAINT,borrow_per_open=.0001,threshold=.003,holding_bars=HOLD,prefix_checks=checks,synthetic_tests=tests,accounts=len(summary),audited_fills=len(fills),notes='Hypothetical short access; no broker rules, availability, real margin, intrabar liquidation or real delay simulation. Gross entry cap, liquidation mark, next-bar margin exit; no new trades after breach. Fixed same-session horizon. Known data only; not a deployment recommendation.')
    (a.output/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8');print(json.dumps(manifest,indent=2))
if __name__=='__main__':main()
