"""R70: artificial cross-sectional and time-scale volume contrasts; no market access."""
import argparse, hashlib, json, runpy
from pathlib import Path
from fractions import Fraction as F
from statistics import median
from itertools import product
P=Path(__file__).with_name('Chappy_Trading_Volume_Baseline_Study_v0.1.py')
if hashlib.sha256(P.read_bytes()).hexdigest()!='719a82912c9fc817b03fc26755124b74bb641630673c7526a846fd47b06bb265':raise ValueError('R69 hash')
R=runpy.run_path(str(P)); row=R['row']; end=R['end']; digest=R['digest']; measure=R['measure']
PLAN={'target':'X','sector':['S1','S2','S3'],'outside_sector':['M1','M2','M3'],'short':5,'long':15,'threshold':2,'aggregation':'median of per-symbol ratios; all three required','interpretation':'descriptive, not causal'}
SHA=digest(PLAN)
SYMS=['X']+PLAN['sector']+PLAN['outside_sector']
def study(rows,day=20,slot=6,cutoff=None):
    if type(day) is not int or day<15:raise ValueError('day')
    if cutoff is None:cutoff=end(day,slot)
    measures={}
    for s in SYMS:
        short=measure(rows,day,slot,cutoff,symbol=s)
        # 15 consecutive planned historical sessions; preserve missing and zero.
        hist={r['day']:r for r in rows if r['symbol']==s and r['regime']=='V1' and r['slot']==slot and day-15<=r['day']<day and r['received']<=cutoff}
        cur=next((r for r in rows if r['symbol']==s and r['regime']=='V1' and r['day']==day and r['slot']==slot and r['received']<=cutoff),None)
        base=F(median([r['volume'] for r in hist.values()])) if len(hist)==15 else None
        long=F(cur['volume'],base) if cur and base and cur['volume'] and cur['high']>cur['low'] else None
        measures[s]={'short':short['same_slot_median']['ratio'],'long':str(long) if long is not None else None,'long_state':'UNKNOWN' if cur is None or base is None else 'OBSERVED' if long is not None else 'UNDEFINED','short_evidence':short,'long_evidence_sha':digest([hist[d] for d in sorted(hist)])}
    def aggregate(syms,key):
        vals=[measures[s][key] for s in syms]
        return median([F(v) for v in vals]) if all(v is not None for v in vals) else None
    def ratio(a,b):return a/b if a is not None and b is not None and b>0 else None
    def st(x):return str(x) if x is not None else None
    contexts={}
    for key in ['short','long']:
        t=F(measures['X'][key]) if measures['X'][key] is not None else None
        s=aggregate(PLAN['sector'],key); m=aggregate(PLAN['outside_sector'],key)
        ts=ratio(t,s); sm=ratio(s,m)
        contexts[key]={'target':st(t),'sector':st(s),'outside':st(m),'target_over_sector':st(ts),'sector_over_outside':st(sm),'flags':{k:None if v is None else v>=2 for k,v in [('target_high',t),('outside_high',m),('target_relative_high',ts),('sector_relative_high',sm)]}}
    return {'plan_sha':SHA,'day':day,'slot':slot,'cutoff':cutoff,'measures':measures,'context':contexts,'cause':None,'prediction':None}
def fixture(t,s,m,shift=False,peer_values=None):
    rows=[]
    for i,(sym,v) in enumerate(zip(SYMS,[t]+[s]*3+[m]*3)):
        scale=i+1
        if peer_values and sym in peer_values:v=peer_values[sym]
        rows += [row(d,6,scale*(300 if shift and d>=15 else 100),symbol=sym) for d in range(5,20)]
        rows.append(row(20,6,scale*v,symbol=sym))
    return rows
CASES={'isolated':(300,100,100,False),'sector':(300,300,100,False),'broad':(300,300,300,False),'target_and_sector':(600,300,100,False),'persistent_shift':(300,300,300,True),'relative_weak':(100,300,300,False)}
def examples():
    out={k:study(fixture(*v)) for k,v in CASES.items()}
    out['peer_outlier']=study(fixture(300,100,100,peer_values={'S1':10000}))
    rr=fixture(300,100,100);out['missing_peer']=study([r for r in rr if not(r['symbol']=='S3' and r['day']==20)])
    return {'synthetic_only':True,'plan':PLAN,'cases':out}
def tests():
    out=[]
    def ck(n,a,b):
        if a!=b:raise AssertionError((n,a,b))
        out.append({'name':n,'pass':True})
    def reject(n,fn):
        try:fn()
        except ValueError:ck(n,True,True);return
        raise AssertionError(n)
    for t,s,m in product([50,100,200,300],repeat=3):
        rr=fixture(t,s,m);a=study(rr);c=a['context']['short'];p=f'{t}:{s}:{m}'
        ck(p+':ratios',[F(c[k]) for k in ['target','sector','outside','target_over_sector','sector_over_outside']],[F(t,100),F(s,100),F(m,100),F(t,s),F(s,m)])
        ck(p+':flags',list(c['flags'].values()),[t>=200,m>=200,t>=2*s,s>=2*m])
        ck(p+':long',a['context']['long'],c)
        ck(p+':order',study(rr[::-1]),a)
    e=examples()['cases'];ck('outlier median',e['peer_outlier']['context']['short']['sector'],'1');ck('missing peer',e['missing_peer']['context']['short']['target_over_sector'],None)
    ck('shift short',e['persistent_shift']['context']['short']['target'],'1');ck('shift long',e['persistent_shift']['context']['long']['target'],'3')
    rr=fixture(300,100,100);a=study(rr);cut=end(20,6)
    ck('future day',study(rr+[row(21,6,999,symbol='X')]),a)
    ck('late peer',study([dict(r,received=cut+1) if r['symbol']=='S1' and r['day']==20 else r for r in rr])['context']['short']['sector'],None)
    ck('old missing short unaffected',study([r for r in rr if not(r['symbol']=='X' and r['day']==5)])['context']['short'],a['context']['short'])
    ck('old missing long',study([r for r in rr if not(r['symbol']=='X' and r['day']==5)])['context']['long']['target'],None)
    ck('zero peer',study([dict(r,volume=0) if r['symbol']=='M1' and r['day']==20 else r for r in rr])['context']['short']['outside'],None)
    ck('cause unknown',a['cause'],None);ck('no forecast',a['prediction'],None)
    reject('duplicate',lambda:study(rr+[rr[0]]));reject('early cutoff',lambda:study(rr,cutoff=cut-1))
    return {'passed':len(out),'tests':out}
if __name__=='__main__':
    p=argparse.ArgumentParser();g=p.add_mutually_exclusive_group(required=True);g.add_argument('--self-test',action='store_true');g.add_argument('--example',action='store_true');a=p.parse_args();print(json.dumps(tests() if a.self_test else examples(),indent=2,sort_keys=True))
