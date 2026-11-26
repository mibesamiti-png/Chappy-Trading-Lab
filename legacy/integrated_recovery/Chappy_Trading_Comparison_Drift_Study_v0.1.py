"""R110: frozen R109 comparison under changing paired payoffs; synthetic only."""
import argparse, hashlib, json, math, runpy
from pathlib import Path
import numpy as np
P=Path(__file__).with_name('Chappy_Trading_Paired_Variance_Study_v0.1.py')
if hashlib.sha256(P.read_bytes()).hexdigest()!='5d29733e2505cc2cc1990e748f8ff775d952a5de9f8b827ab65b29cb77d346b4':raise ValueError('R109 hash')
R=runpy.run_path(str(P)); H=R['H']; JS,W,P0=R['CASES']['overlap_small_edge']; METHODS=R['METHODS']; SEEDS=range(110000,110256)
# change only the 5% disagreement state; common-state probability stays 85%.
# offsets after audit completion (controlled stress, not a market model).
CASES={'stable':[], 'early_flip':[(256,90)], 'mid_flip':[(1024,90)], 'end_flip':[(2048,90)], 'temporary_flip':[(256,90),(1024,10)], 'weakening':[(1024,50)]}
PLAN=dict(cases=CASES,base=[JS,W,P0],methods=METHODS,seeds=list(SEEDS),horizon=H,clock='change offsets relative to completion of stationary audit; common inputs and uniforms across cases',fee=200,observation_fee=1,synthetic_only=True)
SHA=hashlib.sha256(json.dumps(PLAN,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def generate(seed,changes):
    rng=np.random.default_rng(seed);x=np.searchsorted(np.cumsum(W),rng.integers(0,100,H),side='right');u=rng.integers(0,100,H);p=np.array(P0)[x];base=np.where(u<p,1,-1);aa=[R['audit'](x,base,j,0) for j in JS];start=max(z['end'] for z in aa);prob=np.full(H,10,dtype=int)
    for offset,v in changes:prob[min(H,start+offset):]=v
    y=np.where(u<np.where(x==7,prob,p),1,-1);return x,y,aa,prob,start

def theory(j,p):
    # expected per opportunity, in integer yen for our probabilities.
    return sum(W[x]*(int(p if x==7 else P0[x])*R['payoff'](j,x,1)+(100-int(p if x==7 else P0[x]))*R['payoff'](j,x,-1)) for x in range(8))/10000
V={p:{j:theory(j,p) for j in JS} for p in (10,50,90)}
def study():
    counts={};summary={}
    def ck(k,b):
        if not b:raise AssertionError(k)
        counts[k]=counts.get(k,0)+1
    ck('theory',V[10][JS[1]]-V[10][JS[0]]==80 and V[90][JS[1]]-V[90][JS[0]]==-80 and V[50][JS[1]]==V[50][JS[0]])
    for name,changes in CASES.items():
        rows={m:[] for m in METHODS};both=0
        for seed in SEEDS:
            x,y,aa,prob,start=generate(seed,changes);both+=all(z['passed'] for z in aa)
            ck('audit_unchanged',aa==[R['audit'](x,y,j,0) for j in JS]);ck('stationary_prefix',np.all(prob[:start]==10));rs={}
            for m in METHODS:
                n=0 if m=='FIRST' else next(n for n in R['SIZES'] if m.endswith(str(n)));kind=m if not n else m[:-len(str(n))];r=R['run'](x,y,JS,aa,kind,n);rs[m]=r;inc,fin,e,d=(r[k] for k in ('inc','fin','end','d'));sw=fin!=inc
                ck('clock',0<=r['first']<=e<=H);ck('admission',all(j==0 or any(z['j']==j and z['passed'] and z['end']<=t for z in aa) for j,t in [(inc,r['first']),(fin,e)]));ck('fee',r['fee']==200*sw)
                actual=np.r_[R['netvec'](x[r['first']:e],y[r['first']:e],inc),R['netvec'](x[e:],y[e:],fin)];ck('accounting',r['net']==800*int((actual==800).sum())-1200*int((actual==-1200).sum())-e-r['fee'])
                avg=forward=None;gain=0.;better=False;bad=False;good=False
                if len(d):
                    other=next(j for j in JS if j!=inc);lo,hi=R['bounds'](inc,other);ck('range',np.all((d>=lo)&(d<=hi)));s=int(d.sum());ss=int(d@d);var=(n*ss-s*s)/(n*(n-1));q=s/n-200/(H-e);ck('variance',math.isclose(var,r['var'],abs_tol=1e-8));ck('decision',sw==(q>R['margin'](kind,n,hi-lo,var)))
                    if seed<110008:
                        dd=[R['payoff'](other,int(a),int(b))-R['payoff'](inc,int(a),int(b)) for a,b in zip(x[start:e],y[start:e])];ck('direct_difference',np.array_equal(d,dd))
                    avg=float(d.mean());gain=sum(int((prob[e:]==p).sum())*(v[other]-v[inc]) for p,v in V.items())-200;forward=(gain+200)/(H-e);better=gain>0;bad=sw and not better;good=sw and better
                    ck('phase_accounting',sum(int((prob[e:]==p).sum()) for p in V)==H-e)
                    if seed<110004:
                        yy=y.copy();yy[e:]*=-1;rr=R['run'](x,yy,JS,[R['audit'](x,yy,j,0) for j in JS],kind,n);ck('future_mask',(rr['fin'],rr['end'])==(fin,e))
                else:ck('no_switch',not sw)
                rows[m].append(dict(net=r['net'],switch=int(sw),bad=int(bad),good=int(good),better=int(better),completed=int(bool(len(d))),sample=avg,forward=forward,expected_switch_gain=gain if sw else 0,inc_old=int(inc==JS[0]),end=e,margin=r['margin']))
            for n in R['SIZES']:
                a,b,c=(rs[f'{m}{n}'] for m in ('POINT','HOEFF','EB'));ck('matched_clock',a['end']==b['end']==c['end']);ck('subset',b['fin'] in (a['inc'],a['fin']) and c['fin'] in (a['inc'],a['fin']))
        summary[name]=dict(both_admitted=both,methods={m:dict(mean_net=float(np.mean([r['net'] for r in rr])),**{k:sum(r[k] for r in rr) for k in ('switch','bad','good','better','completed','inc_old')},mean_end=float(np.mean([r['end'] for r in rr])),mean_expected_switch_gain=float(np.mean([r['expected_switch_gain'] for r in rr])),old_inc_completed=sum(r['inc_old'] and r['completed'] for r in rr),old_inc_bad=sum(r['inc_old'] and r['bad'] for r in rr),old_inc_mean_sample=float(np.mean([r['sample'] for r in rr if r['inc_old'] and r['completed']])) if any(r['inc_old'] and r['completed'] for r in rr) else None,old_inc_mean_forward=float(np.mean([r['forward'] for r in rr if r['inc_old'] and r['completed']])) if any(r['inc_old'] and r['completed'] for r in rr) else None) for m,rr in rows.items()})
    return dict(passed=sum(counts.values()),counts=counts,plan_sha=SHA),dict(plan=PLAN,plan_sha=SHA,theory=V,summary=summary)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--outdir',type=Path,required=True);a=p.parse_args();t,e=study()
    for name,z in [('tests',t),('examples',e)]: (a.outdir/f'Trading_Round110_{name}.json').write_text(json.dumps(z,sort_keys=True,indent=2)+'\n')
    print(json.dumps(t))
