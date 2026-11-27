"""R109: fixed paired empirical Bernstein versus Hoeffding, synthetic only."""
import argparse, hashlib, json, math, runpy
from pathlib import Path
import numpy as np
P=Path(__file__).with_name('Chappy_Trading_Switch_Evidence_Study_v0.1.py')
if hashlib.sha256(P.read_bytes()).hexdigest()!='0153aa54b952e6c2a3ddda4f093190aa6df540f9e4b4966a0055a99f31649d41':raise ValueError('R108 hash')
R=runpy.run_path(str(P)); T=R['B']['T']; audit=R['A']['audit']; netvec=R['netvec']; H=R['H']; OLD=R['OLD']; NEW=R['NEW']
SEEDS=range(109000,109256); ALPHA=.05; SIZES=(512,2048)
# (candidates, probability mass by input, percent probability of upward outcome by input)
CASES={k:([OLD,NEW],[a,0,100-a-b,0,0,0,b,0],[p,50,50,50,50,50,q,50]) for k,(a,b,p,q) in R['CASES'].items()}
for name,f,p in [('overlap_equal',5,50),('overlap_rare_edge',1,10),('overlap_small_edge',5,10),('overlap_large_edge',20,10)]:
    CASES[name]=([9,256],[100-f,0,0,0,0,0,0,f],[85,50,50,50,50,50,50,p])
METHODS=['FIRST']+[f'{m}{n}' for n in SIZES for m in ('POINT','HOEFF','EB')]
PLAN=dict(cases=CASES,seeds=list(SEEDS),methods=METHODS,horizon=H,alpha=ALPHA,fee=200,observation_fee=1,reference='Maurer and Pontil 2009 Theorem 4, applied to negative normalized difference',comparison='one independent fixed window after both pass, no selection between bounds; full 8-state range, no observed range',synthetic_only=True)
SHA=hashlib.sha256(json.dumps(PLAN,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def payoff(j,x,y):return 0 if T[j,x]==0 else 800 if T[j,x]==y else -1200
def bounds(a,b):
    d=[payoff(b,x,y)-payoff(a,x,y) for x in range(8) for y in (-1,1)];return min(d),max(d)
def margin(kind,n,width,var):
    if n<2 or width<0 or var<0:raise ValueError('invalid comparison')
    if kind=='POINT':return 0.
    if kind=='HOEFF':return width*math.sqrt(math.log(1/ALPHA)/(2*n))
    if kind=='EB':return math.sqrt(2*var*math.log(2/ALPHA)/n)+7*width*math.log(2/ALPHA)/(3*(n-1))
    raise ValueError(kind)
def generate(seed,case):
    js,w,p=case;rng=np.random.default_rng(seed);x=np.searchsorted(np.cumsum(w),rng.integers(0,100,H),side='right');y=np.where(rng.integers(0,100,H)<np.array(p)[x],1,-1);return x,y
def run(x,y,js,aa,kind,n):
    h=len(x); passed=[z for z in aa if z['passed']]; inc=min(passed,key=lambda z:z['end'])['j'] if passed else 0; first=min((z['end'] for z in passed),default=max(z['end'] for z in aa)); start=max(z['end'] for z in aa); end=first if kind=='FIRST' else start; fin=inc; d=np.array([],dtype=np.int64); var=mar=0.; width=0
    if kind!='FIRST' and len(passed)==2:
        end=min(h,start+n)
        if end-start==n:
            other=next(j for j in js if j!=inc); lo,hi=bounds(inc,other);width=hi-lo;d=netvec(x[start:end],y[start:end],other)-netvec(x[start:end],y[start:end],inc);var=float(d.var(ddof=1));mar=margin(kind,n,width,var)
            if end<h and (float(d.mean())-mar)*(h-end)>200:fin=other
    fee=200*int(fin!=inc);gross=int(netvec(x[first:end],y[first:end],inc).sum()+netvec(x[end:],y[end:],fin).sum())
    return dict(first=first,start=start,end=end,inc=inc,fin=fin,fee=fee,net=gross-end-fee,d=d,var=var,margin=mar,width=width)
def study():
    counts={}; summary={}
    def ck(k,b):
        if not b:raise AssertionError(k)
        counts[k]=counts.get(k,0)+1
    for name,case in CASES.items():
        js,w,p=case;values={0:0.}
        for j in js:values[j]=sum(w[x]*(p[x]*payoff(j,x,1)+(100-p[x])*payoff(j,x,-1))/10000 for x in range(8))
        rows={m:[] for m in METHODS}
        for seed in SEEDS:
            x,y=generate(seed,case);aa=[audit(x,y,j,0) for j in js];results={}
            for m in METHODS:
                n=0 if m=='FIRST' else next(n for n in SIZES if m.endswith(str(n)));kind=m if not n else m[:-len(str(n))];r=run(x,y,js,aa,kind,n);results[m]=r;inc,fin,e,d=r['inc'],r['fin'],r['end'],r['d'];sw=inc!=fin
                ck('time',0<=r['first']<=e<=H);ck('admission',all(j==0 or any(z['j']==j and z['passed'] and z['end']<=t for z in aa) for j,t in [(inc,r['first']),(fin,e)]));ck('fee',r['fee']==200*sw)
                direct=np.r_[netvec(x[r['first']:e],y[r['first']:e],inc),netvec(x[e:],y[e:],fin)];ck('accounting',r['net']==800*int((direct==800).sum())-1200*int((direct==-1200).sum())-e-r['fee'])
                if len(d):
                    other=next(j for j in js if j!=inc);lo,hi=bounds(inc,other);ck('range',np.all((d>=lo)&(d<=hi)));ck('full_range',r['width']==hi-lo)
                    # independent integer moment formula and exact payoff table check
                    ds=[payoff(other,int(a),int(b))-payoff(inc,int(a),int(b)) for a,b in zip(x[r['start']:e],y[r['start']:e])] if seed<109008 else d.tolist()
                    ck('difference',sum(ds)==int(d.sum()));s=sum(ds);ss=sum(z*z for z in ds);vv=(n*ss-s*s)/(n*(n-1));ck('variance',math.isclose(vv,r['var'],abs_tol=1e-8));q=s/n-200/(H-e) if e<H else -math.inf
                    if kind=='EB': q-=7*(hi-lo)*math.log(40)/(3*(n-1));expected=q>0 and q*q>2*vv*math.log(40)/n
                    elif kind=='HOEFF':expected=q>0 and q*q>(hi-lo)**2*math.log(20)/(2*n)
                    else:expected=q>0
                    ck('decision',sw==expected)
                else:ck('no_switch_without_comparison',not sw)
                if seed<109004 and e<H:
                    xx=x.copy();yy=y.copy();xx[e:]=2;yy[e:]=-1;rr=run(xx,yy,js,[audit(xx,yy,j,0) for j in js],kind,n);ck('future_mask',rr['fin']==fin)
                if name in R['CASES'] and kind in ('FIRST','POINT','HOEFF'):
                    prev=R['run'](x,y,'FIRST' if kind=='FIRST' else ('POINT' if kind=='POINT' else 'BOUND')+str(n),aa);ck('R108_reuse',(r['first'],inc,e,fin)==(prev['first'],prev['initial'],prev['end'],prev['final']))
                rows[m].append((r['net'],int(sw),int(sw and values[fin]<=values[inc]),int(sw and values[fin]>values[inc]),int(len(d)>0),r['margin'],r['var'],int(len(d)>0 and values[next(j for j in js if j!=inc)]>values[inc]),e))
            for n in SIZES:
                pp,hh,bb=(results[f'{m}{n}'] for m in ('POINT','HOEFF','EB'));ck('matched_clock',pp['end']==hh['end']==bb['end']);ck('subset',bb['fin'] in (pp['inc'],pp['fin']))
        summary[name]=dict(theory=values,range=bounds(*js),methods={m:dict(mean_net=float(np.mean([r[0] for r in rr])),switch=sum(r[1] for r in rr),nonbeneficial=sum(r[2] for r in rr),beneficial=sum(r[3] for r in rr),complete=sum(r[4] for r in rr),mean_margin=float(np.mean([r[5] for r in rr if r[4]])) if any(r[4] for r in rr) else None,mean_sd=float(np.mean([math.sqrt(r[6]) for r in rr if r[4]])) if any(r[4] for r in rr) else None,better_challenger=sum(r[7] for r in rr),mean_end=float(np.mean([r[8] for r in rr]))) for m,rr in rows.items()})
    ck('disjoint_range',bounds(OLD,NEW)==(-1200,1200));ck('opposite_range',bounds(9,256)==(-2000,2000));ck('same_range',bounds(9,9)==(0,0));ck('zero_sample_var_penalty',margin('EB',512,4000,0)>0)
    for n in SIZES:
        ck('zero_variance_formula',math.isclose(margin('EB',n,4000,0),28000*math.log(40)/(3*(n-1))))
    return dict(passed=sum(counts.values()),counts=counts,plan_sha=SHA),dict(plan=PLAN,plan_sha=SHA,summary=summary)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--outdir',type=Path,required=True);a=p.parse_args();t,e=study()
    for name,z in [('tests',t),('examples',e)]: (a.outdir/f'Trading_Round109_{name}.json').write_text(json.dumps(z,sort_keys=True,indent=2)+'\n')
    print(json.dumps(t))
