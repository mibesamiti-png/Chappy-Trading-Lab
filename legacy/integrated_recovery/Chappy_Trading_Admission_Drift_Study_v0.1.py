"""R123: exact piecewise iid admission drift, frozen opposing candidates."""
import argparse, hashlib, json, runpy, math
from pathlib import Path
from fractions import Fraction as F
from collections import Counter
P=Path(__file__).with_name('Chappy_Trading_Admission_Depth_Study_v0.1.py')
HASH='30a626a694630da343775db24ad61ddfc3dd222ebfe5837d6ce30688dbe47a8c'
if hashlib.sha256(P.read_bytes()).hexdigest()!=HASH:raise ValueError('parent hash')
R=runpy.run_path(str(P)); K=R['K']
# Entries (time, evidence window). Both candidates assessed at each look.
S={'PREFIX':((16,16),(32,32)), 'SPREAD':((16,16),(256,256)), 'FULL':tuple((n,n) for n in K), 'FRESH128':((16,16),(256,128)), 'FRESH64':((16,16),(256,64)), 'LATE_FRESH128':((256,128),)}
# (boundary, probability A wins from that boundary onward)
C={'stable70':((0,70),),'stable90':((0,90),),'null':((0,50),),'flip_early':((0,70),(64,30)), 'flip_middle':((0,70),(128,30)), 'flip_late':((0,70),(224,30)), 'late_collapse':((0,90),(240,50)), 'late_recovery':((0,50),(128,70)), 'temporary':((0,50),(64,90),(224,50)), 'after_audit_flip':((0,70),(256,30)), 'weak_collapse':((0,70),(192,55))}
PLAN=dict(parent=HASH,thresholds=K,schedules=S,cases=C,horizons=[512,2048],payoffs=[800,-1200],observation_fee=1,admission_fee=200,scope='exact independent Bernoulli increments with fixed phase changes; first pass; no post-admission monitoring; fixed windows and look dates; no real prices')
SHA=hashlib.sha256(json.dumps(PLAN,sort_keys=True).encode()).hexdigest()
def probs(case,H):
    d=dict(case);p=0;out=[]
    for i in range(H):
        p=d.get(i,p);out.append(p)
    return out

def exact(ps,s):
    looks=dict(s); resets={n-w for n,w in s if n!=w}; active=[1];events=[];cost=F(0)
    for i,p in enumerate(ps[:s[-1][0]]):
        if i in resets:active=[sum(active)]
        nxt=[0]*(len(active)+1)
        for w,v in enumerate(active):nxt[w]+=v*(100-p);nxt[w+1]+=v*p
        active=nxt;n=i+1
        if n not in looks:continue
        win=looks[n];den=100**n;cost+=F(2*sum(active),den);a=b=0
        if len(active)!=win+1:raise ValueError('window')
        for w,v in enumerate(active):
            if w>=K[win]:a+=v;active[w]=0
            elif win-w>=K[win]:b+=v;active[w]=0
        events.append((n,F(a,den),F(b,den),F(sum(active),den)))
    return events,cost

def oracle(ps,s):
    # Independent chunked binomial convolution at phase and evidence boundaries.
    look=dict(s);reset={n-w for n,w in s if n!=w};end=s[-1][0];cuts=sorted({0,end,*look,*reset,*[i for i in range(1,end) if ps[i]!=ps[i-1]]});dist={0:1};e=[];cost=F(0)
    for lo,hi in zip(cuts,cuts[1:]):
        if lo in reset:dist={0:sum(dist.values())}
        p=ps[lo];d=hi-lo;coef=[math.comb(d,k)*p**k*(100-p)**(d-k) for k in range(d+1)];nd={}
        for w,v in dist.items():
            for k,c in enumerate(coef):
                if v and c:nd[w+k]=nd.get(w+k,0)+v*c
        dist=nd
        if hi in look:
            den=100**hi;cost+=F(2*sum(dist.values()),den);a=b=0;keep={};win=look[hi]
            for w,v in dist.items():
                if w>=K[win]:a+=v
                elif win-w>=K[win]:b+=v
                else:keep[w]=v
            dist=keep;e.append((hi,F(a,den),F(b,den),F(sum(dist.values()),den)))
    return e,cost

def metrics(ps,e,cost,H):
    pass_a=pass_b=bad=bad_future=gross=wait=F(0)
    for n,a,b,r in e:
        pass_a+=a;pass_b+=b;wait+=n*(a+b)
        ga=sum(20*p-1200 for p in ps[n:H]);gb=sum(800-20*p for p in ps[n:H]);gross+=a*ga+b*gb
        if ps[n]<=60:bad+=a
        if ps[n]>=40:bad+=b
        if ga<=0:bad_future+=a
        if gb<=0:bad_future+=b
    miss=e[-1][3];wait+=e[-1][0]*miss
    return dict(pass_A=pass_a,pass_B=pass_b,miss=miss,nonpositive_at_admission=bad,nonpositive_remaining=bad_future,expected_net=gross-wait-200*(pass_a+pass_b),expected_gross=gross,expected_wait=wait,expected_looks=cost,final_bad=(e[-1][1] if ps[e[-1][0]]<=60 else F(0))+(e[-1][2] if ps[e[-1][0]]>=40 else F(0)))

def study():
    c=Counter();out={};cache={}
    def ck(k,v):
        if not v:raise AssertionError(k)
        c[k]+=1
    for name,s in S.items():
        ck('budget',2*len(s)<=10);ck('fixed_window',all(w in K and w<=n for n,w in s))
        for case,phase in C.items():
            ps=probs(phase,2048);e,b=exact(ps,s);o,ob=oracle(ps,s);ck('exact_oracle',e==o and b==ob);cache[name,case]=(e,b)
            surv=F(1)
            for n,a,z,r in e:
                ck('mass',a+z+r==surv);ck('nonnegative',min(a,z,r)>=0);surv=r
            ck('budget_consumption',0<=b<=2*len(s))
            rev,rb=exact([100-p for p in ps],s);ck('symmetry',rev==[(n,z,a,r) for n,a,z,r in e] and rb==b)
            # Prefix invariance through each look.
            for n,a,z,r in e:
                changed=ps[:n]+[100-p for p in ps[n:]];ep,_=exact(changed,s);ck('future_mask',[v for v in ep if v[0]<=n]==[v for v in e if v[0]<=n])
            if case.startswith('stable') or case=='null':
                if all(n==w for n,w in s):ck('parent_stationary', (e,b)==R['exact'](ps[0],tuple(n for n,w in s),tuple(n for n,w in s)))
            for H in PLAN['horizons']:
                m=metrics(ps,e,b,H);ck('partition',m['pass_A']+m['pass_B']+m['miss']==1);ck('bad_bounds',0<=m['nonpositive_at_admission']<=1-m['miss'] and 0<=m['nonpositive_remaining']<=1-m['miss']);ck('accounting',m['expected_net']==m['expected_gross']-m['expected_wait']-200*(1-m['miss']))
                out.setdefault(case,{}).setdefault(str(H),{})[name]={k:float(v) for k,v in m.items()}
    for name in S:
        ck('post_boundary_indistinguishable',cache[name,'stable70']==cache[name,'after_audit_flip'])
        e,b=cache[name,'null'];ck('null_union',1-e[-1][3]<=F(2*len(S[name]),700))
    return dict(passed=sum(c.values()),counts=dict(c),exact_cases=len(C)*len(S),economic_cases=len(C)*len(S)*2,plan_sha=SHA),dict(plan=PLAN,plan_sha=SHA,results=out)
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--outdir',type=Path,required=True);args=ap.parse_args();args.outdir.mkdir(exist_ok=True);t,e=study()
    for kind,obj in [('tests',t),('examples',e)]:(args.outdir/f'Trading_Round123_{kind}.json').write_text(json.dumps(obj,sort_keys=True,indent=2)+'\n')
    print(json.dumps(t))
