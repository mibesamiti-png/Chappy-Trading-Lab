"""R108: paired independent comparison of admitted frozen hypotheses; synthetic only."""
import argparse, hashlib, json, math, runpy
from pathlib import Path
import numpy as np
P=Path(__file__).with_name('Chappy_Trading_Parallel_Review_Study_v0.1.py')
if hashlib.sha256(P.read_bytes()).hexdigest()!='150fd6cfb7d62efb90746205e726c6e1b7830f16fb113b3347894193ac181d0e':raise ValueError('R107 hash')
R=runpy.run_path(str(P)); A=R['A']; B=R['R']; OLD=R['OLD']; NEW=R['NEW']; H=R['H']; netvec=R['netvec']; CASES=R['CASES']; SEEDS=range(108000,108256)
METHODS=('FIRST','POINT512','BOUND512','POINT2048','BOUND2048')
PLAN=dict(cases=CASES,seeds=list(SEEDS),horizon=H,methods=METHODS,comparison=[512,2048],alpha=.05,difference_range=[-1200,1200],switch_fee=200,observation_fee=1,rule='one frozen paired comparison after both pass; keep incumbent unless positive lower bound on future remaining gain exceeds switch fee; point comparator zero bound; no stop rule',admission='R107 unchanged',synthetic_only=True)
SHA=hashlib.sha256(json.dumps(PLAN,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def margin(n):return 2400*math.sqrt(math.log(20)/(2*n))
def choose(inc,other,total,n,remaining,bounded):
    if not n or remaining<=0:return inc
    return other if (total/n-(margin(n) if bounded else 0))*remaining>200 else inc

def run(x,y,method,audits=None):
    h=len(x); aa=audits if audits is not None else [A['audit'](x,y,j,0) for j in (OLD,NEW)]
    passed=[z for z in aa if z['passed']]; inc=min(passed,key=lambda z:z['end'])['j'] if passed else 0
    first=min((z['end'] for z in passed),default=max(z['end'] for z in aa)); start=max(z['end'] for z in aa); end=start; final=inc; total=0;n=0
    if method=='FIRST':end=first
    elif len(passed)==2:
        target=512 if method.endswith('512') else 2048;end=min(h,start+target)
        if end-start==target:
            other=NEW if inc==OLD else OLD; d=netvec(x[start:end],y[start:end],other)-netvec(x[start:end],y[start:end],inc);total=int(d.sum());n=target;final=choose(inc,other,total,n,h-end,method.startswith('BOUND'))
    fee=200 if final!=inc else 0
    return dict(first=first,initial=inc,start=start,end=end,final=final,fee=end,switch_fee=fee,total=total,n=n,segments=[(first,end,inc),(end,h,final)])

def study():
    counts={};summary={}
    def ck(k,a,b):
        if a!=b:raise AssertionError((k,a,b))
        counts[k]=counts.get(k,0)+1
    for name,c in CASES.items():
        a,b,p,q=c;v={0:0,OLD:a*(20*p-1200)/100,NEW:b*(20*q-1200)/100};rows={m:[] for m in METHODS}
        for seed in SEEDS:
            x,y=B['generate'](seed,c);aa=[A['audit'](x,y,j,0) for j in (OLD,NEW)]; rs={m:run(x,y,m,aa) for m in METHODS}
            base=R['run'](x,y,'FIRST');ck('prior_first',(rs['FIRST']['initial'],rs['FIRST']['first']),(base['initial'],base['first']))
            for m,r in rs.items():
                profit,w,l,exp=R['accounting'](x,y,r,v);inc,fin,e,n,total=(r[k] for k in ('initial','final','end','n','total'));sw=inc!=fin
                ck('accounting',profit,800*w-1200*l-e-r['switch_fee']);ck('time',0<=r['first']<=e<=H,True);ck('fee',r['switch_fee'],200*sw);ck('admitted',all(j==0 or any(z['j']==j and z['passed'] and z['end']<=i for z in aa) for i,_,j in r['segments']),True)
                if n:
                    other=NEW if inc==OLD else OLD; ds=[]
                    for i in range(r['start'],e):
                        # independent signed difference, disjoint supports
                        d=(800 if y[i]==1 else -1200) if x[i]==6 else -(800 if y[i]==1 else -1200) if x[i]==0 else 0
                        ds.append(d if inc==OLD else -d)
                    ck('paired_direct',total,sum(ds));ck('range',all(-1200<=z<=1200 for z in ds),True)
                    # independent squared inequality, avoids sqrt-based decision implementation
                    t=total/n-200/(H-e) if e<H else -math.inf
                    expected=t>0 and (not m.startswith('BOUND') or t*t>2400**2*math.log(20)/(2*n))
                    ck('decision_direct',sw,expected)
                else:ck('no_comparison_no_switch',sw,False)
                if seed<108008 and e<H:
                    xx=x.copy();yy=y.copy();xx[e:]=2;yy[e:]=-1;ck('future_mask',run(xx,yy,m)['final'],fin)
                rows[m].append((profit,exp,sw,sw and v[fin]<=v[inc],sw and v[fin]>v[inc],fin,inc,e,n, n>0 and v[NEW if inc==OLD else OLD]>v[inc]))
            for size in (512,2048):
                pp=rs[f'POINT{size}'];bb=rs[f'BOUND{size}'];ck('matched_clock',pp['end'],bb['end']);ck('bound_subset',bb['final']==bb['initial'] or bb['final']==pp['final'],True)
        summary[name]=dict(theory=v,methods={m:dict(mean_net=float(np.mean([r[0] for r in rr])),mean_expected_net=float(np.mean([r[1] for r in rr])),switch=sum(r[2] for r in rr),nonbeneficial_switch=sum(r[3] for r in rr),beneficial_switch=sum(r[4] for r in rr),final_old=sum(r[5]==OLD for r in rr),final_new=sum(r[5]==NEW for r in rr),mean_end=float(np.mean([r[7] for r in rr])),complete=sum(r[8]>0 for r in rr),better_challenger=sum(r[9] for r in rr)) for m,rr in rows.items()})
    for n in (512,2048):
        ck('zero_diff',choose(OLD,NEW,0,n,1000,True),OLD);ck('no_future',choose(OLD,NEW,1200*n,n,0,True),OLD);ck('strong_diff',choose(OLD,NEW,1200*n,n,1000,True),NEW);ck('weak_diff',choose(OLD,NEW,10*n,n,1000,True),OLD);ck('point_weak',choose(OLD,NEW,10*n,n,1000,False),NEW)
    return dict(passed=sum(counts.values()),counts=counts,plan_sha=SHA),dict(plan=PLAN,plan_sha=SHA,margins={str(n):margin(n) for n in (512,2048)},summary=summary)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--outdir',type=Path,required=True);a=p.parse_args();t,e=study()
    for name,z in [('tests',t),('examples',e)]: (a.outdir/f'Trading_Round108_{name}.json').write_text(json.dumps(z,sort_keys=True,indent=2)+'\n')
    print(json.dumps(t))
