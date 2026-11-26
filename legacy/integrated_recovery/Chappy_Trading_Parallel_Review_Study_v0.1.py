"""R107: operate one admitted frozen hypothesis while auditing another. Synthetic only."""
import argparse, hashlib, json, runpy
from pathlib import Path
import numpy as np
P=Path(__file__).with_name('Chappy_Trading_Archive_Race_Study_v0.1.py')
if hashlib.sha256(P.read_bytes()).hexdigest()!='8d7d56f228ffdc395040bbc240f1c00ab59123a0cc49305950083963423983a7':raise ValueError('R106 hash')
R=runpy.run_path(str(P)); A=R['R']; T=R['T']; OLD=R['OLD']; NEW=R['NEW']; H=R['H']; COMP=R['COMP']; CASES=R['CASES']; SEEDS=range(107000,107256)
METHODS=('FIRST','WAIT_COMPARE','PARALLEL','PARALLEL_COST')
PLAN=dict(cases=CASES,seeds=list(SEEDS),horizon=H,comparison=COMP,methods=METHODS,looks=R['LOOKS'],alpha_per_candidate_look='1/400',observation_fee=1,switch_fee=200,selection='both pass: independent comparison, maximum positive sample total; ties incumbent; incomplete comparison retains incumbent; cost variant requires improvement above switch fee and charges it',synthetic_only=True,monitor=False)
SHA=hashlib.sha256(json.dumps(PLAN,sort_keys=True,separators=(',',':')).encode()).hexdigest()
netvec=R['netvec']
def run(x,y,method,js=(OLD,NEW)):
    js=R['canonical'](js); h=len(x); w,first,_=A['race'](x,y,js,0); incumbent=w['j'] if w else 0
    if method=='FIRST':return dict(first=first,initial=incumbent,end=first,final=incumbent,fee=first,switch_fee=0,segments=[(first,h,incumbent)])
    aa=[A['audit'](x,y,j,0) for j in js];end=max((z['end'] for z in aa),default=0);passed=[z['j'] for z in aa if z['passed']];final=incumbent; sf=0
    if len(passed)==2:
        start=end;end=min(h,start+COMP)
        if end-start==COMP:
            scores={j:int(netvec(x[start:end],y[start:end],j).sum()) for j in passed}; order=passed if method=='WAIT_COMPARE' else [incumbent]+[j for j in passed if j!=incumbent]
            best=max(order,key=scores.get); final=best if scores[best]>0 else 0
            if method=='PARALLEL_COST' and final not in (0,incumbent):
                if scores[final]-scores[incumbent]<=200:final=incumbent
                else:sf=200
        elif method=='WAIT_COMPARE':final=0
    if method=='WAIT_COMPARE':segments=[(end,h,final)]
    else:segments=[(first,end,incumbent),(end,h,final)]
    return dict(first=first,initial=incumbent,end=end,final=final,fee=end,switch_fee=sf,segments=segments)
def accounting(x,y,r,values):
    gross=wins=losses=0; expected=0
    for a,b,j in r['segments']:
        v=netvec(x[a:b],y[a:b],j);gross+=int(v.sum());wins+=int((v==800).sum());losses+=int((v==-1200).sum());expected+=(b-a)*values[j]
    cost=r['fee']+r['switch_fee'];return gross-cost,wins,losses,expected-cost

def oracle(x,y,method,js):
    # Independent chronological implementation; each candidate audit ends at first pass or final look.
    h=len(x); js=list(dict.fromkeys(j for j in js if j)); active=set(js); hist={j:[] for j in js}; passes=[]; incumbent=0; first=None; end=None; scores={}; comp_start=None; final=None; sf=0; gross=0
    if not js:return (0,0,0,0,0,0)
    for i in range(h):
        if method=='FIRST' and first is not None:live=incumbent
        elif end is not None:live=final
        elif method.startswith('PARALLEL'):live=incumbent
        else:live=0
        if live and T[live,x[i]]:gross+=800 if T[live,x[i]]==y[i] else -1200
        if end is not None:continue
        if comp_start is not None:
            for j in passes:
                if T[j,x[i]]:scores[j]+=800 if T[j,x[i]]==y[i] else -1200
            if i+1-comp_start==COMP:
                order=passes if method=='WAIT_COMPARE' else [incumbent]+[j for j in passes if j!=incumbent]
                if method=='WAIT_COMPARE':order=[j for j in js if j in passes]
                best=max(order,key=scores.get);final=best if scores[best]>0 else 0
                if method=='PARALLEL_COST' and final not in (0,incumbent):
                    if scores[final]-scores[incumbent]<=200:final=incumbent
                    else:sf=200
                end=i+1
            continue
        for j in js:
            if j not in active or not T[j,x[i]]:continue
            hist[j].append(int(T[j,x[i]]==y[i]));n=len(hist[j]);ok=n in A['K'] and sum(hist[j])>=A['K'][n]
            if ok:passes.append(j);active.remove(j)
            elif n==R['LOOKS'][-1]:active.remove(j)
        if passes and first is None:incumbent=passes[0];first=i+1
        if method=='FIRST' and first is not None:end=first;final=incumbent
        elif not active:
            if len(passes)==2:comp_start=i+1;scores={j:0 for j in passes}
            else:end=i+1;final=incumbent
    if first is None:first=end if end is not None else h
    if end is None:end=h;final=0 if method=='WAIT_COMPARE' and comp_start is not None else incumbent
    return first,incumbent,end,final,sf,gross-end-sf

def study():
    checks={};summary={}
    def ck(k,a,b):
        if a!=b:raise AssertionError((k,a,b))
        checks[k]=checks.get(k,0)+1
    for name,c in CASES.items():
        a,b,p,q=c;v={0:0,OLD:a*(20*p-1200)/100,NEW:b*(20*q-1200)/100}; rows={m:[] for m in METHODS}
        for seed in SEEDS:
            x,y=R['generate'](seed,c); results={m:run(x,y,m) for m in METHODS}; aa={j:A['audit'](x,y,j,0) for j in (OLD,NEW)}
            for m,r in results.items():
                profit,w,l,exp=accounting(x,y,r,v);f,j,e,k,s=(r[z] for z in ('first','initial','end','final','switch_fee'))
                ck('accounting',profit,800*w-1200*l-e-s);ck('time',0<=f<=e<=H,True);ck('fee',r['fee'],e);ck('admitted',all(z==0 or aa[z]['passed'] and aa[z]['end']<=i for i,_,z in r['segments']),True);ck('segments',all(i<=t for i,t,_ in r['segments']),True)
                ck('first_match',(j,f),R['decision'](x,y,[OLD,NEW],'FIRST'))
                if m in ('FIRST','WAIT_COMPARE'):ck('prior_decision',(k,e),R['decision'](x,y,[OLD,NEW],m))
                if e<H:ck('prefix',r['final'],run(x[:e],y[:e],m)['final'])
                if seed<107008:ck('chronological_oracle',(f,j,e,k,s,profit),oracle(x,y,m,[OLD,NEW]))
                rows[m].append((j,k,f,e,profit,exp,s,int(k!=j and k!=0),int(k==0 and j!=0)))
            ck('parallel_same_budget',results['PARALLEL']['end'],results['WAIT_COMPARE']['end']);ck('cost_same_budget',results['PARALLEL_COST']['end'],results['PARALLEL']['end'])
        summary[name]=dict(theory={str(k):v for k,v in v.items()},methods={m:dict(mean_net=float(np.mean([r[4] for r in rr])),mean_expected_net=float(np.mean([r[5] for r in rr])),mean_first=float(np.mean([r[2] for r in rr])),mean_end=float(np.mean([r[3] for r in rr])),initial_old=sum(r[0]==OLD for r in rr),final_old=sum(r[1]==OLD for r in rr),final_new=sum(r[1]==NEW for r in rr),switch=sum(r[7] for r in rr),stop=sum(r[8] for r in rr),mean_switch_fee=float(np.mean([r[6] for r in rr]))) for m,rr in rows.items()})
    # No-candidate, only candidate, duplicate, same-slot pass, partial comparison fixtures.
    for n,js in [(0,[]),(40,[OLD]),(40,[OLD,OLD]),(40,[OLD,259]),(600,[OLD,259]),(40,[NEW]),(40,[0,OLD])]:
        x=np.zeros(n,dtype=int);y=np.ones(n,dtype=int);v={j:0 for j in [0,OLD,NEW,259]}
        for m in METHODS:
            r=run(x,y,m,js);ck('fixture_oracle',tuple(r[z] for z in ('first','initial','end','final','switch_fee'))+(accounting(x,y,r,v)[0],),oracle(x,y,m,js))
    return dict(passed=sum(checks.values()),counts=checks,plan_sha=SHA),dict(plan=PLAN,plan_sha=SHA,summary=summary)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--outdir',type=Path,required=True);a=p.parse_args();t,e=study()
    for name,z in [('tests',t),('examples',e)]: (a.outdir/f'Trading_Round107_{name}.json').write_text(json.dumps(z,sort_keys=True,indent=2)+'\n')
    print(json.dumps(t))
