"""Paper-only known archive. Compare artificial data delay, costs, and matched signals.
python Chappy_Trading_Latency_Study_v0.1.py CTRL.zip NEW_OUT_DIR
Requires previous research modules. No network or live execution.
"""
import importlib.util,sys,math,json,hashlib,statistics
from pathlib import Path
from collections import defaultdict,Counter
P=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('lat_market',P/'Chappy_Trading_Market_Replay_v0.1.py');m=importlib.util.module_from_spec(s);sys.modules[s.name]=m;s.loader.exec_module(m)
p,r,f,ls=m.p,m.r,m.f,m.ls
RULES=('NO_TRADE','MOMENTUM_LONG','REBOUND_ANY','REBOUND_PEER','LONG_REBOUND','SHORT_REVERSAL')
LAGS=(0,300,600,900,1200); MULT=1
p.RULES=RULES
class Gate(m.MarketGate):
    def __init__(self):
        super().__init__();self.book=ls.Book(MULT)
    def eligible(self):
        if r.Gate is Gate and p.PipelineGate.__mro__[1].eligible(self):return True
        return bool(self.pending and self.session and self.clock<self.session[1]-r.EXIT_LEAD and not self.fault and self.sync is not None and len(self.last)==len(self.symbols) and set(self.last.values())=={self.sync} and self.clock-self.sync<=f.LAG+300 and self.clock-self.pending['created']<=300)
    def decide(self):
        if self.rule in ('NO_TRADE','MOMENTUM_LONG'):return super().decide()
        # Reuse the existing diagnostic calculation without issuing a momentum or pair order.
        original=self.rule;self.rule='NO_TRADE'
        try:super().decide()
        finally:self.rule=original
        rec=self.diagnostics[-1];rec['rule']=original
        fs=rec['features'];end=rec['end']
        if not fs:return
        ft={k:(v['previous_rsi'],v['last_return_pct']/100,v['peer_return_pct'],v['relative_pp'],v['return_30m_pct'],v['peer_up']) for k,v in fs.items()}
        if original in ('LONG_REBOUND','SHORT_REVERSAL'):chosen=ls.choose(ft,original)
        else:
            candidates=[k for k,v in ft.items() if v[0]<30 and v[1]>0 and (original=='REBOUND_ANY' or v[2]>0)]
            chosen=[(min(candidates,key=lambda k:(ft[k][0],k)),1,1)] if candidates else []
        rec['candidate']=chosen;rec['score']=ft[chosen[0][0]][0] if chosen else None;rec['threshold']=70 if original=='SHORT_REVERSAL' else 30
        if self.book.legs or self.pending or not self.eligible():return
        if not chosen:return
        orders=ls.size(chosen,{k:v['price'] for k,v in fs.items()},self.book.cash)
        if len(orders)!=len(chosen):self.evaluated[-1]=[end,'LOT_SKIP',[]];return
        self.evaluated[-1]=[end,'INTENT',orders];self.request(orders)
    def state(self):return dict(super().state(),latency_seconds=f.LAG,cost_multiplier=MULT)
r.Gate=Gate

def events(data,day,rule,lag):
    # Round19 source mapping/quotes, but explicit observation clock offset.
    base,source=m.events(data,day,rule,'NEXT_BASE_360');seq=[]
    for e in base:
        if e['kind']!='observe':seq.append(e)
    for k in m.SYMS:
        for b in data[k][day]:
            t=(b.ts.hour*60+b.ts.minute-550)*60+300;z=next(z for a,z in r.WINDOWS if a<t<=z)
            if t+lag+1>=z:continue
            for rep in (0,1):seq.append(dict(now=t+lag+rep,kind='observe',symbol=k,end=t,price=float(b.c),volume=int(b.v)))
    priority={'configure':-2,'quote':0,'observe':1,'tick':2}
    return sorted(seq,key=lambda e:(e['now'],priority[e['kind']],e.get('symbol',''))),source

def run(data,day,rule,lag,mult):
    global MULT
    MULT=mult;f.LAG=lag;f.QUOTE_SILENCE=360;m.NEXT_CLOSE=True
    ev,source=events(data,day,rule,lag);g=Gate()
    for e in ev:g.apply(e)
    assert not g.fault and not g.book.legs and not g.pending,(day,rule,lag,g.fault)
    ls.audit(g.book)
    for rec in g.diagnostics:
        assert rec['received']==rec['end']+lag+1
        for k,v in rec['features'].items():
            assert v['price']==source[k,rec['end']]
            assert math.isclose(v['return_30m_pct'],100*(source[k,rec['end']]/source[k,rec['end']-1800]-1),abs_tol=1e-10)
    for x in g.book.fills:
        ts=int(x['ts']);assert x['raw']==source[x['symbol'],ts]
        if x['action']=='OPEN':
            recs=[rec for rec,decision in zip(g.diagnostics,g.evaluated,strict=True) if decision[1]=='INTENT' and ts==rec['end']+lag+300 and [x['symbol'],x['side'],x['qty']] in [list(o) for o in decision[2]]]
            assert len(recs)==1
    return g,ev,source

def main():
    data,dates=m.rel.load(Path(sys.argv[1]));out=Path(sys.argv[2]);out.mkdir(exist_ok=False)
    protected=[P/x for x in ('Trading_Prospective_Plan_01.json','Chappy_Trading_Lab_v1.1.0-rc1.py','Chappy_Trading_Research_Lab_v0.5.0.py','Chappy_Trading_Market_Replay_v0.1.py','Chappy_Trading_Pipeline_Study_v0.2.py')];before={x.name:hashlib.sha256(x.read_bytes()).hexdigest() for x in protected}
    daily=[];fills=[];summary=[];matched=[];checks=0; signals={};baseline={(x['rule'],x['day']):x for x in __import__('csv').DictReader((P/'Trading_Round19_Market_Replay_complete/daily.csv').open(encoding='utf-8-sig')) if x['mode']=='NEXT_BASE_360'}; regress=0
    for lag in LAGS:
        for mult in (1,2):
            for rule in RULES:
                group=[]
                for day in dates:
                    g,ev,source=run(data,day,rule,lag,mult);c=Counter(x[1] for x in g.evaluated);opens=sum(x['action']=='OPEN' for x in g.book.fills)
                    row=dict(lag_min=lag//60,cost=mult,rule=rule,day=day,inputs=len(ev),decisions=len(g.evaluated),signals=sum(bool(x['candidate']) for x in g.diagnostics),intents=c['INTENT'],opens=opens,pnl=g.book.cash-ls.CAP,gross=sum(x['gross'] for x in g.book.fills),dd=g.book.dd,book_rejections=g.book.rejections)
                    daily.append(row);group.append(row);fills.extend(dict(lag_min=lag//60,cost=mult,rule=rule,day=day,**x) for x in g.book.fills)
                    if lag==900 and mult==1 and (rule,day) in baseline:
                        old=baseline[rule,day];assert abs(row['pnl']-float(old['pnl']))<1e-6 and row['opens']==int(old['opens']) and row['decisions']==int(old['decisions']);regress+=1
                    # Matched cohort: all five delays can enter and hold 30min before cutoff; no account constraints.
                    if rule in ('REBOUND_ANY','REBOUND_PEER','LONG_REBOUND','SHORT_REVERSAL') and mult==1:
                        for rec in g.diagnostics:
                            end=rec['end'];window=next((w for w in r.WINDOWS if w[0]<end<=w[1]),None)
                            if not rec['features'] or end+max(LAGS)+300+1800>=window[1]-r.EXIT_LEAD:continue
                            key=(rule,day,end);choice=rec['candidate']
                            if lag==0:signals[key]=choice
                            else:assert signals[key]==choice;checks+=1
                            for k,side,w in choice:
                                entry=end+lag+300;exit=entry+1800;buy=source[k,entry];sell=source[k,exit]
                                for cst in (1,2):
                                    rate=.0005*cst;borrow=.0001*cst if side==-1 else 0
                                    net=(side*(sell*(1-side*rate)-buy*(1+side*rate))-rate*(sell*(1-side*rate)+buy*(1+side*rate))-buy*borrow)/buy*100
                                    matched.append(dict(rule=rule,day=day,end=end,lag_min=lag//60,cost=cst,symbol=k,side=side,entry=entry,exit=exit,gross_pct=side*(sell/buy-1)*100,net_pct=net))
                summary.append(dict(lag_min=lag//60,cost=mult,rule=rule,days=len(group),pnl_sum=sum(x['pnl'] for x in group),gross_sum=sum(x['gross'] for x in group),opens=sum(x['opens'] for x in group),signals=sum(x['signals'] for x in group),positive_days=sum(x['pnl']>0 for x in group),worst_excluding_day=min(sum(x['pnl'] for x in group if x['day']!=d) for d in dates)))
        print('lag',lag,'done',flush=True)
    groups=defaultdict(list)
    for x in matched:groups[x['rule'],x['lag_min'],x['cost']].append(x)
    matchsummary=[dict(rule=k[0],lag_min=k[1],cost=k[2],n=len(v),days=len({x['day'] for x in v}),mean_net_pct=statistics.mean(x['net_pct'] for x in v),mean_gross_pct=statistics.mean(x['gross_pct'] for x in v)) for k,v in sorted(groups.items())]
    assert before=={x.name:hashlib.sha256(x.read_bytes()).hexdigest() for x in protected}
    for name,rows in [('daily',daily),('summary',summary),('fills',fills),('matched_signals',matched),('matched_summary',matchsummary)]:m.write(out/(name+'.csv'),rows)
    manifest=dict(accounts=len(daily),inputs=sum(x['inputs'] for x in daily),fills=len(fills),decisions=sum(x['decisions'] for x in daily),matched_candidate_checks=checks,matched_rows=len(matched),regression_accounts=regress,protected_sha=before,notes='Known 19 days only. Daily independent accounts, 60m max holding or earlier session cutoff; matched signal cohort 30m hold, no capital constraints, same eligible decision timestamps all lag conditions. Artificial delays and close proxy, not live quote or return validation.')
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2));print(manifest)
if __name__=='__main__':main()
