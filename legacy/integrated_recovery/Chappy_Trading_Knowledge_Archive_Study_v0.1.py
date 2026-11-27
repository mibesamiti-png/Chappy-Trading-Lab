"""R105: bounded archived-candidate requalification, synthetic only."""
import argparse, hashlib, json, math, runpy
from pathlib import Path
import numpy as np
P=Path(__file__).with_name('Chappy_Trading_Refresh_Robustness_Study_v0.1.py')
if hashlib.sha256(P.read_bytes()).hexdigest()!='c791a4e064e02d302d0a41a7c5955c613483d855e327f3cc1d7e6306dddfee88':raise ValueError('R104 hash')
R=runpy.run_path(str(P)); B=R['R']; T=R['T']; H=R['H']; SHIFT=R['SHIFT']; TRAIN=B['TRAIN']; LOOKS=B['LOOKS']; SEEDS=range(105000,105064)
K={n:B['R']['cutoff'](n,400) for n in LOOKS}
METHODS=('MATCHED','BLOCK_SPEND','NEW_SPLIT','ARCHIVE_RACE')
PLAN=dict(cases=R['CASES'],seeds=list(SEEDS),methods=METHODS,initial_alpha_per_look='1/200',refresh_alpha_per_candidate_look='1/400',max_refresh_candidates=2,look_slots=LOOKS,trigger='R103 BLOCK_SPEND unchanged',refresh_train=TRAIN,selection='first independent pass, old wins simultaneous tie; deduplicate, WAIT not audited',synthetic_only=True,fee_per_calendar_slot=1)
SHA=hashlib.sha256(json.dumps(PLAN,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def audit(x,y,j,start):
    ix=np.flatnonzero(T[j,x[start:]])+start; wins=T[j,x[ix]]==y[ix]; cs=np.cumsum(wins); end=len(x); n=len(ix); passed=False
    for k in LOOKS:
        if len(ix)<k:break
        if int(cs[k-1])>=K[k]:end=int(ix[k-1])+1;n=k;passed=True;break
        if k==LOOKS[-1]:end=int(ix[k-1])+1;n=k
    return dict(j=j,end=end,n=n,w=int(cs[n-1]) if n else 0,passed=passed)
def race(x,y,js,start):
    a=[audit(x,y,j,start) for j in js]; winners=[z for z in a if z['passed']]; w=min(winners,key=lambda z:z['end']) if winners else None
    end=w['end'] if w else max((z['end'] for z in a),default=start)
    # Record only evidence available at actual stopping time; never expose future counterfactual audit.
    a=[audit(x[:end],y[:end],j,start) for j in js]
    return w,end,a

def simulate(x,y,base,method):
    if method=='BLOCK_SPEND':return base
    cut=base['refresh']
    if cut is None:return base
    first=B['simulate'](x[:cut],y[:cut],'BLOCK_SPEND'); old=first['epochs'][0]['candidate']; h=len(x); te=min(cut+TRAIN,h)
    out={**first,'refresh':cut,'epochs':list(first['epochs'])}
    def charge(a,b):out['fees']+=b-a;out['post_net']-=max(0,b-max(a,SHIFT));out['net']-=b-a
    charge(cut,te)
    if te-cut<TRAIN:return out
    new=B['R']['select'](x[cut:te],y[cut:te]);js=list(dict.fromkeys(j for j in ([old,new] if method=='ARCHIVE_RACE' else [new]) if j))
    w,end,a=race(x,y,js,te);charge(te,end)
    e=dict(start=cut,train_end=te,old=old,new=new,candidates=js,audits=a,audit_end=end,pass_at=end if w else None,candidate=w['j'] if w else 0,live_end=h if w else None);out['epochs'].append(e)
    if w:
        d=T[w['j'],x]; ix=np.flatnonzero(d[te:])+te; wins=d[ix]==y[ix];cs=np.concatenate(([0],np.cumsum(wins)));k=np.arange(w['n'],len(ix)); allowed=(k>=4)&((cs[k]-cs[np.maximum(0,k-4)])>=3);live=ix[k[allowed]];pnl=np.where(d[live]==y[live],800,-1200);gross=int(pnl.sum());out['gross']+=gross;out['net']+=gross;out['post_net']+=int(pnl[live>=SHIFT].sum());out['trades']+=len(live);charge(end,h)
    return out

def independent(x,y,js,start):
    # chronological race; old-first order is fixed before observing audit results
    active=list(js); hist={j:[] for j in js}
    if not active:return None,start,hist
    for i in range(start,len(x)):
        winners=[]
        for j in list(active):
            if not T[j,x[i]]:continue
            hist[j].append(int(T[j,x[i]]==y[i]));n=len(hist[j])
            if n in LOOKS and sum(hist[j])>=K[n]:winners.append(j)
            if n==LOOKS[-1]:active.remove(j)
        if winners:return winners[0],i+1,hist
        if not active:return None,i+1,hist
    return None,len(x),hist

def study():
    counts={}; summary={}
    def ck(k,a,b):
        if a!=b:raise AssertionError((k,a,b))
        counts[k]=counts.get(k,0)+1
    for n,k in K.items():
        tail=lambda z:sum(math.comb(n,i)*3**i*2**(n-i) for i in range(z,n+1));ck('integer_cutoff',400*tail(k)<=5**n<400*tail(k-1),True)
    for case in R['CASES']:
        rows={m:[] for m in METHODS}
        for seed in SEEDS:
            x,y=R['series'](seed,case);base=B['simulate'](x,y,'BLOCK_SPEND');matched=B['simulate'](x,y,'MATCHED')
            for m in METHODS:
                r=matched if m=='MATCHED' else simulate(x,y,base,m);rows[m].append(r)
                ck('accounting',r['net'],r['gross']-r['fees']);ck('fee_bound',0<=r['fees']<=H,True);ck('initial_match',r['epochs'][0]['pass_at'],base['epochs'][0]['pass_at']);ck('epoch_limit',len(r['epochs'])<=2,True)
                if m in ('NEW_SPLIT','ARCHIVE_RACE') and r['refresh'] is not None:
                    ck('trigger_match',r['refresh'],base['refresh'])
                    if len(r['epochs'])<2:continue
                    e=r['epochs'][1];js=e['candidates'];w,end,hist=independent(x,y,js,e['train_end']);ck('race_oracle',(e['candidate'] or None,e['audit_end']),(w,end));ck('unique_candidates',len(js),len(set(js)));ck('candidate_budget',len(js)<=2,True)
                    for a in e['audits']:ck('audit_counts',(a['n'],a['w']),(len(hist[a['j']]),sum(hist[a['j']])));ck('audit_prefix',a,audit(x[:end],y[:end],a['j'],e['train_end']))
                    ck('frozen_selection',e['new'],B['R']['select'](x[e['start']:e['train_end']],y[e['start']:e['train_end']]))
                    first=B['simulate'](x[:e['start']],y[:e['start']],'BLOCK_SPEND'); gross=first['gross'];trades=first['trades'];post=first['post_net']
                    if w:
                        hh=hist[w][:];
                        for i in range(end,H):
                            if not T[w,x[i]]:continue
                            win=int(T[w,x[i]]==y[i]);p=800 if win else -1200
                            if len(hh)>=4 and sum(hh[-4:])>=3:gross+=p;trades+=1;post+=p if i>=SHIFT else 0
                            hh.append(win)
                    last=H if w else end;post-=max(0,last-max(e['start'],SHIFT));ck('live_oracle',(r['gross'],r['trades'],r['post_net'],r['fees']),(gross,trades,post,first['fees']+last-e['start']))
        summary[case]={}
        for m,rs in rows.items():
            es=[r['epochs'][1] for r in rs if len(r['epochs'])==2];ad=[e for e in es if e['pass_at'] is not None];summary[case][m]=dict(mean_net=sum(r['net'] for r in rs)/len(rs),mean_post_net=sum(r['post_net'] for r in rs)/len(rs),mean_fees=sum(r['fees'] for r in rs)/len(rs),initial_pass=sum(r['epochs'][0]['pass_at'] is not None for r in rs),refresh=sum(r['refresh'] is not None for r in rs),second_pass=len(ad),old_restored=sum(e.get('old')==e['candidate'] and e.get('new')!=e['candidate'] for e in ad),same_candidate=sum(e.get('old')==e.get('new') for e in es if 'old' in e),mean_second_pass_slot=sum(e['pass_at'] for e in ad)/len(ad) if ad else None)
    return dict(passed=sum(counts.values()),counts=counts,plan_sha=SHA),dict(plan=PLAN,plan_sha=SHA,summary=summary)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--outdir',type=Path,required=True);a=p.parse_args();t,e=study()
    for name,z in [('tests',t),('examples',e)]: (a.outdir/f'Trading_Round105_{name}.json').write_text(json.dumps(z,sort_keys=True,indent=2)+'\n')
    print(json.dumps(t))
