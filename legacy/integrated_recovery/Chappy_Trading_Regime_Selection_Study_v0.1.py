"""R72 synthetic sequential policy selection. No live prices, orders or financial returns."""
import argparse, hashlib, json, runpy
from pathlib import Path
from fractions import Fraction as F
from collections import Counter
from copy import deepcopy
P=Path(__file__).with_name('Chappy_Trading_Composite_Hypothesis_Study_v0.1.py')
if hashlib.sha256(P.read_bytes()).hexdigest()!='6008d21c6ee5e2ac7ce6a6a59e87c7f88bd3e7407ce99056a0859e4525ef5f31':raise ValueError('R71 hash')
R=runpy.run_path(str(P)); digest=R['digest']
PLAN={'window_slots':8,'minimum_resolved':6,'hit_margin':2,'horizon_slots':3,'availability':'received <= decision, earlier slot only','policies':['CONTINUE','REVERSE','ADAPT','NO_DIRECTION'],'scenarios':['blocks','interleaved','blocks_delayed'],'no_market_adoption':True}
SHA=digest(PLAN)

def fixtures():
    _,_,records=R['build'](); groups={g:[r for r in records if r['regime']==g] for g in R['REGIMES']}
    ordered=sum(groups.values(),[]); inter=[r for z in zip(*groups.values()) for r in z]
    missing=[r for r in records if r['regime']=='missing']; result={}
    for name,src in [('blocks',ordered),('interleaved',inter),('blocks_delayed',ordered)]:
        src=src[:24]+missing[:1]+src[24:48]+missing[1:]+src[48:]; schedule=[]; labels={}
        for i,r in enumerate(src):
            cid=f'T{i:03}'; labels[cid]=r['regime']; outcome=r['outcome'] if r['eligible'] else None
            if outcome=='UNKNOWN':outcome=None
            schedule.append({'id':cid,'slot':i,'eligible':r['eligible'],'direction':r['predictions']['CONTINUE'],'outcome':outcome,'received':i+3+(4 if name=='blocks_delayed' and i%3==0 else 0) if outcome is not None else None})
        result[name]=(schedule,labels)
    return result

def validate(rows):
    for i,r in enumerate(rows):
        if set(r)!= {'id','slot','eligible','direction','outcome','received'} or r['id']!=f'T{i:03}' or type(r['slot']) is not int or r['slot']!=i or type(r['eligible']) is not bool:raise ValueError('schedule')
        if r['eligible'] and r['direction'] not in ('UP','DOWN') or not r['eligible'] and (r['direction'] is not None or r['outcome'] is not None):raise ValueError('eligibility')
        if r['outcome'] is None:
            if r['received'] is not None:raise ValueError('missing result')
        elif r['outcome'] not in ('UP','DOWN','FLAT') or type(r['received']) is not int or r['received']<i+PLAN['horizon_slots']:raise ValueError('future result')

def opposite(d):return {'UP':'DOWN','DOWN':'UP',None:None}[d]

def select(evidence):
    # Only previously received, eligible outcomes; no scenario labels, price futures or IDs with regime info.
    c=sum(x['direction']==x['outcome'] for x in evidence); r=sum(opposite(x['direction'])==x['outcome'] for x in evidence)
    n=len(evidence)
    mode='CONTINUE' if n>=PLAN['minimum_resolved'] and c-r>=PLAN['hit_margin'] else 'REVERSE' if n>=PLAN['minimum_resolved'] and r-c>=PLAN['hit_margin'] else 'NO_DIRECTION'
    return mode,c,r

def decisions(rows):
    validate(rows); result=[]
    for i,cur in enumerate(rows):
        ev=[{k:r[k] for k in ('id','slot','direction','outcome','received')} for r in rows[max(0,i-PLAN['window_slots']):i] if r['eligible'] and r['received'] is not None and r['received']<=i]
        mode,c,r=select(ev)
        # With 8 previous slots and 3-slot settlement, at most 6 observations can be available.
        d=cur['direction']; mode=mode if cur['eligible'] else 'NO_DIRECTION'
        preds={'CONTINUE':d,'REVERSE':opposite(d),'ADAPT':d if mode=='CONTINUE' else opposite(d) if mode=='REVERSE' else None,'NO_DIRECTION':None}
        result.append({'id':cur['id'],'slot':i,'eligible':cur['eligible'],'mode':mode,'evidence':ev,'counts':[len(ev),c,r],'predictions':preds})
    return result

def evaluate(rows,frozen,expected_sha,cutoff):
    validate(rows)
    if type(cutoff) is not int or cutoff<0 or digest(frozen)!=expected_sha or decisions(rows)!=frozen:raise ValueError('frozen decision mismatch')
    result=[]
    for r,d in zip(rows,frozen):
        if r['slot']>cutoff:continue
        y=r['outcome'] if r['received'] is not None and r['received']<=cutoff else None
        result.append(dict(d,outcome=y,hits={k:None if p is None or y is None else p==y for k,p in d['predictions'].items()}))
    return result

def summary(rs):
    eligible=[r for r in rs if r['eligible']]; resolved=[r for r in eligible if r['outcome'] is not None]; out={}
    for k in PLAN['policies']:
        n=sum(r['predictions'][k] is not None for r in eligible); s=sum(r['hits'][k] is not None for r in eligible); h=sum(r['hits'][k] is True for r in eligible)
        out[k]={'predictions':n,'scored':s,'hits':h,'unresolved_predictions':n-s,'abstained':len(eligible)-n,'accuracy':str(F(h,s)) if s else None,'hits_per_resolved_opportunity':str(F(h,len(resolved))) if resolved else None}
    return {'total':len(rs),'eligible':len(eligible),'resolved':len(resolved),'unknown':len(eligible)-len(resolved),'ineligible':len(rs)-len(eligible),'policies':out,'modes':dict(Counter(r['mode'] for r in eligible))}

def examples(fixtures_=None):
    out={}
    for name,(rows,labels) in (fixtures_ or fixtures()).items():
        d=decisions(rows); h=digest(d); rs=evaluate(rows,d,h,len(rows)+10)
        out[name]={'decision_sha':h,'summary':summary(rs),'by_regime':{g:summary([r for r in rs if labels[r['id']]==g]) for g in (*R['REGIMES'],'missing')},'records':rs,'labels_for_posthoc_only':labels,'schedule':rows}
    return {'synthetic_only':True,'plan':PLAN,'plan_sha':SHA,'scenarios':out,'market_adoption':False}

def tests():
    fs=fixtures(); ex=examples(fs); out=[]
    def ck(n,a,b):
        if a!=b:raise AssertionError((n,a,b))
        out.append({'name':n,'pass':True})
    def reject(n,fn):
        try:fn()
        except ValueError:ck(n,True,True);return
        raise AssertionError(n)
    for name,(rows,labels) in fs.items():
        d=decisions(rows); h=digest(d); rs=evaluate(rows,d,h,len(rows)+10); sm=summary(rs)
        ck(name+':denominator',[sm[k] for k in ('total','eligible','resolved','unknown','ineligible')],[74,73,72,1,1])
        ck(name+':static hits',[sm['policies'][k]['hits'] for k in ('CONTINUE','REVERSE')],[28,28]);ck(name+':no direction',sm['policies']['NO_DIRECTION']['accuracy'],None)
        for i,x in enumerate(d):
            ck(name+f':prefix {i}',decisions(rows[:i+1])[-1],x)
            valid=[r for r in rows[:i] if i-r['slot']<=8 and r['received'] is not None and r['received']<=i]
            c=sum(r['outcome']==r['direction'] for r in valid); rev=sum(r['outcome']!=r['direction'] and r['outcome']!='FLAT' for r in valid)
            ck(name+f':oracle counts {i}',x['counts'],[len(valid),c,rev])
            expected='CONTINUE' if len(valid)>=6 and c-rev>=2 else 'REVERSE' if len(valid)>=6 and rev-c>=2 else 'NO_DIRECTION'
            ck(name+f':mode {i}',x['mode'],expected if rows[i]['eligible'] else 'NO_DIRECTION')
            masked=deepcopy(rows)
            for r in masked:
                if r['received'] is not None and r['received']>i:r['outcome']=None;r['received']=None
            ck(name+f':unreceived masked {i}',decisions(masked)[i],x)
            ck(name+f':cutoff {i}',[r['outcome'] for r in evaluate(rows,d,h,i)],[r['outcome'] if r['received'] is not None and r['received']<=i else None for r in rows[:i+1]])
        for k,v in sm['policies'].items():ck(name+':coverage '+k,v['predictions']+v['abstained'],73);ck(name+':scoring '+k,v['scored']+v['unresolved_predictions'],v['predictions'])
        reject(name+':bad digest',lambda:evaluate(rows,d,'0'*64,99)); bad=deepcopy(rows);bad[0]['received']=2;reject(name+':early outcome',lambda:decisions(bad));bad=deepcopy(rows);bad[1]['id']=bad[0]['id'];reject(name+':duplicate',lambda:decisions(bad))
    ck('delay cannot add predictions',ex['scenarios']['blocks_delayed']['summary']['policies']['ADAPT']['predictions']<=ex['scenarios']['blocks']['summary']['policies']['ADAPT']['predictions'],True)
    ck('no adoption',ex['market_adoption'],False)
    return {'passed':len(out),'tests':out}
if __name__=='__main__':
    p=argparse.ArgumentParser();g=p.add_mutually_exclusive_group(required=True);g.add_argument('--self-test',action='store_true');g.add_argument('--example',action='store_true');a=p.parse_args();print(json.dumps(tests() if a.self_test else examples(),indent=2,sort_keys=True))
