"""Known historical 5m close proxy replay, PAPER ONLY. No broker or network.
Run: python Chappy_Trading_Market_Replay_v0.1.py CTRL.zip NEW_OUTPUT_DIR
All accounts reset each day; no out-of-sample or live execution claims.
"""
import csv, hashlib, importlib.util, json, math, sys, tempfile
from pathlib import Path
from collections import Counter
P=Path(__file__).resolve().parent
def load_module(name,file):
    s=importlib.util.spec_from_file_location(name,P/file);m=importlib.util.module_from_spec(s);sys.modules[name]=m;s.loader.exec_module(m);return m
p=load_module('market_pipeline','Chappy_Trading_Pipeline_Study_v0.2.py'); rel=load_module('market_relative','Chappy_Trading_Relative_Study_v0.1.py')
r=p.r; f=p.f; ls=p.ls; durable=p.d
# Seconds since 09:10 JST. Original data contains no 09:00/09:05 bars.
r.WINDOWS=((0,8400),(12000,22800));r.EXIT_LEAD=360
SYMS=tuple(rel.r.PILOT_SYMBOLS); MODES=('BASE_360','STAGGER_360','MISSING_360','STRICT_180','NEXT_BASE_360','NEXT_STAGGER_360','NEXT_MISSING_360','NEXT_STRICT_180')
NEXT_CLOSE=False
class MarketGate(p.PipelineGate):
    def __init__(self):super().__init__();self.symbols=SYMS
    def eligible(self):
        if super().eligible():return True
        # Experimental pending-only allowance through the next 5m close.
        return bool(NEXT_CLOSE and self.pending and self.session and self.clock<self.session[1]-r.EXIT_LEAD and not self.fault and self.sync is not None and len(self.last)==len(self.symbols) and set(self.last.values())=={self.sync} and self.clock-self.sync<=1200 and self.clock-self.pending["created"]<=300)
    def state(self):return dict(super().state(),market_replay_version=1,next_close=NEXT_CLOSE,quote_silence=f.QUOTE_SILENCE,windows=r.WINDOWS,exit_lead=r.EXIT_LEAD)
r.Gate=MarketGate

def events(data,day,rule,mode):
    seq=[(0,-2,'',dict(kind='configure',rule=rule))]; source={}
    for i,k in enumerate(SYMS):
        for b in data[k][day]:
            # Archive timestamps are start labels; price becomes observable at end.
            t=(b.ts.hour*60+b.ts.minute-550)*60+300
            assert any(a<t<=z for a,z in r.WINDOWS) and b.v==int(b.v)>0
            source[k,t]=float(b.c)
            if any(a<t<z for a,z in r.WINDOWS):
                seq.append((t,0,k,dict(kind='quote',symbol=k,price=float(b.c),stamp=t)))
            arrival=t+900+(i*18 if 'STAGGER' in mode else 0)
            # Do not fabricate same-session late bars: record only observations that arrive before close.
            window=next(w for w in r.WINDOWS if w[0]<t<=w[1])
            if arrival+1>=window[1]:continue
            for rep in (0,1):
                if 'MISSING' in mode and k==SYMS[-1] and t==18000:continue
                seq.append((arrival+rep,1,k,dict(kind='observe',symbol=k,end=t,price=float(b.c),volume=int(b.v))))
    for a,z in r.WINDOWS:
        for t in (a,z-r.EXIT_LEAD,z):seq.append((t,2,'',dict(kind='tick')))
    return [dict(now=t,**e) for t,_,_,e in sorted(seq,key=lambda x:x[:3])],source

def validate(g,source):
    for x in g.book.fills:
        if x['action']=='OPEN':
            match=[(rec,y) for rec,y in zip(g.diagnostics,g.evaluated,strict=True) if y[1]=='INTENT' and rec['received']<int(x['ts']) and 0<int(x['ts'])-rec['received']<=300 and any(k==x['symbol'] and side==x['side'] and qty==x['qty'] for k,side,qty in y[2])]
            assert match and int(x['ts'])==match[-1][0]['end']+1200
        assert x['raw']==source[x['symbol'],int(x['ts'])]
        assert any(a<int(x['ts'])<z for a,z in r.WINDOWS)
    for rec in g.diagnostics:
        assert 900<=rec['received']-rec['end']<=1020
        for k,v in rec['features'].items():
            assert v['price']==source[k,rec['end']]
            assert math.isclose(v['return_30m_pct'],100*(source[k,rec['end']]/source[k,rec['end']-1800]-1),abs_tol=1e-10)
    assert not g.book.legs and not g.pending,(g.fault,g.book.legs)
    ls.audit(g.book)

def run(data,day,rule,mode):
    global NEXT_CLOSE
    NEXT_CLOSE=mode.startswith('NEXT_')
    f.QUOTE_SILENCE=180 if 'STRICT' in mode else 360
    ev,source=events(data,day,rule,mode);g=MarketGate()
    for e in ev:g.apply(e)
    validate(g,source)
    if mode in ('BASE_360','STAGGER_360','NEXT_BASE_360','NEXT_STAGGER_360'):assert not g.fault,(day,rule,mode,g.fault)
    if 'MISSING' in mode:assert g.fault in ('SYNC_TIMEOUT','UPSTREAM_GAP'),(day,rule,g.fault)
    if not NEXT_CLOSE:assert not g.book.fills
    if rule=='NO_TRADE':assert not g.book.fills and g.book.cash==ls.CAP
    return g,ev

def write(path,rows):
    with path.open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=list(dict.fromkeys(k for row in rows for k in row)));w.writeheader();w.writerows(rows)

def main():
    data,dates=rel.load(Path(sys.argv[1]));out=Path(sys.argv[2]);out.mkdir(exist_ok=False)
    protected=[P/x for x in ('Trading_Prospective_Plan_01.json','Chappy_Trading_Lab_v1.1.0-rc1.py','Chappy_Trading_Research_Lab_v0.5.0.py','Chappy_Trading_Pipeline_Study_v0.2.py')];before={x.name:hashlib.sha256(x.read_bytes()).hexdigest() for x in protected}
    rows=[];fills=[];decisions=[];summary=[];journal=[]
    for mode in MODES:
        for rule in p.RULES:
            for day in dates:
                g,ev=run(data,day,rule,mode);c=Counter(x[1] for x in g.evaluated); opens=sum(x['action']=='OPEN' for x in g.book.fills)
                row=dict(mode=mode,rule=rule,day=day,inputs=len(ev),decisions=len(g.evaluated),complete=len(g.evaluated)-c['WARMUP'],intents=c['INTENT'],opens=opens,closes=sum(x['action']=='CLOSE' for x in g.book.fills),fault=g.fault or '',pnl=g.book.cash-ls.CAP,gross=sum(x['gross'] for x in g.book.fills),open_legs=len(g.book.legs),book_rejections=g.book.rejections)
                rows.append(row);fills.extend(dict(mode=mode,rule=rule,day=day,**x) for x in g.book.fills)
                decisions.extend(dict(mode=mode,rule=rule,day=day,end=x['end'],received=x['received'],status=y[1],orders=json.dumps(y[2]),features=json.dumps(x['features'])) for x,y in zip(g.diagnostics,g.evaluated,strict=True))
            group=rows[-len(dates):];summary.append(dict(mode=mode,rule=rule,days=len(group),pnl_sum=sum(x['pnl'] for x in group),positive_days=sum(x['pnl']>0 for x in group),negative_days=sum(x['pnl']<0 for x in group),opens=sum(x['opens'] for x in group),fault_days=sum(bool(x['fault']) for x in group),decisions=sum(x['decisions'] for x in group),intents=sum(x['intents'] for x in group),inputs=sum(x['inputs'] for x in group)))
        print(mode,'done',flush=True)
    # Full durable path on one real-price day with each mode; all other accounts in memory.
    with tempfile.TemporaryDirectory() as tmp:
        for mode in ('NEXT_BASE_360','NEXT_MISSING_360'):
            rule='PAIR';day=dates[0];g,ev=run(data,day,rule,mode);path=Path(tmp)/(mode+'.db');anchor=Path(tmp)/(mode+'.anchor');state=r.digest(g.state())
            with durable.Durable(path,anchor,create=True) as j:
                for e in ev:j.send(**e)
                assert r.digest(j.g.state())==state;head=j.j.head
            with durable.Durable(path,anchor) as j:
                assert r.digest(j.g.state())==state and j.j.head==head and j.j.seq==len(ev)
            journal.append(dict(mode=mode,day=day,rule=rule,inputs=len(ev),state=state,head=head,result='PASS'));print('durable',mode,flush=True)
    assert before=={x.name:hashlib.sha256(x.read_bytes()).hexdigest() for x in protected}
    for name,v in [('daily',rows),('summary',summary),('fills',fills),('decisions',decisions),('journal_audit',journal)]:write(out/(name+'.csv'),v)
    manifest=dict(mode='KNOWN_PRICE_HYPOTHETICAL_RECEIPT',days=dates,symbols=SYMS,source_sha=rel.ARCHIVE,source_bars=len(dates)*len(SYMS)*63,accounts=len(rows),inputs=sum(x['inputs'] for x in rows),fills=len(fills),decisions=len(decisions),durable_rows=sum(x['inputs'] for x in journal),protected_sha=before,notes='Independent day accounts; 5m close proxy only; synthetic 15m receipt, no actual quote timestamps, no live orders. Morning starts 09:10 archive; close cutoff 6min before end; no overnight exposure. Sparse quote baseline 360s; strict original 180s comparison. Four original pipeline rules; no new strategy optimization. NEXT variants allow an already-issued instruction to execute at next 5m close within 300 seconds and sync age <=1200, without relaxing new decision or missing-feed timeout. Not a live safety recommendation.')
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2));print(json.dumps(manifest,indent=2))
if __name__=='__main__':main()
