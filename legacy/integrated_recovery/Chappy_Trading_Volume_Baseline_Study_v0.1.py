"""R69 synthetic volume baselines; no market access, prediction or orders."""
import argparse, hashlib, json, runpy
from pathlib import Path
from fractions import Fraction as F
from statistics import median
from itertools import product
from copy import deepcopy
P=Path(__file__).with_name('Chappy_Trading_Price_Response_Study_v0.1.py')
if hashlib.sha256(P.read_bytes()).hexdigest()!='1b9e2634cdfaeaa15b6d11446e187cfaa90a3d6daa89f64dc1e670a0685511a3':raise ValueError('R68 hash')
R=runpy.run_path(str(P)); digest=R['digest']; classify=R['classify']
# Artificial days and segments, not an exchange calendar. Slots are 5-minute bars.
PLAN={'history_days':5,'local_bars':3,'segments':[[0,11],[20,31]],'high_ratio':2,'history_estimator':['mean','median'],'missing_policy':'no substitution','target':'volume classification only'}
PLAN_SHA=digest(PLAN)
def end(day,slot):return day*86400+(slot+1)*300
def row(day,slot,v,received=None,symbol='X',regime='V1',o=100,h=110,l=90,c=101):
    return dict(day=day,slot=slot,volume=v,received=end(day,slot) if received is None else received,symbol=symbol,regime=regime,open=o,high=h,low=l,close=c)
def segment(s):return next((a for a,b in PLAN['segments'] if a<=s<=b),None)
def valid(r):
    if set(r)!=set(row(0,0,0)) or any(type(r[k]) is not int for k in ('day','slot','volume','received','open','high','low','close')):raise ValueError('schema')
    if r['day']<0 or segment(r['slot']) is None or r['volume']<0 or r['received']<end(r['day'],r['slot']) or not 0<r['low']<=min(r['open'],r['close'])<=max(r['open'],r['close'])<=r['high'] or not all(isinstance(r[k],str) and r[k] for k in ('symbol','regime')):raise ValueError('row')
def measure(rows,day,slot,cutoff,symbol='X',regime='V1'):
    if any(type(x) is not int for x in (day,slot,cutoff)) or day<5 or segment(slot) is None or not end(day,slot)<=cutoff<end(day,slot)+300:raise ValueError('decision')
    seen={}
    for r in rows:
        valid(r)
        if r['symbol']!=symbol or r['regime']!=regime or r['received']>cutoff:continue
        key=(r['day'],r['slot'])
        if key in seen:raise ValueError('duplicate')
        seen[key]=r
    cur=seen.get((day,slot)); local=[seen.get((day,s)) for s in range(slot-3,slot)] if slot-3>=segment(slot) else []
    hist=[seen.get((d,slot)) for d in range(day-5,day)]
    def calc(samples,method):
        present=[r for r in samples if r is not None]
        out={'state':'UNKNOWN','n':len(present),'baseline':None,'ratio':None,'category':None,'source_sha':digest(present)}
        if cur is None or not samples or len(present)!=len(samples):return out
        vs=[r['volume'] for r in present]; base=F(sum(vs),len(vs)) if method=='mean' else F(median(vs))
        span=cur['high']-cur['low']
        out['baseline']=str(base)
        if base==0 or cur['volume']==0 or span==0:return dict(out,state='UNDEFINED')
        ratio=F(cur['volume'],base);body=F(cur['close']-cur['open'],span)
        return dict(out,state='OBSERVED',ratio=str(ratio),category=classify(ratio,body))
    return {'plan_sha':PLAN_SHA,'day':day,'slot':slot,'cutoff':cutoff,'symbol':symbol,'regime':regime,'current_sha':digest(cur) if cur else None,'local_mean':calc(local,'mean'),'same_slot_mean':calc(hist,'mean'),'same_slot_median':calc(hist,'median'),'prediction':None}
def fixture(v,local,hist,slot=6):
    return [row(d,slot,x) for d,x in enumerate(hist,5)]+[row(10,s,x) for s,x in zip(range(slot-3,slot),local) if segment(s)==segment(slot) and segment(s) is not None]+[row(10,slot,v)]
CASES={'seasonal_normal':(300,[100]*3,[280,290,300,310,320]),'persistent_unusual':(300,[300]*3,[80,90,100,110,120]),'outlier_history':(250,[100]*3,[100,100,100,100,1100]),'regime_shift':(300,[300]*3,[100]*5),'opening':(600,[],[500,550,600,650,700])}
def examples():
    result={}
    for k,(v,l,h) in CASES.items():
        s=0 if k=='opening' else 6
        result[k]=measure(fixture(v,l,h,s),10,s,end(10,s))
    return {'synthetic_only':True,'plan':PLAN,'cases':result,'limitations':['fixed artificial sessions; no exchange calendar','mean/median not probability','persistent change vs anomaly cannot be identified from ratio alone','no real market data or price predictions']}
def tests():
    out=[]
    def ck(n,a,b):
        if a!=b:raise AssertionError((n,a,b))
        out.append({'name':n,'pass':True})
    def reject(n,fn):
        try:fn()
        except ValueError:ck(n,True,True);return
        raise AssertionError(n)
    for v,l,h in product((1,50,100,200,300,500),(1,100,300),(1,100,300,500)):
        rs=fixture(v,[l]*3,[h]*5);cut=end(10,6);a=measure(rs,10,6,cut)
        for key,base in [('local_mean',l),('same_slot_mean',h),('same_slot_median',h)]:
            ck(f'{v}:{l}:{h}:{key}',a[key]['category'],'HIGH_VOLUME_WEAK_BODY' if v>=2*base else 'ORDINARY_VOLUME')
        ck(f'{v}:{l}:{h}:reverse',measure(rs[::-1],10,6,cut),a)
    e=examples()['cases'];
    for k,vals in {'seasonal_normal':('3','1','1'),'persistent_unusual':('1','3','3'),'outlier_history':('5/2','5/6','5/2'),'regime_shift':('1','3','3'),'opening':(None,'1','1')}.items():
        ck(k,tuple(e[k][x]['ratio'] for x in ('local_mean','same_slot_mean','same_slot_median')),vals)
    r=fixture(300,[100]*3,[100]*5);cut=end(10,6);a=measure(r,10,6,cut)
    ck('future day',measure(r+[row(11,6,999)],10,6,cut),a)
    ck('future slot',measure(r+[row(10,7,999)],10,6,cut),a)
    ck('other symbol',measure(r+[row(10,6,999,symbol='Y')],10,6,cut),a)
    ck('missing history',measure(r[1:],10,6,cut)['same_slot_median']['state'],'UNKNOWN')
    ck('delayed history',measure([dict(r[0],received=cut+1)]+r[1:],10,6,cut)['same_slot_mean']['state'],'UNKNOWN')
    ck('different regime',measure([dict(r[0],regime='V0')]+r[1:],10,6,cut)['same_slot_mean']['state'],'UNKNOWN')
    ck('late current',measure(r[:-1]+[dict(r[-1],received=cut+1)],10,6,cut)['local_mean']['state'],'UNKNOWN')
    ck('zero historical',measure(fixture(300,[100]*3,[0]*5),10,6,cut)['same_slot_median']['state'],'UNDEFINED')
    ck('zero current',measure(fixture(0,[100]*3,[100]*5),10,6,cut)['same_slot_median']['state'],'UNDEFINED')
    ck('zero included',measure(fixture(200,[100]*3,[0,100,100,100,100]),10,6,cut)['same_slot_mean']['baseline'],'80')
    ck('afternoon no cross',measure(fixture(300,[],[100]*5,20),10,20,end(10,20))['local_mean']['state'],'UNKNOWN')
    ck('no price prediction',a['prediction'],None)
    reject('duplicate',lambda:measure(r+[r[0]],10,6,cut));reject('early cutoff',lambda:measure(r,10,6,cut-1));reject('late cutoff',lambda:measure(r,10,6,cut+300));reject('lunch slot',lambda:measure(r,10,12,end(10,12)));reject('bad volume',lambda:measure(r+[row(10,7,-1)],10,6,cut))
    return {'passed':len(out),'tests':out}
if __name__=='__main__':
    p=argparse.ArgumentParser();g=p.add_mutually_exclusive_group(required=True);g.add_argument('--self-test',action='store_true');g.add_argument('--example',action='store_true');a=p.parse_args();print(json.dumps(tests() if a.self_test else examples(),indent=2,sort_keys=True))
