"""R74 synthetic expected payoff study; no market forecasts or orders."""
import argparse, hashlib, json, runpy
from pathlib import Path
from fractions import Fraction as F
from copy import deepcopy
P=Path(__file__).with_name('Chappy_Trading_Economic_Value_Study_v0.1.py')
if hashlib.sha256(P.read_bytes()).hexdigest()!='8ad5370ca7d1341f5df9bc845b2a97a64bb03526952bb3fe0800a73c3666b85e': raise ValueError('R73 hash')
R=runpy.run_path(str(P)); S=R['R']; digest=R['digest']
PLAN={'window_slots':12,'minimum_resolved':6,'minimum_positive_and_negative':2,'extra_cost_stress_bps':20,'notional_yen':100000,'policies':['POINT','SENSITIVE'],'costs':R['PLAN']['round_trip_cost_bps'],'model':'relative signed return; leave-one-out minimum is sensitivity, not confidence bound','no_market_adoption':True}
SHA=digest(PLAN)
def estimate(xs,cost):
    n=len(xs); p=[x for x in xs if x>0]; l=[-x for x in xs if x<0]; f=n-len(p)-len(l)
    e={'n':n,'positive':len(p),'negative':len(l),'flat':f,'net':None,'sensitivity':None}
    if n>=6 and min(len(p),len(l))>=2:
        e.update(p_gain=str(F(len(p),n)),p_loss=str(F(len(l),n)),p_flat=str(F(f,n)),mean_gain=str(F(sum(p),len(p))),mean_loss=str(F(sum(l),len(l))),net=str(F(sum(xs),n)-cost),sensitivity=str(min(F(sum(xs)-x,n-1) for x in xs)-cost-20))
    return e

def decisions(rows,moves,cost):
    d,h=R['freeze'](rows); R['evaluate'](rows,d,h,moves,cost,0); out=[]
    for i,r in enumerate(rows):
        ev=[{'id':a['id'],'received':m['received'],'relative_bps':m['return_bps']*(1 if a['direction']=='UP' else -1)} for a,m in zip(rows[max(0,i-12):i],moves[max(0,i-12):i]) if a['eligible'] and m['received'] is not None and m['received']<=i]
        xs=[e['relative_bps'] for e in ev]; est={'CONTINUE':estimate(xs,cost),'REVERSE':estimate([-x for x in xs],cost)}; preds={}
        for k,field in [('POINT','net'),('SENSITIVE','sensitivity')]:
            valid=[(F(e[field]),p) for p,e in est.items() if e[field] is not None and F(e[field])>0];valid.sort(reverse=True)
            choice=valid[0][1] if valid and (len(valid)==1 or valid[0][0]>valid[1][0]) and r['eligible'] else None
            preds[k]=r['direction'] if choice=='CONTINUE' else S['opposite'](r['direction']) if choice=='REVERSE' else None
        out.append({'id':r['id'],'slot':i,'eligible':r['eligible'],'evidence':ev,'estimates':est,'predictions':preds})
    return out

def evaluate(rows,moves,cost,d,h,cutoff):
    if type(cutoff) is not int or cutoff<0 or digest(d)!=h or decisions(rows,moves,cost)!=d: raise ValueError('frozen decision mismatch')
    old,oh=R['freeze'](rows); scored=R['evaluate'](rows,old,oh,moves,cost,cutoff); out=[]
    for x,s in zip(d,scored):
        ret=s['return_bps']; pay={k:dict(v) for k,v in s['payoff'].items()}; hits=dict(s['hits'])
        for k,p in x['predictions'].items():
            state='INELIGIBLE' if not x['eligible'] else 'ABSTAIN' if p is None else 'UNRESOLVED' if ret is None else 'SCORED'
            net=0 if state=='ABSTAIN' else ret*(1 if p=='UP' else -1)-cost if state=='SCORED' else None
            pay[k]={'state':state,'net_yen':None if net is None else net*10}; hits[k]=None if p is None or s['outcome'] is None else p==s['outcome']
        out.append(dict(x,return_bps=ret,outcome=s['outcome'],payoff=pay,hits=hits))
    return out

def summary(rs):
    el=[r for r in rs if r['eligible']]; resolved=sum(r['outcome'] is not None for r in el); result={}
    for k in S['PLAN']['policies']+PLAN['policies']:
        scored=[r for r in el if r['payoff'][k]['state']=='SCORED']; vals=[r['payoff'][k]['net_yen'] for r in scored]; un=sum(r['payoff'][k]['state']=='UNRESOLVED' for r in el); n=len(vals); hits=sum(r['hits'][k] is True for r in scored)
        result[k]={'scored':n,'unresolved':un,'abstained':len(el)-n-un,'hits':hits,'accuracy':str(F(hits,n)) if n else None,'economic_wins':sum(v>0 for v in vals),'observed_net_yen':sum(vals),'all_selected_net_yen':None if un else sum(vals),'net_per_resolved_opportunity_yen':str(F(sum(vals),resolved)) if resolved else None}
    return {'eligible':len(el),'resolved':resolved,'unknown':len(el)-resolved,'policies':result}

def fixtures():
    for name,(rows,_) in S['fixtures']().items():
        old,_=R['freeze'](rows)
        for scenario in R['PLAN']['magnitude_scenarios']:
            moves=R['price_moves'](rows,old,scenario)
            for cost in PLAN['costs']: yield name,scenario,cost,rows,moves

def examples():
    out={}
    for name,scenario,cost,rows,moves in fixtures():
        d=decisions(rows,moves,cost); h=digest(d); rs=evaluate(rows,moves,cost,d,h,100)
        out[f'{name}:{scenario}:{cost}']={'decision_sha':h,'summary':summary(rs),'decisions':d if name=='blocks' and scenario=='symmetric' and cost==20 else None}
    return {'synthetic_only':True,'plan':PLAN,'plan_sha':SHA,'cases':out,'market_adoption':False}

def tests():
    out=[]
    def ck(n,a,b):
        if a!=b: raise AssertionError((n,a,b))
        out.append({'name':n,'pass':True})
    for name,scenario,cost,rows,moves in fixtures():
        tag=f'{name}:{scenario}:{cost}'; d=decisions(rows,moves,cost); h=digest(d); rs=evaluate(rows,moves,cost,d,h,100); sm=summary(rs)
        ck(tag+':denominator',(sm['eligible'],sm['resolved'],sm['unknown']),(73,72,1))
        for i,x in enumerate(d):
            valid=[j for j in range(max(0,i-12),i) if rows[j]['eligible'] and moves[j]['received'] is not None and moves[j]['received']<=i]
            ck(tag+f':evidence {i}',[e['id'] for e in x['evidence']],[rows[j]['id'] for j in valid])
            for k,sign in [('CONTINUE',1),('REVERSE',-1)]:
                vals=[sign*moves[j]['return_bps']*(1 if rows[j]['direction']=='UP' else -1) for j in valid]; e=x['estimates'][k]; p=[z for z in vals if z>0]; l=[z for z in vals if z<0]; ok=len(vals)>=6 and min(len(p),len(l))>=2
                oracle=F(sum(p)+sum(l),len(vals))-cost if ok else None
                ck(tag+f':mean {i}:{k}',e['net'],str(oracle) if ok else None)
                if ok:
                    ck(tag+f':decomposition {i}:{k}',F(e['p_gain'])*F(e['mean_gain'])-F(e['p_loss'])*F(e['mean_loss'])-cost,oracle)
                    ck(tag+f':sensitivity {i}:{k}',F(e['sensitivity']),min(F(sum(vals[:j]+vals[j+1:]),len(vals)-1) for j in range(len(vals)))-cost-20)
            ck(tag+f':subset {i}',x['predictions']['SENSITIVE'] is None or x['predictions']['SENSITIVE']==x['predictions']['POINT'],True)
        for k in PLAN['policies']:
            vals=[F(100000,10000)*(m['return_bps']*(1 if x['predictions'][k]=='UP' else -1)-cost) for x,m in zip(d,moves) if x['predictions'][k] is not None and m['return_bps'] is not None]
            ck(tag+':oracle '+k,sm['policies'][k]['observed_net_yen'],sum(vals)); ck(tag+':coverage '+k,sm['policies'][k]['scored']+sm['policies'][k]['unresolved']+sm['policies'][k]['abstained'],73)
        for i in (0,8,25,50,73):
            a=deepcopy(rows); b=deepcopy(moves)
            for r,m in zip(a,b):
                if m['received'] is not None and m['received']>i: r['received']=r['outcome']=m['received']=m['return_bps']=None
            ck(tag+f':unreceived mask {i}',decisions(a,b,cost)[i],d[i]); ck(tag+f':prefix {i}',decisions(rows[:i+1],moves[:i+1],cost)[-1],d[i]); ck(tag+f':cutoff {i}',[r['return_bps'] for r in evaluate(rows,moves,cost,d,h,i)],[m['return_bps'] if m['received'] is not None and m['received']<=i else None for m in moves[:i+1]])
        try: evaluate(rows,moves,cost,d,'0'*64,100)
        except ValueError: ck(tag+':wrong hash',True,True)
        else: raise AssertionError('hash accepted')
    ck('one sided sample insufficient',estimate([100]*8,20)['net'],None); ck('three outcomes exact',estimate([100,100,-100,-100,0,0],20)['net'],'-20')
    return {'passed':len(out),'tests':out}
if __name__=='__main__':
    p=argparse.ArgumentParser();g=p.add_mutually_exclusive_group(required=True);g.add_argument('--self-test',action='store_true');g.add_argument('--example',action='store_true');a=p.parse_args();print(json.dumps(tests() if a.self_test else examples(),indent=2,sort_keys=True))
