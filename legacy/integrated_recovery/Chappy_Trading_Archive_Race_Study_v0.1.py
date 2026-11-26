"""R106: frozen two-candidate race, synthetic independent opportunities only."""
import argparse, hashlib, json, runpy
from pathlib import Path
import numpy as np
P=Path(__file__).with_name('Chappy_Trading_Knowledge_Archive_Study_v0.1.py')
if hashlib.sha256(P.read_bytes()).hexdigest()!='2b33261821e4127ae9cd46329a99db18014c132435d949d315eb16e77241f254':raise ValueError('R105 hash')
R=runpy.run_path(str(P)); T=R['T']; K=R['K']; LOOKS=R['LOOKS']; OLD=260; NEW=272; H=8192; COMP=512; SEEDS=range(106000,106256)
CASES={'rare_high_accuracy_low_value':(70,1,75,99),'rarer_higher_value':(70,20,65,95),'both_frequent_new_better':(60,40,75,95),'very_frequent_old_better':(95,5,70,99),'equal_value':(50,50,75,75),'break_even':(70,20,60,60)}
PLAN=dict(cases=CASES,seeds=list(SEEDS),horizon=H,comparison=COMP,old=OLD,new=NEW,looks=LOOKS,alpha_per_candidate_look='1/400',methods=['FIRST','WAIT_COMPARE'],cost_per_observation=1,win=800,loss=-1200,monitor=False,synthetic_only=True)
SHA=hashlib.sha256(json.dumps(PLAN,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def generate(seed,case):
    a,b,p,q=case; rng=np.random.default_rng(seed); u=rng.integers(0,100,H); v=rng.integers(0,100,H); x=np.where(u<a,0,np.where(u<a+b,6,2)); y=np.where(v<np.where(x==0,p,np.where(x==6,q,50)),1,-1); return x,y

def canonical(js):return list(dict.fromkeys(j for j in js if j))
def netvec(x,y,j):
    d=T[j,x];return np.where(d==0,0,np.where(d==y,800,-1200))
def decision(x,y,js,method):
    if method=='FIRST':
        w,end,_=R['race'](x,y,js,0);return (w['j'] if w else 0),end
    a=[R['audit'](x,y,j,0) for j in js]; end=max((z['end'] for z in a),default=0);passed=[z['j'] for z in a if z['passed']]
    if not passed:return 0,end
    if len(passed)==1:return passed[0],end
    stop=min(end+COMP,len(x));
    if stop-end<COMP:return 0,stop
    scores=[int(netvec(x[end:stop],y[end:stop],j).sum()) for j in passed]; k=max(range(len(scores)),key=lambda i:scores[i]);return (passed[k] if scores[k]>0 else 0),stop

def study():
    counts={}; summary={}
    def ck(k,a,b):
        if a!=b:raise AssertionError((k,a,b))
        counts[k]=counts.get(k,0)+1
    # Actual R105 race on fixed boundary fixtures; canonicalization belongs to caller.
    x=np.zeros(32,dtype=int); y=np.ones(32,dtype=int); j2=259
    for raw,expected in [([], (0,0)),([0],(0,0)),([OLD,OLD],(OLD,16)),([OLD,j2],(OLD,16)),([j2,OLD],(j2,16)),([NEW],(0,32))]:
        js=canonical(raw); w,end,a=R['race'](x,y,js,0);ck('fixture',(w['j'] if w else 0,end),expected);ck('fixture_unique',len(a),len(js)); z,t,_=R['independent'](x,y,js,0);ck('fixture_oracle',(z or 0,t),expected)
    # Split actual R105 audit at each threshold; exact hit boundary.
    for n,k in K.items():
        for wins in [k-1,k]:
            # arrange losses first to prevent earlier pass when final result is below threshold
            xx=np.zeros(n,dtype=int); yy=np.r_[np.full(n-wins,-1),np.ones(wins)].astype(int); z=R['audit'](xx,yy,OLD,0); ck('threshold_direct',z['passed'],any(m<=n and int((yy[:m]==1).sum())>=K[m] for m in LOOKS))
    for name,c in CASES.items():
        a,b,p,q=c; values={0:0,OLD:a*(20*p-1200)/100,NEW:b*(20*q-1200)/100}; rows={m:[] for m in PLAN['methods']}; both=0; first_lower=0; times=[]
        for seed in SEEDS:
            x,y=generate(seed,c);js=[OLD,NEW]; aa=[R['audit'](x,y,j,0) for j in js];passed=[z['j'] for z in aa if z['passed']];both+=len(passed)==2
            f,ft=decision(x,y,js,'FIRST');w,wt=decision(x,y,js,'WAIT_COMPARE');first_lower+=bool(len(passed)==2 and values[f]<max(values[j] for j in passed));
            if len(passed)==2:times.append([aa[0]['end'],aa[1]['end']])
            if seed<106016:
                o,t,_=R['independent'](x,y,js,0);ck('race_oracle',(f,ft),(o or 0,t))
            for m,j,end in [('FIRST',f,ft),('WAIT_COMPARE',w,wt)]:
                ck('admitted',j==0 or j in passed,True);ck('time_bound',0<=end<=H,True);ck('prefix',(j,end),decision(x[:end],y[:end],js,m) if m=='FIRST' else (j,end)) if m=='FIRST' else None
                if m=='WAIT_COMPARE' and len(passed)==2 and end< H:
                    start=max(z['end'] for z in aa); s=[int(netvec(x[start:end],y[start:end],i).sum()) for i in passed]; best=max(range(len(s)),key=lambda k:s[k]);ck('comparison_window',end-start,COMP);ck('comparison_oracle',j,passed[best] if s[best]>0 else 0)
                vec=netvec(x[end:],y[end:],j);fee=end;profit=int(vec.sum())-fee; wins=int((vec==800).sum());losses=int((vec==-1200).sum());ck('accounting',profit,800*wins-1200*losses-fee)
                ck('direct_count',wins+losses,int(np.count_nonzero(T[j,x[end:]])))
                rows[m].append((j,end,profit,values[j]*(H-end)-fee))
        summary[name]=dict(theory_yen_per_slot={str(k):v for k,v in values.items()},both_pass=both,first_lower_value_among_both=first_lower,mean_pass_slots_given_both=np.mean(times,axis=0).tolist() if times else None,methods={m:dict(old=sum(r[0]==OLD for r in rs),new=sum(r[0]==NEW for r in rs),wait=sum(r[0]==0 for r in rs),mean_end=sum(r[1] for r in rs)/len(rs),mean_net=sum(r[2] for r in rs)/len(rs),mean_expected_net=sum(r[3] for r in rs)/len(rs)) for m,rs in rows.items()})
    return dict(passed=sum(counts.values()),counts=counts,plan_sha=SHA),dict(plan=PLAN,plan_sha=SHA,summary=summary)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--outdir',type=Path,required=True);a=p.parse_args();t,e=study()
    for name,z in [('tests',t),('examples',e)]: (a.outdir/f'Trading_Round106_{name}.json').write_text(json.dumps(z,sort_keys=True,indent=2)+'\n')
    print(json.dumps(t))
