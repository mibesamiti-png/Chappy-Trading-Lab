"""R43: retrospective event bundle; no execution, prediction, or live eligibility."""
import csv, json, hashlib, argparse, re
from pathlib import Path
from datetime import datetime
from decimal import Decimal as D
from fractions import Fraction as F
ROOT=Path(__file__).resolve().parent
BASE='Trading_Round43_Event_Bundle'
PROTECTED={
'CTRL.zip':'b8bd4e8d9aacbba177c9d7380310b81ac31b9d245d6d1ceecfb9e495b2b493c6',
'Trading_Prospective_Plan_01.json':'3311941f206b44220374d38e7cef86900cdb1bd480c111d0d2403ad73d1589cb',
'Chappy_Trading_Lab_v1.1.0-rc1.py':'8b314f6c8f495434b4801bffed74e3b08867a0a35561dc29f0e45e68a4b50de8',
'Chappy_Trading_Research_Lab_v0.5.0.py':'bef9720f6649951c8bfec5dbb0c53dd8eda478a8fa5c6bf10d59861a52a704e1',
'Trading_Round26_Consensus/consensus_events.csv':'f747f0a96a4506b922996b3f7d14ce50c40fb802f66b9124911fc5bcf91cdd7c',
'Trading_Round41_Baseline/event_comparison.csv':'d7a608b234d677199b5b66dc9aa5f6f2283807e48f8c86d82763e5267b7c75b5'}
def require(b,msg):
    if not b: raise ValueError(msg)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):
    with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def write(p,rows):
    with p.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def sign(x):return (x>0)-(x<0)
def stamp(s):
    require(bool(re.fullmatch(r'2026-\d{2}-\d{2}T\d{2}:\d{2}',s)),'timestamp format JST minute')
    t=datetime.fromisoformat(s); require(t<datetime(2026,11,26),'holdout');return t
def num(s):
    require(bool(re.fullmatch(r'[0-9]+',s)),'nonnegative integer required');return D(s)
def validate(rows,events):
    seen=set(); out=[]
    for r in rows:
        k=r['kind']; sym=r['symbol'];key=(sym,k,r['metric'],r['period'])
        require(sym in events and key not in seen,'unknown or duplicate');seen.add(key)
        t=stamp(r['published_jst']);e=stamp(events[sym]['release_jst']);require(t.date()==e.date(),'not event day')
        require(all(r[a].startswith('https://') for a in ('source','clock_source')),'missing source')
        old=new=None; pct=None
        if k=='FY_REVISION':
            require((r['metric'],r['period'],r['unit'])==('NET_PROFIT','FY2027','JPY_million'),'FY dimensions')
            old,new=num(r['old']),num(r['new'])
        elif k=='DIVIDEND':
            require(r['metric'] in ('INTERIM_DPS','ANNUAL_DPS','YEAR_END_DPS') and r['period']=='FY2027' and r['unit']=='JPY_per_share','dividend dimensions')
            old,new=num(r['old']),num(r['new'])
        elif k in ('BUYBACK_NEW','BUYBACK_EXPANSION'):
            require((r['metric'],r['period'],r['unit'])==('AUTHORIZED_CAP','PROGRAM','JPY_million'),'cap dimensions')
            new=num(r['new']);require(new>0,'zero cap')
            if k=='BUYBACK_EXPANSION':
                old=num(r['old']);require(new>old>0,'not expansion')
            else: require(r['old']=='','new cap is not a change from zero')
        elif k=='BUYBACK_PROGRESS':
            require((r['metric'],r['period'],r['unit'],r['old'],r['new'])==('EXISTING_PROGRAM','PROGRAM','NA','',''),'progress not cap')
        else: raise ValueError('unsupported kind')
        if old is not None and old!=0:
            pct=100*(new-old)/old
            require(abs(F(pct)-100*(F(new)-F(old))/F(old))<F(1,10**20),'arithmetic')
        if old is not None: direction={-1:'DOWN',0:'UNCHANGED',1:'UP'}[sign(new-old)]
        else: direction='NEW_CAP' if k=='BUYBACK_NEW' else 'PROGRESS_ONLY'
        relation='SAME_MINUTE' if t==e else 'EARLIER' if t<e else 'LATER'
        out.append(dict(r,relation=relation,offset_minutes=int((t-e).total_seconds()/60),change_pct='' if pct is None else str(pct),direction=direction,receipt_jst='',live_eligible=False))
    return out

def bundle(rows,events):
    out=[]
    for sym,e in events.items():
        a=[r for r in rows if r['symbol']==sym]; same=[r for r in a if r['relation']=='SAME_MINUTE']
        def one(kind):
            v=[r for r in same if r['kind'] in kind];require(len(v)<=1,'ambiguous category');return v[0] if v else None
        fy=one({'FY_REVISION'}); div=one({'DIVIDEND'}); cap=one({'BUYBACK_NEW','BUYBACK_EXPANSION','BUYBACK_PROGRESS'})
        out.append(dict(symbol=sym,name=e['name'],release_jst=e['release_jst'],h1_surprise_pct=e['surprise_pct'],fy_net_revision_pct=fy['change_pct'] if fy else '',dividend_state=div['direction'] if div else 'UNVERIFIED',dividend_scope=div['metric'] if div else '',buyback_same_minute=cap['kind'] if cap else 'UNVERIFIED',earlier_buyback_progress=sum(r['kind']=='BUYBACK_PROGRESS' and r['relation']=='EARLIER' for r in a),relative_reaction_pp=e['relative_pp'],reaction_window=e['kind'],coverage='NOT_EXHAUSTIVE',receipt_status='UNVERIFIED',live_eligible=False))
    return out

def main(out):
    for p,h in PROTECTED.items():require(sha(ROOT/p)==h,'protected hash '+p)
    events={r['symbol']:r for r in read(ROOT/'Trading_Round41_Baseline/event_comparison.csv')}
    cons={r['symbol']:r for r in read(ROOT/'Trading_Round26_Consensus/consensus_events.csv')}
    checks=[]
    def check(n,b):require(b,n);checks.append({'test':n,'result':'PASS'})
    for sym,e in events.items():
        c=cons[sym];check('release_'+sym,e['release_jst']==c['release_jst'])
        a,b=e['surprise_pct'],c['consensus_gap_pct'];check('surprise_'+sym,(not a and not b) or abs(D(a)-D(b))<D('0.000000001'))
    source=ROOT/BASE/'disclosures.csv'; original=read(source);rows=validate(original,events);b=bundle(rows,events)
    check('six_events',len(b)==6);check('15_disclosures',len(rows)==15)
    check('all_FY_up',all(D(r['fy_net_revision_pct'])>0 for r in b))
    check('same_minute_caps',sum(r['buyback_same_minute'] in ('BUYBACK_NEW','BUYBACK_EXPANSION') for r in b)==3)
    check('sony_progress_earlier',next(r for r in rows if r['kind']=='BUYBACK_PROGRESS')['offset_minutes']==-240)
    check('unknown_not_zero',sum(r['buyback_same_minute']=='UNVERIFIED' for r in b)==3)
    check('dividend_unverified',sum(r['dividend_state']=='UNVERIFIED' for r in b)==1)
    check('no_live',all(not r['live_eligible'] for r in rows+b))
    check('new_cap_not_zero_baseline',all(not r['change_pct'] for r in rows if r['kind']=='BUYBACK_NEW'))
    for field,value in [('symbol','9999.T'),('unit','JPY_per_share'),('metric','PRETAX'),('old','nan'),('new','-1'),('published_jst','2026-11-26T15:30'),('published_jst','2026-10-28'),('published_jst','2026-10-29T15:30'),('source',''),('clock_source','')]:
        try:validate([dict(original[0],**{field:value})],events)
        except ValueError:check('reject_'+field+'_'+value,True)
        else:raise ValueError('accepted invalid '+field)
    try:validate(original+[original[0]],events)
    except ValueError:check('reject_duplicate',True)
    else:raise ValueError('accepted duplicate')
    for r in rows:
        if r['kind']=='BUYBACK_EXPANSION':check('expansion_30pct',D(r['change_pct'])==30)
    positive=lambda r:D(r['relative_reaction_pp'])>0
    known=[r for r in b if r['h1_surprise_pct']!=''];caps=[r for r in b if r['buyback_same_minute'] in ('BUYBACK_NEW','BUYBACK_EXPANSION')]
    summary={'events':len(b),'disclosures':len(rows),'same_minute':sum(r['relation']=='SAME_MINUTE' for r in rows),'h1_direction_matches':sum(sign(D(r['h1_surprise_pct']))==sign(D(r['relative_reaction_pp'])) for r in known),'h1_known':len(known),'FY_up_positive_reactions':sum(map(positive,b)),'same_minute_new_or_expanded_caps':len(caps),'cap_positive_reactions':sum(map(positive,caps)),'actual_receipt_verified':0,'checks':len(checks)}
    out.mkdir(parents=True,exist_ok=True);write(out/'classified_disclosures.csv',rows);write(out/'bundles.csv',b);write(out/'tests.csv',checks)
    (out/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    (out/'manifest.json').write_text(json.dumps({'mode':'RETROSPECTIVE_ONLY','protected':PROTECTED,'disclosures_sha256':sha(source),'limitations':'Manual web excerpts; minute-level release grouping, not receipt; non-exhaustive; mixed price windows and convenience peers; net profit forecast not H1 pretax/ordinary consensus; no causal or strategy inference; unknown not zero.'},indent=2),encoding='utf-8')
    for p,h in PROTECTED.items():require(sha(ROOT/p)==h,'protected modified '+p)
    print(json.dumps(summary))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,default=ROOT/BASE/'results');main(p.parse_args().out)
