"""R73: synthetic directional payoff study, not execution simulation or market evidence."""
import argparse, hashlib, json, runpy
from pathlib import Path
from fractions import Fraction as F
P=Path(__file__).with_name('Chappy_Trading_Regime_Selection_Study_v0.1.py')
if hashlib.sha256(P.read_bytes()).hexdigest()!='f1678ab42c11426ed78478e4de5231836c09918f2d96998985948adec1d2f429':raise ValueError('R72 hash')
R=runpy.run_path(str(P)); digest=R['digest']; POL=R['PLAN']['policies']
PLAN={'notional_yen':100000,'round_trip_cost_bps':[20,40,150], 'magnitude_scenarios':['symmetric','continuation_large','reversal_large','adapt_error_stress'], 'directional_bps_small':100,'directional_bps_large':400,'flat_bps':0,'model':'signed close-to-close simple price return on fixed notional minus fixed round-trip cost; independent exposures, not actual execution or short selling','stress':'adapt_error_stress deliberately assigns large magnitude to wrong nonflat ADAPT predictions; not a causal or probability model','no_market_adoption':True}
SHA=digest(PLAN)
def freeze(rows):
    d=R['decisions'](rows);return d,digest(d)
def price_moves(rows,d,scenario):
    if scenario not in PLAN['magnitude_scenarios']:raise ValueError('scenario')
    result=[]
    for r,x in zip(rows,d):
        y=r['outcome']; a=x['predictions']['ADAPT']; direct=r['direction']
        if y is None: v=None
        elif y=='FLAT':v=0
        else:
            large=(scenario=='continuation_large' and y==direct or scenario=='reversal_large' and y!=direct or scenario=='adapt_error_stress' and a is not None and a!=y)
            v=(400 if large else 100)*(1 if y=='UP' else -1)
        result.append({'id':r['id'],'received':r['received'],'return_bps':v})
    return result

def evaluate(rows,d,h,moves,cost,cutoff):
    if type(cost) is not int or cost not in PLAN['round_trip_cost_bps']:raise ValueError('cost')
    if len(moves)!=len(rows):raise ValueError('missing move row')
    for r,m in zip(rows,moves):
        if set(m)!={'id','received','return_bps'} or m['id']!=r['id'] or m['received']!=r['received']:raise ValueError('move binding')
        v=m['return_bps']; y=r['outcome']
        if y is None:
            if v is not None:raise ValueError('unobserved return')
        elif type(v) is not int or (y=='FLAT' and v!=0) or (y=='UP' and v not in (100,400)) or (y=='DOWN' and v not in (-100,-400)):raise ValueError('return/outcome mismatch')
    scored=R['evaluate'](rows,d,h,cutoff); out=[]
    for s,m in zip(scored,moves):
        v=m['return_bps'] if s['outcome'] is not None else None
        pay={}
        for k,p in s['predictions'].items():
            if not s['eligible']: state='INELIGIBLE'; gross=net=fee=None
            elif p is None: state='ABSTAIN';gross=net=fee=0
            elif v is None:state='UNRESOLVED';gross=net=fee=None
            else:state='SCORED';gross=v*(1 if p=='UP' else -1);fee=cost;net=gross-fee
            pay[k]={'state':state,'gross_bps':gross,'cost_bps':fee,'net_bps':net,'net_yen':None if net is None else net*10}
        out.append(dict(s,return_bps=v,payoff=pay))
    return out

def summarize(rs):
    result={}; eligible=[r for r in rs if r['eligible']]; common=[r for r in eligible if r['outcome'] is not None]
    for k in POL:
        p=[r['payoff'][k] for r in eligible]; scored=[x for x in p if x['state']=='SCORED']; un=sum(x['state']=='UNRESOLVED' for x in p); abstain=sum(x['state']=='ABSTAIN' for x in p)
        gross=sum(x['gross_bps'] for x in scored); cost=sum(x['cost_bps'] for x in scored); net=gross-cost; hits=sum(r['hits'][k] is True for r in eligible)
        wins=sum(x['net_bps']>0 for x in scored); losses=sum(x['net_bps']<0 for x in scored)
        result[k]={'predictions':len(scored)+un,'scored':len(scored),'unresolved_predictions':un,'abstained':abstain,'hits':hits,'accuracy':str(F(hits,len(scored))) if scored else None,'economic_wins':wins,'economic_losses':losses,'economic_flat':len(scored)-wins-losses,'gross_yen':gross*10,'cost_yen':cost*10,'observed_net_yen':net*10,'all_selected_net_yen':None if un else net*10,'net_yen_per_resolved_opportunity':str(F(net*10,len(common))) if common else None,'break_even_cost_bps':str(F(gross,len(scored))) if scored else None}
    # paired comparison on ADAPT-abstained, resolved opportunities; counterfactual static scores, not foregone actual income
    abst=[r for r in common if r['payoff']['ADAPT']['state']=='ABSTAIN']; missed={k:sum(r['payoff'][k]['net_yen'] for r in abst) for k in ('CONTINUE','REVERSE')}
    return {'total':len(rs),'eligible':len(eligible),'resolved_opportunities':len(common),'unknown_opportunities':len(eligible)-len(common),'policies':result,'adapt_abstained_resolved':len(abst),'static_net_on_adapt_abstentions_yen':missed}

def examples():
    out={}
    for name,(rows,_) in R['fixtures']().items():
        d,h=freeze(rows); cases={}
        for s in PLAN['magnitude_scenarios']:
            moves=price_moves(rows,d,s);cases[s]={'moves_sha':digest(moves),'costs':{str(c):summarize(evaluate(rows,d,h,moves,c,100)) for c in PLAN['round_trip_cost_bps']}}
        out[name]={'decision_sha':h,'cases':cases}
    return {'synthetic_only':True,'plan':PLAN,'plan_sha':SHA,'scenarios':out,'market_adoption':False}

def tests():
    out=[]
    def ck(n,a,b):
        if a!=b:raise AssertionError((n,a,b))
        out.append({'name':n,'pass':True})
    def reject(n,fn):
        try:fn()
        except ValueError:ck(n,True,True);return
        raise AssertionError(n)
    for name,(rows,_) in R['fixtures']().items():
        d,h=freeze(rows); base=R['summary'](R['evaluate'](rows,d,h,100))
        for scenario in PLAN['magnitude_scenarios']:
            moves=price_moves(rows,d,scenario); prev=None
            for cost in PLAN['round_trip_cost_bps']:
                tag=f'{name}:{scenario}:{cost}'; rs=evaluate(rows,d,h,moves,cost,100); sm=summarize(rs)
                ck(tag+':denominator',[sm[k] for k in ('total','eligible','resolved_opportunities','unknown_opportunities')],[74,73,72,1])
                for k,p in sm['policies'].items():
                    ck(tag+':frozen prediction '+k,[p[t] for t in ('predictions','scored','hits','accuracy','abstained','unresolved_predictions')],[base['policies'][k][t] for t in ('predictions','scored','hits','accuracy','abstained','unresolved_predictions')])
                    # Independent rational arithmetic directly on fixed notional and signed return.
                    vals=[F(100000,10000)*(m['return_bps']*(1 if x['predictions'][k]=='UP' else -1)-cost) for x,m in zip(d,moves) if x['predictions'][k] is not None and m['return_bps'] is not None]
                    ck(tag+':oracle net '+k,p['observed_net_yen'],sum(vals));ck(tag+':oracle wins '+k,p['economic_wins'],sum(v>0 for v in vals));ck(tag+':oracle cost '+k,p['cost_yen'],len(vals)*cost*10)
                    ck(tag+':unknown total '+k,p['all_selected_net_yen'],None if p['unresolved_predictions'] else sum(vals))
                    if prev is not None:ck(tag+':cost sensitivity '+k,p['observed_net_yen'],prev['policies'][k]['observed_net_yen']-(cost-prev_cost)*10*len(vals))
                for i,r in enumerate(rs):
                    ck(tag+f':row {i}',r['return_bps'],moves[i]['return_bps'])
                    ck(tag+f':no direction {i}',r['payoff']['NO_DIRECTION']['net_yen'],0 if r['eligible'] else None)
                prev=sm;prev_cost=cost
            for cutoff in (0,10,30,73):
                rs=evaluate(rows,d,h,moves,20,cutoff)
                ck(f'{name}:{scenario}:cutoff {cutoff}',[r['return_bps'] for r in rs],[m['return_bps'] if m['received'] is not None and m['received']<=cutoff else None for m in moves[:cutoff+1]])
        moves=price_moves(rows,d,'symmetric');bad=[dict(m) for m in moves];bad[0]['id']='bad';reject(name+':wrong id',lambda:evaluate(rows,d,h,bad,20,100));bad=[dict(m) for m in moves];bad[0]['return_bps']=999;reject(name+':wrong magnitude',lambda:evaluate(rows,d,h,bad,20,100));reject(name+':short moves',lambda:evaluate(rows,d,h,moves[:-1],20,100));reject(name+':bad hash',lambda:evaluate(rows,d,'0'*64,moves,20,100));reject(name+':bad cost',lambda:evaluate(rows,d,h,moves,-1,100));reject(name+':unknown scenario',lambda:price_moves(rows,d,'bad'))
    return {'passed':len(out),'tests':out}
if __name__=='__main__':
    p=argparse.ArgumentParser();g=p.add_mutually_exclusive_group(required=True);g.add_argument('--self-test',action='store_true');g.add_argument('--example',action='store_true');a=p.parse_args();print(json.dumps(tests() if a.self_test else examples(),indent=2,sort_keys=True))
