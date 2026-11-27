"""Synthetic first-stop comparison; no market data, order, or live adoption interface."""
import argparse, hashlib, itertools, json, math
from collections import defaultdict
from fractions import Fraction as F
from pathlib import Path

R54_SHA='8a5213b3869ad5686b3fe8d22f0318d01ac7a90ada03cdee7ad1c7a4521e37f2'
P0=F(13,18)
PLAN={'n':8,'baseline':'13/18','pre_groups':5,'post_groups':20,'shift_rates':['13/18','3/5','9/20','1/4'],'copy_probabilities':['0','1/4','1/2'],'policies':{'R54_2_OF_2':[2,2,'two-sided'],'3_OF_3':[3,3,'two-sided'],'3_OF_4':[3,4,'two-sided'],'LOW_2_OF_2':[2,2,'low-only']},'gap':'1/4','reset_dependence_at_change':True,'missing':'immediate stop'}
def digest(obj):return hashlib.sha256(json.dumps(obj,sort_keys=True,separators=(',',':')).encode()).hexdigest()
PLAN_SHA=digest(PLAN)

def pmf(p):
    if not isinstance(p,F) or not 0<=p<=1:raise ValueError('p')
    return [F(math.comb(8,k))*p**k*(1-p)**(8-k) for k in range(9)]

def flag(k,side):
    d=F(k,8)-P0
    return int(abs(d)>=F(1,4) if side=='two-sided' else d<=-F(1,4))

def advance(history,k,policy):
    a,b,side=PLAN['policies'][policy]
    if k is None:return history,True
    if type(k) is not int or not 0<=k<=8:raise ValueError('count')
    h=history+(flag(k,side),)
    # Require a complete window, including for 3-of-4.
    return h[-(b-1):],len(h)>=b and sum(h[-b:])>=a

def replay(counts,policy):
    history=();first=None
    for i,k in enumerate(counts,1):
        history,stop=advance(history,k,policy)
        if stop:first=i;break
    return first

def distribution(rates,copy,policy,exact=False,reset_at=()):
    if not isinstance(copy,F) or not 0<=copy<1:raise ValueError('copy probability')
    if policy not in PLAN['policies']:raise ValueError('policy')
    conv=F if exact else float
    states={((),None):conv(1)};alarms=[];survival=[]
    c=conv(copy)
    for i,p in enumerate(rates):
        probs=list(map(conv,pmf(p)));nxt=defaultdict(lambda:conv(0));alarm=conv(0)
        for (history,prev),mass in states.items():
            for k,q in enumerate(probs):
                weight=q if prev is None or i in reset_at else (1-c)*q+c*(k==prev)
                if not weight:continue
                h,stop=advance(history,k,policy)
                if stop:alarm+=mass*weight
                else:nxt[h,k]+=mass*weight
        states=nxt;alarms.append(alarm);survival.append(sum(states.values(),conv(0)))
    return alarms,survival

def metrics(p,copy,policy):
    pre=PLAN['pre_groups'];post=PLAN['post_groups']
    a,s=distribution([P0]*pre+[p]*post,copy,policy,reset_at=(pre,))
    alive=s[pre-1]
    if alive<=0:raise ValueError('no survivors')
    cond=[x/alive for x in a[pre:]]
    detected=sum(cond)
    return {'pre_stop':1-alive,'conditional_stop_by_5':sum(cond[:5]),'conditional_stop_by_10':sum(cond[:10]),'conditional_stop_by_20':detected,'conditional_mean_groups_if_detected':sum((i+1)*x for i,x in enumerate(cond))/detected if detected else None,'conditional_censored_mean_groups':sum((i+1)*x for i,x in enumerate(cond))+post*(1-detected)}

def example():
    out=[]
    for c in map(F,PLAN['copy_probabilities']):
        for name in PLAN['policies']:
            a,s=distribution([P0]*20,c,name)
            for p in map(F,PLAN['shift_rates']):
                out.append({'policy':name,'copy_probability':str(c),'post_p':str(p),'false_stop_20':1-s[-1],**metrics(p,c,name)})
    return {'plan':PLAN,'plan_sha':PLAN_SHA,'rows':out,'live_adoption':False,'note':'Copy model repeats entire previous count with specified probability, otherwise independent binomial; dependence resets at change, including no-shift comparison. First-stop only, conditional on surviving preperiod. All inputs synthetic.'}

def brute(rates,c,policy,reset_at=()):
    probs=[pmf(p) for p in rates];out=[F(0)]*len(rates)
    for seq in itertools.product(range(9),repeat=len(rates)):
        w=F(1)
        for i,k in enumerate(seq):w*=probs[i][k] if i==0 or i in reset_at else (1-c)*probs[i][k]+c*(seq[i-1]==k)
        stop=replay(seq,policy)
        if stop:out[stop-1]+=w
    return out

def self_test():
    tests=[]
    def ck(n,v):
        if not v:raise AssertionError(n)
        tests.append({'name':n,'pass':True})
    def reject(n,fn):
        try:fn()
        except ValueError:ck(n,True)
        else:raise AssertionError(n)
    ck('R54 source hash',hashlib.sha256(Path(__file__).with_name('Chappy_Trading_Sequential_Monitor_v0.1.py').read_bytes()).hexdigest()==R54_SHA)
    ck('fixed plan',digest(PLAN)==PLAN_SHA)
    ck('R54 bad counts',[k for k in range(9) if flag(k,'two-sided')]==[0,1,2,3,8]);ck('low counts',[k for k in range(9) if flag(k,'low-only')]==[0,1,2,3])
    for p in map(F,PLAN['shift_rates']):ck('pmf '+str(p),sum(pmf(p))==1)
    for name in PLAN['policies']:
        ck('good '+name,replay([6]*8,name) is None);ck('missing '+name,replay([6,None,6],name)==2)
        for c in map(F,PLAN['copy_probabilities']):
            rates=[P0,P0,F(1,4),F(1,4)]
            a,s=distribution(rates,c,name,True,(2,));b=brute(rates,c,name,(2,))
            ck('brute '+name+str(c),a==b);ck('mass '+name+str(c),sum(a)+s[-1]==1)
            af,sf=distribution(rates,c,name,False,(2,));ck('float '+name+str(c),max(abs(float(x)-y) for x,y in zip(a,af))<1e-12)
    a,s=distribution([P0]*20,F(0),'R54_2_OF_2',True)
    q=sum(pmf(P0)[k] for k in range(9) if flag(k,'two-sided'))
    ck('R54 two groups',a[1]==q*q)
    ck('R54 20 groups',abs(float(1-s[-1])-0.210016)<1e-5)
    ck('window needs 4',replay([1,1,1,6],'3_OF_4')==4)
    ck('isolated bad',replay([1,6,1,6],'R54_2_OF_2') is None)
    ck('high-only difference',replay([8,8],'R54_2_OF_2')==2 and replay([8,8],'LOW_2_OF_2') is None)
    reject('bad count',lambda:replay([9],'R54_2_OF_2'));reject('bad p',lambda:pmf(F(-1)));reject('bad copy',lambda:distribution([P0],F(1),'R54_2_OF_2'));reject('bad policy',lambda:distribution([P0],F(0),'X'))
    for r in example()['rows']:
        ck('metric bounds '+r['policy']+r['copy_probability']+r['post_p'],0<=r['conditional_stop_by_5']<=r['conditional_stop_by_10']<=r['conditional_stop_by_20']<=1+1e-12 and 0<=r['false_stop_20']<=1 and 0<=r['conditional_censored_mean_groups']<=20+1e-12)
    return {'test_count':len(tests),'tests':tests}

if __name__=='__main__':
    ap=argparse.ArgumentParser();g=ap.add_mutually_exclusive_group(required=True);g.add_argument('--self-test',action='store_true');g.add_argument('--example',action='store_true');a=ap.parse_args();print(json.dumps(self_test() if a.self_test else example(),sort_keys=True,indent=2))
