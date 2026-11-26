"""R126: synthetic bounded requalification after R125, no real orders."""
import argparse,hashlib,json,runpy
from pathlib import Path
from collections import Counter
import numpy as np
P=Path(__file__).with_name('Chappy_Trading_Admission_Monitor_Study_v0.1.py');PH='d74b8b35e70f68cf4aca2ff30c38919dae7628956b7fc3b8af01d28be37fccc2'
if hashlib.sha256(P.read_bytes()).hexdigest()!=PH:raise ValueError('parent')
R=runpy.run_path(str(P));G=R['R'];Q,H,A,B=R['Q'],R['H'],R['A'],R['B'];K=G['K'];L=R['K']
MODES=('FLEX_SHORT','SPREAD','FRESH128');POL=('STOP','PAUSE','RESTART','BOTH');SEEDS=list(range(126000,126032))
CASES=dict(R['CASES']);CASES.update(relapse=(True,((0,50),(1024,50),(2048,90),(2304,20),(2432,90),(3200,20))),long_temporary=(True,((0,50),(1024,50),(2048,90),(2304,20),(2800,90))))
PLAN=dict(parent=PH,cases=CASES,modes=MODES,policies=POL,seeds=SEEDS,cap=35,cool=256,short='previous four wins >=3',restart='same candidate once, sparse fixed schedule from remaining looks, no final boundary activation',thresholds=K,monitor=[32,L],fee=200,obs=1)
SHA=hashlib.sha256(json.dumps(PLAN,sort_keys=True).encode()).hexdigest()
def run(y,z,p,scalar=False):
    a=z['actions'].copy();ad=z['admissions'].get('recovery1') or z['admissions'].get('recovery2');spent=z['spent'];obs=fee=0;stops=[];groups=[];looks=[];resume=start=None
    if ad:
        j,t=ad;hit=(y==Q[j,7]).astype(int);a[t:]=0
        for epoch in (1,2):
            end=H
            if scalar:
                for i in range(t,H):
                    if p not in ('PAUSE','BOTH') or (i>=t+4 and sum(hit[i-4:i])>=3):a[i]=j
                    if (i+1-t)%32==0:
                        w=int(sum(hit[i-31:i+1]));groups.append((epoch,i+1,w))
                        if w<=L:end=i+1;stops.append(end);break
            else:
                n=(H-t)//32
                for k,w in enumerate(hit[t:t+n*32].reshape(n,32).sum(axis=1),1):
                    groups.append((epoch,t+k*32,int(w)))
                    if w<=L:end=t+k*32;stops.append(end);break
                if p in ('PAUSE','BOTH'):
                    if end-t>=5:a[t+4+np.flatnonzero(np.convolve(hit[t:end],np.ones(4,dtype=int),'valid')[:-1]>=3)]=j
                else:a[t:end]=j
            obs+=end-t
            if not stops or stops[-1]!=end or epoch==2 or p not in ('RESTART','BOTH') or spent>=35 or end+256>=H:break
            start=end+256;obs+=256;ns=G['SP'][min(5,35-spent)]
            if scalar:
                w=0
                for i in range(start,H):
                    w+=int(hit[i]);obs+=1;n=i+1-start
                    if n in ns and i+1<H:
                        spent+=1;ok=w>=K[n];looks.append((i+1,n,w,ok))
                        if ok:resume=i+1;fee+=200;break
                        if n==ns[-1]:break
            else:
                for n in ns:
                    e=start+n
                    if e>=H:obs+=H-start;break
                    w=int(hit[start:e].sum());spent+=1;ok=w>=K[n];looks.append((e,n,w,ok))
                    if ok:resume=e;obs+=n;fee+=200;break
                else:obs+=n
            if resume is None:break
            t=resume
    gross=int(np.where(a==0,0,np.where(Q[a,7]==y,800,-1200)).sum())
    return dict(actions=a,net=gross-z['fee']-z['cost']-obs-fee,gross=gross,spent=spent,obs=obs,fee=fee,stops=stops,groups=groups,looks=looks,resume=resume,start=start,ad=ad)
def study():
    c=Counter();out={};fixtures={}
    def ck(k,v):
        if not v:raise AssertionError(k)
        c[k]+=1
    def check(y,z,p):
        s=run(y,z,p);q=run(y,z,p,True);ck('scalar_oracle',all(s[k]==q[k] for k in s if k!='actions') and np.array_equal(s['actions'],q['actions']));ck('cap',z['spent']<=s['spent']<=35 and s['spent']==z['spent']+len(s['looks']));ck('accounting',s['net']==s['gross']-z['fee']-z['cost']-s['obs']-s['fee']);ck('monitor_cap',len(s['groups'])<=R['MAX'])
        if s['ad']:
            j,t=s['ad'];ck('prior_unchanged',np.array_equal(s['actions'][:t],z['actions'][:t]));ck('identity',np.all((s['actions'][t:]==0)|(s['actions'][t:]==j)))
            for ep,e,w in s['groups']:ck('monitor_evidence',e-32>=(t if ep==1 else s['resume']) and w==int((y[e-32:e]==Q[j,7]).sum()))
            for e,n,w,ok in s['looks']:ck('fresh_audit',e-n==s['start']>=s['stops'][0]+256 and w==int((y[e-n:e]==Q[j,7]).sum()) and ok==(w>=K[n]))
            if s['stops']:ck('stop_permission',not np.any(s['actions'][s['stops'][0]:s['resume'] or H]))
            if len(s['stops'])==2:ck('terminal',not np.any(s['actions'][s['stops'][1]:]))
            if s['resume']:ck('resume_permission',s['looks'][-1][0]==s['resume'] and s['looks'][-1][-1] and s['resume']<H and s['fee']==200)
        if p=='STOP':
            q=R['apply'](y,z,'STOP');ck('parent_stop',s['net']==q['net'] and np.array_equal(s['actions'],q['actions']) and s['obs']==q['obs'])
        return s
    for name,(req,phases) in CASES.items():
        ps=np.zeros(H,dtype=int)
        for t,v in phases:ps[t:]=v
        totals={m:{p:Counter() for p in POL} for m in MODES}
        for seed in SEEDS:
            y=np.where(np.random.default_rng(seed).random(H)<ps/100,1,-1)
            for m in MODES:
                z=G['simulate'](y,req,m)
                for p in POL:
                    s=check(y,z,p);v=totals[m][p]
                    for k,val in dict(net=s['net'],obs=s['obs'],trades=int(np.count_nonzero(s['actions'])),spent=s['spent'],admitted=int(bool(s['ad'])),stops=int(bool(s['stops'])),resumes=int(s['resume'] is not None),restops=int(len(s['stops'])==2),exhausted=int(bool(s['stops']) and z['spent']==35),attempts=int(s['start'] is not None)).items():v[k]+=val
                    if s['resume']:
                        j=s['ad'][0];prob=ps[s['resume']] if Q[j,7]==1 else 100-ps[s['resume']];v['nonpositive_resume']+=int(prob<=60)
                    if seed==SEEDS[0] and s['ad']:
                        for cut in {s['ad'][1],*s['stops'],*([s['resume']] if s['resume'] else [])}:
                            yy=y.copy();yy[cut:]*=-1;q=run(yy,G['simulate'](yy,req,m),p);ck('future_prefix',np.array_equal(s['actions'][:cut],q['actions'][:cut]) and [g for g in s['groups'] if g[1]<=cut]==[g for g in q['groups'] if g[1]<=cut] and [g for g in s['looks'] if g[0]<=cut]==[g for g in q['looks'] if g[0]<=cut])
        out[name]={m:{p:{**dict(v),'mean_net':v['net']/len(SEEDS),'mean_obs':v['obs']/len(SEEDS)} for p,v in mm.items()} for m,mm in totals.items()}
    for name,t,spent,tail in [('recover',2304,30,np.r_[-np.ones(32),np.ones(H-2336)]),('exhausted',2304,35,np.r_[-np.ones(32),np.ones(H-2336)]),('last_look',H-32-256-16,30,np.r_[-np.ones(32),np.ones(272)]),('relapse',2304,30,np.r_[-np.ones(32),np.ones(512),-np.ones(H-2848)]),('stable',2304,30,np.ones(H-2304)),('weak',2304,30,np.tile([1,1,1,1,-1,-1,-1,-1],(H-2304)//8))]:
        y=np.r_[np.ones(t),tail].astype(int);a=np.zeros(H,dtype=int);a[t:]=A;z=dict(actions=a,admissions={'recovery2':(A,t)},spent=spent,cost=0,fee=0);fixtures[name]={}
        for p in POL:
            s=check(y,z,p);fixtures[name][p]={k:v for k,v in s.items() if k not in ('actions','groups')}
    ck('recover',fixtures['recover']['RESTART']['resume']==2608);ck('exhausted',fixtures['exhausted']['RESTART']['resume'] is None and fixtures['exhausted']['RESTART']['start'] is None);ck('last_no_activation',fixtures['last_look']['RESTART']['resume'] is None and fixtures['last_look']['RESTART']['fee']==0);ck('relapse',len(fixtures['relapse']['BOTH']['stops'])==2);ck('stable_pause',fixtures['stable']['PAUSE']['gross']==fixtures['stable']['STOP']['gross']-3200)
    return dict(passed=sum(c.values()),counts=dict(c),random_trials=len(CASES)*len(SEEDS)*len(MODES)*len(POL),fixture_trials=len(fixtures)*len(POL),plan_sha=SHA),dict(plan=PLAN,plan_sha=SHA,summary=out,fixtures=fixtures)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--outdir',type=Path,required=True);a=p.parse_args();a.outdir.mkdir(exist_ok=True);t,e=study()
    for k,v in [('tests',t),('examples',e)]:(a.outdir/f'Trading_Round126_{k}.json').write_text(json.dumps(v,sort_keys=True,indent=2)+'\n')
    print(json.dumps(t))
