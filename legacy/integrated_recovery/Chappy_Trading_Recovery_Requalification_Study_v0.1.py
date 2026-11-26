"""R113: finite requalification after absolute stop; synthetic only."""
import argparse, hashlib, json, math, runpy
from pathlib import Path
import numpy as np
P=Path(__file__).with_name('Chappy_Trading_Dual_Monitor_Study_v0.1.py')
if hashlib.sha256(P.read_bytes()).hexdigest()!='9c3537714c77c5953314592cb441c6f93a920ab383b5aeb4aed17dd86d358a7f':raise ValueError('R112 hash')
R=runpy.run_path(str(P)); B=R['B']; H=R['H']; JS=R['JS']; K=R['K']; SEEDS=range(113000,113128)
if hashlib.sha256(P.with_name('Chappy_Trading_Knowledge_Archive_Study_v0.1.py').read_bytes()).hexdigest()!='2b33261821e4127ae9cd46329a99db18014c132435d949d315eb16e77241f254':raise ValueError('R105 hash')
A=runpy.run_path(str(P.with_name('Chappy_Trading_Knowledge_Archive_Study_v0.1.py')))
CASES={**R['CASES'],'repeat_loss':[(2048,25,10),(2560,85,10),(4096,25,10)]}
METHODS={'TERMINAL':0,'RECOVER_ONCE':1,'RECOVER_TWICE':2}; COOL=256
PLAN=dict(seeds=list(SEEDS),cases=CASES,methods=METHODS,horizon=H,cooldown=COOL,look_thresholds=A['K'],recovery_alpha='1/400 per candidate/look, <=20 looks total',priority='candidate active at stop first on ties',resume='next opportunity after fresh audit, one resume maximum; absolute monitor only; second stop terminal',observation_fee=1,resume_fee=200,synthetic_only=True)
SHA=hashlib.sha256(json.dumps(PLAN,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def run(x,y,b,base,m):
    h=len(x); s=base['stop']; out=dict(net=base['net'],attempts=[],resume=None,second_stop=None,candidate=None,extra_obs=0,extra_gross=0,extra_fee=0)
    if s is None or not METHODS[m]:return out
    active=b['inc'] if base['rollback'] is not None else b['fin']; js=list(dict.fromkeys([active,*JS])); t=s
    for _ in range(METHODS[m]):
        start=min(h,t+COOL)
        if start==h:t=h;break
        w,end,a=A['race'](x,y,js,start);out['attempts'].append(dict(start=start,end=end,audits=a,winner=w['j'] if w else None));t=end
        if w and end<h:
            j=w['j'];out['resume']=end;out['candidate']=j;out['extra_fee']=200
            p=B['netvec'](x[end:],y[end:],j);stop=R['absolute'](p);t=end+stop if stop is not None and end+stop<h else h
            out['second_stop']=t if t<h else None;out['extra_gross']=int(p[:t-end].sum());break
        if end>=h:break
    out['extra_obs']=t-s;out['net']+=out['extra_gross']-out['extra_obs']-out['extra_fee'];return out

def oracle_audit(x,y,js,start):
    hist={j:[] for j in js};active=list(js)
    for i in range(start,len(x)):
        winners=[]
        for j in list(active):
            v=B['payoff'](j,int(x[i]),int(y[i]));hist[j].append(v>0);n=len(hist[j]);k=A['K'].get(n)
            if k is not None and sum(hist[j])>=k:winners.append(j)
            if n==max(A['K']):active.remove(j)
        if winners or not active:return (winners[0] if winners else None),i+1,hist
    return None,len(x),hist

def study():
    counts={};summary={}
    def ck(k,v):
        if not v:raise AssertionError(k)
        counts[k]=counts.get(k,0)+1
    for n,k in A['K'].items():
        tail=lambda z:sum(math.comb(n,i)*3**i*2**(n-i) for i in range(z,n+1));ck('threshold',400*tail(k)<=5**n<400*tail(k-1))
    ck('budget',max(METHODS.values())*len(JS)*len(A['K'])==20)
    for name,changes in CASES.items():
        rows={m:[] for m in METHODS}
        for seed in SEEDS:
            x,y,aa,c,d,start=R['generate'](seed,changes);b=B['run'](x,y,JS,aa,'EB',2048);base=R['run'](x,y,b,'DUAL');s=base['stop'];active=b['inc'] if base['rollback'] is not None else b['fin'];js=list(dict.fromkeys([active,*JS]))
            ck('initial_audit',aa==[B['audit'](x,y,j,0) for j in JS])
            for m in METHODS:
                r=run(x,y,b,base,m);resume=r['resume'];second=r['second_stop'];attempts=r['attempts'];ck('budget_count',len(attempts)<=METHODS[m]);ck('accounting',r['net']==base['net']+r['extra_gross']-r['extra_obs']-r['extra_fee']);ck('fee',r['extra_fee']==200*int(resume is not None));ck('unchanged',not (s is None or m=='TERMINAL') or r['net']==base['net']);ck('observation',0<=r['extra_obs']<=(H-s if s is not None else 0))
                t=s
                for a in attempts:
                    ck('fresh_clock',a['start']==t+COOL and a['start']<a['end']<=H);t=a['end'];ck('audit_prefix',a['audits']==[A['audit'](x[:t],y[:t],j,a['start']) for j in js]);ck('pass_evidence',a['winner'] is None or any(z['j']==a['winner'] and z['passed'] for z in a['audits']))
                    if seed<113016:
                        w,e,hist=oracle_audit(x,y,js,a['start']);ck('audit_oracle',(w,e)==(a['winner'],a['end']));ck('audit_counts',all((z['n'],z['w'])==(len(hist[z['j']]),sum(hist[z['j']])) for z in a['audits']))
                if resume is not None:
                    ck('resume_clock',s<resume<H and attempts[-1]['end']==resume and attempts[-1]['winner']==r['candidate']);end=second if second is not None else H;ck('resume_pnl',r['extra_gross']==sum(B['payoff'](r['candidate'],int(xx),int(yy)) for xx,yy in zip(x[resume:end],y[resume:end])));ck('resume_obs',r['extra_obs']==end-s)
                    p=B['netvec'](x[resume:],y[resume:],r['candidate']);off=next((i for i in range(32,len(p),32) if sum(p[i-32:i]>0)<=K),None);ck('restop',second==(resume+off if off is not None else None))
                    if seed<113016:
                        yy=y.copy();yy[resume:]*=-1;rr=run(x,yy,b,base,m);ck('future_mask',(rr['resume'],rr['candidate'])==(resume,r['candidate']))
                else:ck('no_trade_before_pass',r['extra_gross']==0 and second is None)
                # Evaluation only: true expected value at resume, not used by run.
                v=None if resume is None else sum(R['W'][i]*(int(d[resume] if i==7 else c[resume])*B['payoff'](r['candidate'],i,1)+(100-int(d[resume] if i==7 else c[resume]))*B['payoff'](r['candidate'],i,-1)) for i in range(8))/10000
                rows[m].append((r,s,v))
        summary[name]={}
        for m,rr in rows.items():
            ad=[(r,s,v) for r,s,v in rr if r['resume'] is not None];summary[name][m]=dict(mean_net=float(np.mean([r['net'] for r,s,v in rr])),initial_stops=sum(s is not None for r,s,v in rr),resumes=len(ad),nonpositive_resumes=sum(v<=0 for r,s,v in ad),second_stops=sum(r['second_stop'] is not None for r,s,v in rr),attempts=sum(len(r['attempts']) for r,s,v in rr),mean_resume_delay=float(np.mean([r['resume']-s for r,s,v in ad])) if ad else None,mean_extra_obs=float(np.mean([r['extra_obs'] for r,s,v in rr])))
    return dict(passed=sum(counts.values()),counts=counts,plan_sha=SHA),dict(plan=PLAN,plan_sha=SHA,summary=summary)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--outdir',type=Path,required=True);a=p.parse_args();t,e=study()
    for name,z in [('tests',t),('examples',e)]:(a.outdir/f'Trading_Round113_{name}.json').write_text(json.dumps(z,sort_keys=True,indent=2)+'\n')
    print(json.dumps(t))
