"""R71: synthetic matched continuation/reversal hypotheses. No market data or orders."""
import argparse, hashlib, json, runpy
from pathlib import Path
from fractions import Fraction as F
from itertools import product
from copy import deepcopy
P=Path(__file__).with_name('Chappy_Trading_Volume_Context_Study_v0.1.py')
if hashlib.sha256(P.read_bytes()).hexdigest()!='e60569d83993846861afa9f5739f9550aa282bc21cba42355d8498ca7e2a961d':raise ValueError('R70 hash')
R=runpy.run_path(str(P)); digest=R['digest']; row=R['row']; end=R['end']; context=R['study']; fixture=R['fixture']
B=R['R']['R']; bar=B['bar']; basefreeze=B['freeze']; baseeval=B['evaluate']
DAY=20; SLOT=6; CUT=end(DAY,SLOT); DEADLINE=end(DAY,SLOT+3)
PLAN={'day':DAY,'slot':SLOT,'horizon':3,'threshold':'1/100','eligibility':'observed short/long context, zero gap, abs body >= 3/4, short target volume >= 2','strata':'target_over_sector >=2 vs <2','policies':['CONTINUE','REVERSE','NO_DIRECTION'],'case_design':'3 synthetic regimes x 2 contexts x 2 signs x 6 cases + 2 missing cases','costs':None,'target':'future close relative to signal close; not executable return'}
SHA=digest(PLAN)
REGIMES={'continuation':[1,1,1,1,-1,0],'reversal':[-1,-1,-1,-1,1,0],'balanced':[1,1,-1,-1,0,0]}

def prefix(stratum,sign):
    rr=fixture(300,100 if stratum=='isolated' else 300,100 if stratum=='isolated' else 300)
    rr=[dict(r,open=100,high=109 if sign==1 else 101,low=99 if sign==1 else 91,close=100+8*sign) if r['symbol']=='X' and r['day']==DAY else r for r in rr]
    return rr+[row(DAY,s,100,o=100,h=102,l=98,c=100) for s in range(3,6)]

def local_bars(rows,cutoff):
    # Translate day/slot timestamps to R68's local clock without changing availability.
    return [bar(r['slot']-3,r['open'],r['high'],r['low'],r['close'],r['volume'],r['received']-DAY*86400-3*300) for r in rows if r['symbol']=='X' and r['regime']=='V1' and r['day']==DAY and 3<=r['slot']<=9 and r['received']<=cutoff]

def freeze(cid,rows):
    if not isinstance(cid,str) or not cid:raise ValueError('case id')
    c=context(rows,DAY,SLOT,CUT)
    b=basefreeze(cid,local_bars(rows,CUT),3,1200)
    s=c['context']['short']; l=c['context']['long']; f=b['feature']
    eligible=bool(f and all(s[k] is not None and l[k] is not None for k in ('target','sector','outside','target_over_sector','sector_over_outside')) and F(f['gap'])==0 and abs(F(f['body_fraction']))>=F(3,4) and F(s['target'])>=2)
    direction='UP' if eligible and F(f['body_fraction'])>0 else 'DOWN' if eligible else None
    return {'case_id':cid,'plan_sha':SHA,'context_sha':digest(c),'base':b,'context':c['context'],'eligible':eligible,'stratum':('isolated' if F(s['target_over_sector'])>=2 else 'shared') if eligible else None,'predictions':{'CONTINUE':direction,'REVERSE':{'UP':'DOWN','DOWN':'UP',None:None}[direction],'NO_DIRECTION':None}}

def evaluate(fr,expected_sha,cid,rows,cutoff=DEADLINE):
    if type(cutoff) is not int or cutoff<CUT:raise ValueError('cutoff')
    if digest(fr)!=expected_sha or fr['case_id']!=cid or fr['plan_sha']!=SHA or freeze(cid,rows)!=fr:raise ValueError('identity')
    b=fr['base']; ev=baseeval(b,digest(b),cid,local_bars(rows,cutoff),cutoff-DAY*86400-3*300)
    outcome=ev['outcome']
    return {'case_id':cid,'eligible':fr['eligible'],'stratum':fr['stratum'],'outcome':outcome,'predictions':fr['predictions'],'hits':{k:None if p is None or outcome=='UNKNOWN' else p==outcome for k,p in fr['predictions'].items()},'pnl':None}

def tail(rows,sign,relative):
    c=next(r['close'] for r in rows if r['symbol']=='X' and r['day']==DAY and r['slot']==SLOT); z=c+sign*relative*3
    return [row(DAY,s,100,o=c,h=max(c,z)+1,l=min(c,z)-1,c=z if s==9 else c) for s in (7,8,9)]

def design():
    return [(f'{reg}:{st}:{sg}:{i}',reg,st,sg,i) for reg,st,sg,i in product(REGIMES,('isolated','shared'),(-1,1),range(6))]+[('missing_future','missing','isolated',1,0),('missing_peer','missing','isolated',1,0)]

def build():
    cases=design(); prefixes={}
    for cid,reg,st,sg,i in cases:
        p=prefix(st,sg)
        if cid=='missing_peer':p=[r for r in p if not(r['symbol']=='S3' and r['day']==DAY)]
        prefixes[cid]=p
    frozen={cid:freeze(cid,p) for cid,p in prefixes.items()}
    manifest={cid:digest(fr) for cid,fr in frozen.items()}
    # Futures constructed only after all decisions are fixed; known artificial design, not blind.
    records=[]
    for cid,reg,st,sg,i in cases:
        p=prefixes[cid]; t=tail(p,sg,REGIMES[reg][i] if reg in REGIMES else 1)
        if cid=='missing_future':t=t[:-1]
        records.append(dict(evaluate(frozen[cid],manifest[cid],cid,p+t),regime=reg))
    return frozen,manifest,records

def summarize(records,expected_ids):
    ids=[r['case_id'] for r in records]
    if len(ids)!=len(set(ids)) or set(ids)!=set(expected_ids):raise ValueError('case denominator')
    eligible=[r for r in records if r['eligible']]; resolved=[r for r in eligible if r['outcome']!='UNKNOWN']
    return {'total':len(records),'eligible':len(eligible),'resolved':len(resolved),'unknown':len(eligible)-len(resolved),'ineligible':len(records)-len(eligible),'outcomes':{k:sum(r['outcome']==k for r in resolved) for k in ('UP','DOWN','FLAT')},'policies':{k:{'predictions':sum(r['predictions'][k] is not None for r in eligible),'scored':sum(r['hits'][k] is not None for r in eligible),'hits':sum(r['hits'][k] is True for r in eligible),'accuracy':str(F(sum(r['hits'][k] is True for r in eligible),sum(r['hits'][k] is not None for r in eligible))) if any(r['hits'][k] is not None for r in eligible) else None} for k in PLAN['policies']}}

def examples():
    fr,m,rs=build(); groups={reg:summarize([r for r in rs if r['regime']==reg],[cid for cid,r,*_ in design() if r==reg]) for reg in (*REGIMES,'missing')}
    return {'synthetic_only':True,'plan':PLAN,'plan_sha':SHA,'manifest_sha':digest(m),'manifest':m,'frozen':fr,'records':rs,'summary':summarize(rs,m),'by_regime':groups,'by_context':{st:summarize([r for r in rs if r['regime'] in REGIMES and r['stratum']==st],[cid for cid,reg,s,*_ in design() if reg in REGIMES and s==st]) for st in ('isolated','shared')},'market_adoption':False}

def tests():
    out=[]
    def ck(n,a,b):
        if a!=b:raise AssertionError((n,a,b))
        out.append({'name':n,'pass':True})
    def reject(n,fn):
        try:fn()
        except ValueError:ck(n,True,True);return
        raise AssertionError(n)
    f,m,rs=build(); by={r['case_id']:r for r in rs}
    for cid,reg,st,sg,i in design()[:72]:
        p=prefix(st,sg); t=tail(p,sg,REGIMES[reg][i]); a=by[cid]; d=REGIMES[reg][i]
        ck(cid+':eligible',a['eligible'],True);ck(cid+':stratum',a['stratum'],st)
        ck(cid+':outcome',a['outcome'],{1:'UP',-1:'DOWN',0:'FLAT'}[sg*d]);ck(cid+':hits',list(a['hits'].values()),[d==1,d==-1,None])
        ck(cid+':future not used',freeze(cid,p+t),f[cid]);ck(cid+':early',evaluate(f[cid],m[cid],cid,p+t,DEADLINE-1)['outcome'],'UNKNOWN')
    e=examples();
    for reg,h1,h2 in [('continuation',16,4),('reversal',4,16),('balanced',8,8)]:
        g=e['by_regime'][reg];ck(reg+':resolved',g['resolved'],24);ck(reg+':hits',[g['policies'][k]['hits'] for k in ('CONTINUE','REVERSE')],[h1,h2]);ck(reg+':abstain',g['policies']['NO_DIRECTION']['accuracy'],None)
    ck('missing future',by['missing_future']['outcome'],'UNKNOWN');ck('missing peer',by['missing_peer']['eligible'],False);ck('denominator', [e['summary'][k] for k in ('total','eligible','resolved','unknown','ineligible')],[74,73,72,1,1]);ck('matched context',e['by_context']['isolated'],e['by_context']['shared']);ck('no market adoption',e['market_adoption'],False)
    cid='continuation:isolated:1:0'; p=prefix('isolated',1); t=tail(p,1,1); a=f[cid]
    reject('wrong hash',lambda:evaluate(a,'0'*64,cid,p+t));reject('wrong case',lambda:evaluate(a,m[cid],'other',p+t));reject('changed prefix',lambda:evaluate(a,m[cid],cid,prefix('shared',1)+t));reject('duplicate case',lambda:summarize(rs+[rs[0]],m));reject('dropped case',lambda:summarize(rs[:-1],m));reject('early cutoff',lambda:evaluate(a,m[cid],cid,p+t,CUT-1));ck('reverse order',freeze(cid,p[::-1]),a)
    return {'passed':len(out),'tests':out}
if __name__=='__main__':
    p=argparse.ArgumentParser(); g=p.add_mutually_exclusive_group(required=True);g.add_argument('--self-test',action='store_true');g.add_argument('--example',action='store_true');a=p.parse_args();print(json.dumps(tests() if a.self_test else examples(),indent=2,sort_keys=True))
