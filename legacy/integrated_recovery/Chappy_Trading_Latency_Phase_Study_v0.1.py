"""R84: synthetic latency and phase study, no real prices or orders."""
import argparse, hashlib, json, runpy
from pathlib import Path
from itertools import product
from fractions import Fraction as F
P=Path(__file__).with_name('Chappy_Trading_Diagnostic_Response_Study_v0.1.py')
if hashlib.sha256(P.read_bytes()).hexdigest()!='795bb258acfaf491d1710b2671c57373a542f9417ba01b9e5db62fb6cc3c5588':raise ValueError('R83 hash')
R=runpy.run_path(str(P)); POL=R['POLICIES']; N=128; C=20
PLAN=dict(slots=N,half_periods=[2,4,8,16,32,64],delays=[1,3,5,8,12],phases='0,h/2,h,3h/2',window=4,cost_bps=C,notional=100000,amplitude_bps=100,policies=POL,observation='free fixed-delay complete synthetic shadow results',method='R83 unchanged, shifted clock',synthetic_only=True)
def val(h,ph,j):return 100 if ((j+ph)//h)%2==0 else -100
def cases():return [(h,d,ph) for h,d in product(PLAN['half_periods'],PLAN['delays']) for ph in (0,h//2,h,3*h//2)]
def decide(p,i,d,rec):
    ready=[dict(q,received=q['received']+3-d) for q in rec if q['received']<=i and i-d-3<=q['index']<=i-d]
    return R['decide'](p,i+3-d,C,ready)
def receipts(h,d,ph):return [dict(index=j,received=j+d,bps=val(h,ph,j)) for j in range(N)]
def simulate(h,d,ph,p):
    rec=receipts(h,d,ph); rows=[]; total=peak=dd=0
    for i in range(N):
        x=decide(p,i,d,rec);a=x['action'];v=val(h,ph,i);g=10*(a*v-C) if a else 0
        rows.append(dict(index=i,action=a,truth_bps=v,net_yen=g,evidence=x['evidence']));total+=g;peak=max(peak,total);dd=max(dd,peak-total)
    trades=sum(r['action']!=0 for r in rows);correct=sum(r['action']*r['truth_bps']>0 for r in rows)
    return rows,dict(net_yen=total,drawdown_yen=dd,trades=trades,correct=correct,wrong=trades-correct,wait=N-trades,accuracy=str(F(correct,trades)) if trades else None)
def examples():
    data=[dict(half_period=h,delay=d,phase=ph,methods={p:simulate(h,d,ph,p)[1] for p in POL}) for h,d,ph in cases()];agg=[]
    for h,d in product(PLAN['half_periods'],PLAN['delays']):
        group=[r for r in data if r['half_period']==h and r['delay']==d];methods={}
        for p in POL:
            v=[r['methods'][p]['net_yen'] for r in group];methods[p]=dict(mean_yen=sum(v)/4,min_yen=min(v),max_yen=max(v),negative_phases=sum(x<0 for x in v),trades=sum(r['methods'][p]['trades'] for r in group))
        agg.append(dict(half_period=h,delay=d,methods=methods))
    return dict(synthetic_only=True,plan=PLAN,plan_sha=R['digest'](PLAN),cases=data,aggregate=agg)
def tests():
    counts={}
    def ck(n,a,b):
        if a!=b:raise AssertionError((n,a,b))
        counts[n]=counts.get(n,0)+1
    for h,d,ph in cases():
        rec=receipts(h,d,ph)
        for p in POL:
            rows,s=simulate(h,d,ph,p);cum=[0]
            for i,r in enumerate(rows):
                ids=list(range(max(0,i-d-3),i-d+1));vs=[val(h,ph,j) for j in ids];a=1 if p=='FIXED' else 0
                if p not in ('FIXED','WAIT') and len(vs)==4:
                    m=F(sum(vs),4)
                    if m>C:a=1
                    elif m< -C and p in ('SYMMETRIC','TARGETED'):a=-1
                ck('evidence',r['evidence'],ids);ck('action',r['action'],a);ck('pnl',r['net_yen'],10*(a*val(h,ph,i)-C) if a else 0)
                pre=[q for q in rec if q['received']<=i];future=[dict(q,bps=99999) for q in rec if q['received']>i]
                ck('future_mask',decide(p,i,d,pre),decide(p,i,d,pre+future));ck('order',decide(p,i,d,pre),decide(p,i,d,pre[::-1]))
                if d==3:ck('R83_clock',decide(p,i,d,rec),R['decide'](p,i,C,rec))
                cum.append(cum[-1]+r['net_yen'])
            ck('partition',s['correct']+s['wrong']+s['wait'],N);ck('total',s['net_yen'],cum[-1]);ck('drawdown',s['drawdown_yen'],max(cum[a]-cum[b] for b in range(N+1) for a in range(b+1)))
        ck('targeted_equals_symmetric',simulate(h,d,ph,'TARGETED')[1],simulate(h,d,ph,'SYMMETRIC')[1])
    return dict(passed=sum(counts.values()),counts=counts)
if __name__=='__main__':
    p=argparse.ArgumentParser();g=p.add_mutually_exclusive_group(required=True);g.add_argument('--self-test',action='store_true');g.add_argument('--example',action='store_true');a=p.parse_args();print(json.dumps(tests() if a.self_test else examples(),indent=2,sort_keys=True))
