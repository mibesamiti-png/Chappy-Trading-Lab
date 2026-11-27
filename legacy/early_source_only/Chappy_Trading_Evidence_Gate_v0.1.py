"""R27: point-in-time evidence gate. Research only; never emits orders.
Run: python Chappy_Trading_Evidence_Gate_v0.1.py NEW_OUTPUT_DIR
Synthetic timestamps are tests, not historical receipt evidence.
"""
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
import csv, json, hashlib, sys, itertools
P=Path(__file__).resolve().parent
D=Decimal
KINDS=('H1_ACTUAL','H1_EXPECTED','FY_OLD','FY_NEW','FY_EXPECTED','PRICE_REACTION')
POST={'H1_ACTUAL','FY_NEW','PRICE_REACTION'}
PRE=set(KINDS)-POST
MAX_FORECAST_AGE=timedelta(days=30) # research assumption, not calibrated
MAX_PRICE_AGE=timedelta(minutes=5)

def aware(t):return isinstance(t,datetime) and t.tzinfo is not None and t.utcoffset() is not None
@dataclass(frozen=True)
class Fact:
    symbol:str; event:str; kind:str; period:str; metric:str; unit:str
    value:Decimal; observed:datetime; published:datetime; received:datetime|None
    source:str; evidence_id:str; origin:str='SYNTHETIC'

# Context is an explicit event/issuer and expected measurement definitions.
@dataclass(frozen=True)
class Context:
    symbol:str; event:str; release:datetime; h1_metric:str; fy_metric:str
    h1_period:str='H1'; fy_period:str='FY'; price_period:str='POST_5M'
    origin:str='SYNTHETIC'

def definition(c,k):
    if k.startswith('H1_'):return (c.h1_period,c.h1_metric,'JPY_million')
    if k.startswith('FY_'):return (c.fy_period,c.fy_metric,'JPY_million')
    return (c.price_period,'RETURN','pct')

def eligibility(c,f,now):
    if (f.symbol,f.event)!=(c.symbol,c.event):return 'WRONG_EVENT'
    if f.kind not in KINDS:return 'UNKNOWN_KIND'
    if f.origin!=c.origin or f.origin not in ('SYNTHETIC','CAPTURED'):return 'UNVERIFIED_ORIGIN'
    if not f.source.strip() or not f.evidence_id.strip():return 'MISSING_PROVENANCE'
    if not isinstance(f.value,D) or not f.value.is_finite():return 'INVALID_VALUE'
    if (f.period,f.metric,f.unit)!=definition(c,f.kind):return 'INCOMPARABLE_MEASURE'
    if not aware(f.received):return 'NO_VERIFIED_RECEIPT'
    if not all(map(aware,(f.observed,f.published))):return 'INVALID_CLOCK'
    if not f.observed<=f.published<=f.received:return 'CLOCK_ORDER'
    if f.received>=now:return 'NOT_YET_AVAILABLE'
    if f.kind in POST and f.observed<c.release:return 'PRE_RELEASE_POST_FACT'
    if f.kind in PRE and f.received>=c.release:return 'NOT_PRE_RELEASE_CAPTURE'
    if f.kind in ('H1_EXPECTED','FY_EXPECTED') and c.release-f.observed>MAX_FORECAST_AGE:return 'STALE_FORECAST'
    if f.kind=='PRICE_REACTION':
        if f.observed<c.release+timedelta(minutes=5):return 'REACTION_WINDOW_INCOMPLETE'
        if now-f.observed>MAX_PRICE_AGE:return 'STALE_PRICE'
        if f.value<=-100:return 'INVALID_RETURN'
    return 'OK'

def sign(x):return 'UP' if x>0 else 'DOWN' if x<0 else 'FLAT'
def delta(a,b):return None if b==0 else (a-b)/abs(b)*100

def evaluate(c,facts,now):
    if not aware(now) or not aware(c.release):raise ValueError('timezone required')
    accepted={k:[] for k in KINDS}; rejected=[]
    for f in facts:
        status=eligibility(c,f,now)
        if status=='OK':accepted[f.kind].append(f)
        else:rejected.append((f.evidence_id,status))
    vals={}; conflicts=[]; provenance={}
    for k,group in accepted.items():
        # No automatic source majority or last-write-wins. Explicit correction handling deferred.
        if len({f.value for f in group})>1:conflicts.append(k)
        elif group:
            vals[k]=group[0].value;provenance[k]=sorted(set(f.evidence_id for f in group))
    missing=sorted(set(KINDS)-vals.keys())
    axes={}
    for name,a,b in [('H1_SURPRISE','H1_ACTUAL','H1_EXPECTED'),('FY_REVISION','FY_NEW','FY_OLD'),('FY_SURPRISE','FY_NEW','FY_EXPECTED')]:
        if a in vals and b in vals:
            v=delta(vals[a],vals[b]);axes[name]=None if v is None else sign(v)
    if 'PRICE_REACTION' in vals:axes['PRICE_REACTION']=sign(vals['PRICE_REACTION'])
    if now<=c.release:state='PRE_RELEASE_WAIT'
    elif conflicts:state='SOURCE_CONFLICT_REVIEW'
    elif missing or len(axes)!=4 or None in axes.values():state='INSUFFICIENT_EVIDENCE'
    elif set(axes.values())=={'UP'}:state='ALIGNED_UP_RESEARCH'
    elif set(axes.values())=={'DOWN'}:state='ALIGNED_DOWN_RESEARCH'
    elif set(axes.values())=={'FLAT'}:state='ALL_FLAT_RESEARCH'
    else:state='MIXED_SIGNALS_REVIEW'
    return dict(state=state,execution='DISABLED_RESEARCH_ONLY',axes=axes,missing=missing,conflicts=sorted(conflicts),provenance=provenance,rejected=sorted(rejected))

def tests():
    t=datetime.fromisoformat('2026-11-04T14:00:00+09:00'); now=t+timedelta(minutes=6)
    c=Context('SYNTH','E1',t,'PRETAX','PRETAX')
    values=[110,100,100,120,110,2]
    facts=[]
    for k,v in zip(KINDS,values):
        obs=t-timedelta(days=1) if k in PRE else t+timedelta(minutes=5 if k=='PRICE_REACTION' else 0)
        period,metric,unit=definition(c,k)
        facts.append(Fact(c.symbol,c.event,k,period,metric,unit,D(v),obs,obs,obs+timedelta(seconds=1),'synthetic://case',k))
    cases=[]
    def check(name,fs,expected,n=now,ctx=c,reason=None):
        result=evaluate(ctx,fs,n);assert result['state']==expected,(name,result);assert result['execution']=='DISABLED_RESEARCH_ONLY'
        if reason:assert reason in [v for _,v in result['rejected']],(name,result)
        assert evaluate(ctx,list(reversed(fs)),n)==result
        cases.append(dict(case=name,state=result['state'],execution=result['execution'],rejected=';'.join(x[1] for x in result['rejected'])))
    check('aligned_up',facts,'ALIGNED_UP_RESEARCH')
    check('aligned_down',[replace(f,value=D(v)) for f,v in zip(facts,[90,100,100,80,90,-2])],'ALIGNED_DOWN_RESEARCH')
    check('all_flat',[replace(f,value=D(v)) for f,v in zip(facts,[100,100,100,100,100,0])],'ALL_FLAT_RESEARCH')
    for i,f in enumerate(facts):
        check('missing_'+f.kind,facts[:i]+facts[i+1:],'INSUFFICIENT_EVIDENCE')
        check('no_receipt_'+f.kind,facts[:i]+[replace(f,received=None)]+facts[i+1:],'INSUFFICIENT_EVIDENCE',reason='NO_VERIFIED_RECEIPT')
        check('metric_'+f.kind,facts[:i]+[replace(f,metric='WRONG')]+facts[i+1:],'INSUFFICIENT_EVIDENCE',reason='INCOMPARABLE_MEASURE')
        check('disputed_'+f.kind,facts+[replace(f,value=f.value+1,evidence_id=f.kind+'B')],'SOURCE_CONFLICT_REVIEW')
        check('duplicate_'+f.kind,facts+[replace(f,evidence_id=f.kind+'B')],'ALIGNED_UP_RESEARCH')
    def mod(i,**kw):return facts[:i]+[replace(facts[i],**kw)]+facts[i+1:]
    check('mixed_h1',mod(0,value=D(90)),'MIXED_SIGNALS_REVIEW')
    check('mixed_price',mod(5,value=D(-1)),'MIXED_SIGNALS_REVIEW')
    check('mixed_fy',mod(4,value=D(130)),'MIXED_SIGNALS_REVIEW')
    check('pre_release',facts,'PRE_RELEASE_WAIT',t)
    check('same_second_receipt',mod(0,received=now),'INSUFFICIENT_EVIDENCE',reason='NOT_YET_AVAILABLE')
    check('future_receipt',mod(0,received=now+timedelta(seconds=1)),'INSUFFICIENT_EVIDENCE',reason='NOT_YET_AVAILABLE')
    check('late_forecast_receipt',mod(1,received=t),'INSUFFICIENT_EVIDENCE',reason='NOT_PRE_RELEASE_CAPTURE')
    check('early_actual',mod(0,observed=t-timedelta(seconds=1)),'INSUFFICIENT_EVIDENCE',reason='PRE_RELEASE_POST_FACT')
    check('stale_forecast',mod(1,observed=t-timedelta(days=31)),'INSUFFICIENT_EVIDENCE',reason='STALE_FORECAST')
    check('stale_price',facts,'INSUFFICIENT_EVIDENCE',t+timedelta(minutes=11),reason='STALE_PRICE')
    check('short_window',mod(5,observed=t+timedelta(minutes=4)),'INSUFFICIENT_EVIDENCE',reason='REACTION_WINDOW_INCOMPLETE')
    check('bad_clock',mod(0,published=t-timedelta(seconds=1)),'INSUFFICIENT_EVIDENCE',reason='CLOCK_ORDER')
    check('naive_clock',mod(0,published=t.replace(tzinfo=None)),'INSUFFICIENT_EVIDENCE',reason='INVALID_CLOCK')
    check('nan',mod(0,value=D('NaN')),'INSUFFICIENT_EVIDENCE',reason='INVALID_VALUE')
    check('wrong_issuer',mod(0,symbol='OTHER'),'INSUFFICIENT_EVIDENCE',reason='WRONG_EVENT')
    check('retrospective_origin',mod(0,origin='RETROSPECTIVE'),'INSUFFICIENT_EVIDENCE',reason='UNVERIFIED_ORIGIN')
    check('zero_consensus',mod(1,value=D(0)),'INSUFFICIENT_EVIDENCE')
    check('negative_consensus',mod(1,value=D(-100)),'ALIGNED_UP_RESEARCH')
    check('source_missing',mod(0,source=''),'INSUFFICIENT_EVIDENCE',reason='MISSING_PROVENANCE')
    check('different_period',mod(0,period='FY'),'INSUFFICIENT_EVIDENCE',reason='INCOMPARABLE_MEASURE')
    check('different_unit',mod(0,unit='JPY'),'INSUFFICIENT_EVIDENCE',reason='INCOMPARABLE_MEASURE')
    # Adding facts that are not available yet must not alter the visible result axes/state.
    prefix=0
    for sec in range(-60,421,15):
        n=t+timedelta(seconds=sec);a=evaluate(c,facts,n);b=evaluate(c,[f for f in facts if f.received<n],n)
        for key in ('state','axes','missing','conflicts','provenance','execution'):assert a[key]==b[key]
        prefix+=1
    return cases,prefix

def read(p):
    with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def write(p,rows):
    with p.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main(out):
    protected=['CTRL.zip','Trading_Prospective_Plan_01.json','Chappy_Trading_Lab_v1.1.0-rc1.py','Chappy_Trading_Research_Lab_v0.5.0.py','Chappy_Trading_Consensus_Study_v0.1.py','Trading_Round26_Consensus/consensus_events.csv']
    before={n:sha(P/n) for n in protected};assert before['CTRL.zip']=='b8bd4e8d9aacbba177c9d7380310b81ac31b9d245d6d1ceecfb9e495b2b493c6';assert before['Trading_Prospective_Plan_01.json']=='3311941f206b44220374d38e7cef86900cdb1bd480c111d0d2403ad73d1589cb'
    cases,prefix=tests();rows=[]
    for r in read(P/'Trading_Round26_Consensus/consensus_events.csv'):
        assert r['release_jst'][:10]<='2026-11-24' and not r['receipt_jst'] and r['live_eligible']=='False'
        cols=['consensus_gap_pct','fy_revision_pct','fy_reported_gap_pct','reaction_pct'];axis={k:sign(D(r[k])) if r[k] else 'UNKNOWN' for k in cols}
        signs=set(axis.values())-{'UNKNOWN'}; mixed='UP' in signs and 'DOWN' in signs
        rows.append(dict(symbol=r['symbol'],name=r['name'],**axis,known_axes=sum(v!='UNKNOWN' for v in axis.values()),retrospective_conflict=mixed,live_state='INSUFFICIENT_EVIDENCE',reason='NO_VERIFIED_RECEIPT',execution='DISABLED_RESEARCH_ONLY'))
    assert len(rows)==12 and all(r['live_state']=='INSUFFICIENT_EVIDENCE' for r in rows)
    assert before=={n:sha(P/n) for n in protected}
    out.mkdir(parents=True,exist_ok=False);write(out/'synthetic_tests.csv',cases);write(out/'historical_review.csv',rows)
    manifest=dict(synthetic_cases=len(cases),order_invariance_checks=len(cases),prefix_checks=prefix,historical_events=len(rows),historical_eligible=0,retrospective_mixed=sum(r['retrospective_conflict'] for r in rows),complete_axes=sum(r['known_axes']==4 for r in rows),protected=before,notes='No trades. Synthetic tests only. Historical review is diagnostic, not as-of replay. Origin and receipt claims require separate verification; no authenticated feed. Forecast age 30d and price age 5m are provisional test settings.')
    (out/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(manifest,ensure_ascii=False,indent=2))
if __name__=='__main__':main(Path(sys.argv[1]))
