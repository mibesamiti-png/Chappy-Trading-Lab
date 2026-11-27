"""R64: synthetic forecast sidecar bound to decision prefix; no market data or orders."""
import argparse, copy, hashlib, importlib.util, json, sys
from pathlib import Path
from fractions import Fraction
from dataclasses import asdict
ROOT=Path(__file__).parent

def load(name,filename,pin):
    p=ROOT/filename
    if hashlib.sha256(p.read_bytes()).hexdigest()!=pin:raise RuntimeError(name+' dependency changed')
    s=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(s);sys.modules[name]=m;s.loader.exec_module(m);return m
c=load('r53','Chappy_Trading_Calibration_Study_v0.1.py','9d1e42d1e218a2d9f98bab128cfcebbd205b6629911835620800476d1f6d65be')
i=load('r63','Chappy_Trading_Integrated_Improvement_v0.1.py','fbf899ceb682fc7a99697ce08374a004d350a3a997100dfdeb64b2ae0a74e04e')
a=i.a;e=i.e;r=i.r;need=i.need;digest=c.digest
CASES=('D01','D02','E01','E02','E03')
PROBS={'A':6000,'B':8000,'C':8000}

def prefix():
    ev=e.fixture();idx=next(k for k,x in enumerate(ev) if x['kind']=='allocate');return ev[:idx+1]

def freeze(case_ids,probs,model_sha):
    need(tuple(case_ids)==CASES,'case universe');need(set(probs)<=set(r.SYMBOLS),'forecast symbol');need(all(type(v) is int and 0<=v<=10000 for v in probs.values()),'probability');need(isinstance(model_sha,str) and len(model_sha)==64,'model hash')
    p=e.seal(prefix());dec=[x for x in p['result']['journal'] if x['kind']=='DECISION'];need(len(dec)==3,'decision count')
    rows=[]
    for case in case_ids:
        for d in dec:
            b=d['body'];symbol=b['symbol'];need(b['gate']['gate']=='RESEARCH_ELIGIBLE','gate');rows.append({'case':case,'symbol':symbol,'decision_id':b['id'],'decision_hash':d['hash'],'forecast_id':case+':'+b['id'],'time':d['clock'],'deadline':b['plan']['deadline'],'p':probs.get(symbol)})
    obj={'prefix_head':p['head'],'prefix_count':len(prefix()),'model_sha':model_sha,'cases':list(case_ids),'rows':rows,'scope':'artificial probability sidecar; conditional on resolved; not a historical forecast'}
    return {'manifest':obj,'sha256':digest(obj)}

def evaluate(frozen,expected_manifest,model,expected_model,streams,cutoff):
    m=frozen['manifest'];need(digest(m)==frozen['sha256']==expected_manifest,'forecast anchor');need(m['model_sha']==expected_model==model['sha256'],'model binding');need(digest(model['model'])==expected_model,'model integrity');need(type(cutoff) is int and cutoff>=0,'cutoff');need(set(streams)==set(m['cases'])==set(CASES),'case coverage');need(len(m['rows'])==len(CASES)*3 and len({x['forecast_id'] for x in m['rows']})==len(m['rows']),'forecast coverage')
    fs=[];rs=[];trace=[]
    for case in CASES:
        records,head=streams[case];full=e.restore(records,head);events=[x['event'] for x in full['records']];n=m['prefix_count'];need(n==len(prefix()) and len(events)>=n and e.seal(events[:n])['head']==m['prefix_head']==e.seal(prefix())['head'],'prefix binding')
        need(cutoff>=events[n-1]['at'],'forecast not yet available');review=a.review(records,head,cutoff);pr=e.seal([x for x in events if x['at']<=cutoff]);j=r.j48.Journal.restore(pr['result']['journal'],pr['result']['journal_head']);by={x['id']:x for x in review['rows']};dec={x['body']['id']:x for x in pr['result']['journal'] if x['kind']=='DECISION'};rows=[x for x in m['rows'] if x['case']==case];need({x['decision_id'] for x in rows}==set(by)==set(dec),'decision universe')
        for x in rows:
            v=by[x['decision_id']];d=dec[x['decision_id']];need(x['decision_hash']==v['decision_hash']==d['hash'] and x['symbol']==v['symbol'] and x['time']==d['clock'] and x['deadline']==d['body']['plan']['deadline'] and x['forecast_id']==case+':'+v['id'],'decision binding');need(v['gate']=='RESEARCH_ELIGIBLE','ineligible')
            y=j._review_result(v['id'],cutoff);need(y['outcome']==v['observed_outcome'],'review disagreement');label=None;observed=None
            if y['outcome'] in ('CONFIRMED_OBSERVED','REFUTED'):
                label='CONFIRMED' if y['outcome']=='CONFIRMED_OBSERVED' else 'REFUTED';observed=pr['result']['journal'][y['decisive_seq']-1]['clock'];need(x['time']<observed<=min(cutoff,x['deadline']),'decisive time')
            # Expired without decisive evidence is not proof of complete observation coverage.
            # R53 then reports UNKNOWN rather than treating it as refuted or known expiry.
            if x['p'] is not None:
                fs.append(c.Forecast(x['forecast_id'],x['time'],x['deadline'],x['p'],case));
                if label:rs.append(c.Result(x['forecast_id'],observed,label))
            trace.append({**x,'audit_outcome':y['outcome'],'calibration_label':label or ('OPEN' if cutoff<x['deadline'] else 'UNKNOWN'),'decisive_at':observed,'decisive_ids':y['decisive_ids'],'execution_status':v['status'],'realized_pnl_cents':v['realized_pnl_cents'],'forecast_recorded':x['p'] is not None})
    z=c.evaluate(fs,rs,model,expected_model,cutoff);return {'cutoff':cutoff,'manifest_sha':expected_manifest,'model_sha':expected_model,'eligible':len(trace),'forecast_count':len(fs),'missing_forecasts':len(trace)-len(fs),'trace':trace,'calibration':z,'live_adoption':False}

def inputs(action='SELECT'):
    return {k:(v['records'],v['head']) for k in CASES for v in [e.seal(i.branch(action,i.OUTCOMES[k]))]}

def study():
    train,*_=c.fixtures();model=c.fit(*train);h=model['sha256'];f=freeze(CASES,PROBS,h);b=inputs();s=inputs('WAIT_SIGNAL');return {'model':model,'frozen':f,'before_result':evaluate(f,f['sha256'],model,h,b,115),'observed':evaluate(f,f['sha256'],model,h,b,120),'base':evaluate(f,f['sha256'],model,h,b,145),'strict':evaluate(f,f['sha256'],model,h,s,145)}

def self_test():
    tests=[]
    def ck(n,x,y=True):
        if x!=y:raise AssertionError((n,x,y))
        tests.append({'name':n,'pass':True})
    def reject(n,fn):
        try:fn()
        except (ValueError,KeyError,TypeError):ck(n,True)
        else:ck(n,False)
    z=study();f=z['frozen'];m=z['model'];h=m['sha256'];b=inputs();s=inputs('WAIT_SIGNAL');base=z['base'];strict=z['strict'];v=base['calibration']['overall'];ck('eligible',base['eligible'],15);ck('forecast count',base['forecast_count'],15);ck('resolved',v['resolved'],10);ck('confirmed',v['counts']['CONFIRMED'],8);ck('refuted',v['counts']['REFUTED'],2);ck('unknown',v['counts']['UNKNOWN'],5);ck('confirmed resolved',v['confirmed_over_resolved'],'4/5');ck('lower',v['confirmed_over_all_observed_lower'],'8/15');ck('upper',v['confirmed_over_all_observed_upper'],'13/15');ck('abstained',v['calibration_abstained'],5);ck('raw exact',v['paired_raw_brier'],str((8*Fraction(1,5)**2+2*Fraction(4,5)**2)/10));ck('cal exact',v['paired_calibrated_brier'],str((8*Fraction(5,18)**2+2*Fraction(13,18)**2)/10));ck('same calibration',base['calibration'],strict['calibration']);ck('different execution',base['trace']!=strict['trace']);ck('no adoption',base['live_adoption'],False);ck('pre open',z['before_result']['calibration']['overall']['counts']['OPEN'],15);ck('pre brier null',z['before_result']['calibration']['overall']['raw_brier_resolved'],None);ck('at120 resolved',z['observed']['calibration']['overall']['resolved'],10);ck('at120 open',z['observed']['calibration']['overall']['counts']['OPEN'],5)
    for x in base['trace']:
        ck(x['forecast_id']+' outcome',x['calibration_label'],'UNKNOWN' if x['symbol']=='A' else 'REFUTED' if x['symbol']=='C' and x['case'] in ('D01','D02') else 'CONFIRMED');ck(x['forecast_id']+' decisive',x['decisive_at'],None if x['symbol']=='A' else 120)
    def ev(f=f,sha=f['sha256'],model=m,msha=h,streams=b,t=145):return evaluate(f,sha,model,msha,streams,t)
    for k in ('p','decision_hash','deadline','time','symbol','forecast_id'):
        bad=copy.deepcopy(f);bad['manifest']['rows'][0][k]=None;reject('tamper '+k,lambda:ev(f=bad))
    bad=copy.deepcopy(f);bad['manifest']['rows'][0]['p']=10000;bad['sha256']=digest(bad['manifest']);reject('rehashed forecast',lambda:ev(f=bad));bad=copy.deepcopy(m);bad['model']['mapping']['4']='1';reject('model tamper',lambda:ev(model=bad));reject('wrong model anchor',lambda:ev(msha='0'*64));reject('wrong forecast anchor',lambda:ev(sha='0'*64));reject('case missing',lambda:ev(streams={k:v for k,v in b.items() if k!='E03'}));reject('extra case',lambda:ev(streams={**b,'X':b['E03']}));reject('before decision',lambda:ev(t=114));reject('bool cutoff',lambda:ev(t=True));reject('bad head',lambda:ev(streams={**b,'D01':(b['D01'][0],'0'*64)}));reject('truncated',lambda:ev(streams={**b,'D01':(b['D01'][0][:-1],b['D01'][1])}));reject('bool p',lambda:freeze(CASES,{'A':True},h));reject('invalid p',lambda:freeze(CASES,{'A':10001},h));reject('extra symbol',lambda:freeze(CASES,{'X':5000},h));reject('wrong cases',lambda:freeze(CASES[:-1],PROBS,h))
    missing=freeze(CASES,{'B':8000},h);q=evaluate(missing,missing['sha256'],m,h,b,145);ck('missing denominator',q['eligible'],15);ck('missing forecast count',q['missing_forecasts'],10);ck('no retrospective fill',q['forecast_count'],5);ck('missing not calibration result',q['calibration']['overall']['n'],5)
    for t in (115,120,140,145):
        cut={k:(v['records'],v['head']) for k in CASES for v in [e.seal([x['event'] for x in b[k][0] if x['event']['at']<=t])]};ck('prefix '+str(t),ev(t=t),ev(streams=cut,t=t))
    return {'test_count':len(tests),'tests':tests}
if __name__=='__main__':
    p=argparse.ArgumentParser();g=p.add_mutually_exclusive_group(required=True);g.add_argument('--self-test',action='store_true');g.add_argument('--example',action='store_true');x=p.parse_args();print(json.dumps(self_test() if x.self_test else study(),sort_keys=True,indent=2))
