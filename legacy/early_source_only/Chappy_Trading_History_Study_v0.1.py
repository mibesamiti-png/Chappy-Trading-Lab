"""Known archive only, paper research. Usage: python script.py CTRL.zip NEW_OUT_DIR. Requires prior research modules."""
import csv,hashlib,importlib.util,json,math,sys
from pathlib import Path
from collections import Counter
P=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('histlat',P/'Chappy_Trading_Latency_Study_v0.1.py');lat=importlib.util.module_from_spec(s);sys.modules[s.name]=lat;s.loader.exec_module(lat)
m,r,f,ls=lat.m,lat.r,lat.f,lat.ls
MODES=('SESSION','DAY','PRIOR_DAYS','MIXED');RULES=('LONG_REBOUND','SHORT_REVERSAL');MODE='SESSION';SEED={};DAY='';CACHE={};CHECKS=0

def independent(xs):
    ds=[b-a for a,b in zip(xs,xs[1:])];g=sum(max(x,0) for x in ds[:14])/14;l=sum(max(-x,0) for x in ds[:14])/14
    for x in ds[14:]:g=(13*g+max(x,0))/14;l=(13*l+max(-x,0))/14
    return 50 if g==l==0 else 100 if l==0 else 100*g/(g+l)
class Gate(lat.Gate):
    def eligible(self):
        if lat.p.PipelineGate.__mro__[1].eligible(self):return True
        return bool(self.pending and self.session and self.clock<self.session[1]-r.EXIT_LEAD and not self.fault and self.sync is not None and len(self.last)==len(self.symbols) and set(self.last.values())=={self.sync} and self.clock-self.sync<=f.LAG+300 and self.clock-self.pending['created']<=300)
    def decide(self):
        global CHECKS
        end=self.sync;start=self.session[0];key=(DAY,f.LAG,MODE,end)
        local={k:[self.history[k,t][0] for t in range(start+300,end+1,300)] for k in self.symbols}
        day={k:[v[0] for (sym,t),v in self.history.items() if sym==k and t<=end] for k in self.symbols}
        history=local if MODE=='SESSION' else day if MODE in ('DAY','MIXED') else {k:SEED[k]+day[k] for k in self.symbols}
        short=local if MODE in ('SESSION','MIXED') else history
        rec=dict(end=end,received=self.clock,rule=self.rule,bars=len(local[self.symbols[0]]),rsi_bars=len(history[self.symbols[0]]),short_bars=len(short[self.symbols[0]]),features={},candidate=[]);self.diagnostics.append(rec)
        if min(map(len,history.values()))<16 or min(map(len,short.values()))<7:
            self.evaluated.append([end,'WARMUP',[]]);return
        if key not in CACHE:
            ret={k:100*(v[-1]/v[-7]-1) for k,v in short.items()};ft={}
            for k in self.symbols:
                prev=ls.port.r.core.rsi(history[k][:-1],14)[-1];assert math.isclose(prev,independent(history[k][:-1]),abs_tol=1e-9)
                peer=sum(v for sym,v in ret.items() if sym!=k)/5
                ft[k]=(prev,short[k][-1]/short[k][-2]-1,peer,ret[k]-peer,ret[k],sum(v>0 for sym,v in ret.items() if sym!=k));CHECKS+=1
            CACHE[key]=ft
        ft=CACHE[key];rec['features']=ft
        if self.rule in ('LONG_REBOUND','SHORT_REVERSAL'):chosen=ls.choose(ft,self.rule)
        else:
            candidates=[k for k,v in ft.items() if v[0]<30 and v[1]>0 and (self.rule=='REBOUND_ANY' or v[2]>0)]
            chosen=[(min(candidates,key=lambda k:(ft[k][0],k)),1,1)] if candidates else []
        rec['candidate']=chosen
        if self.book.legs or self.pending or not self.eligible():status='BUSY_OR_BLOCKED';orders=[]
        elif not chosen:status='NO_SIGNAL';orders=[]
        else:
            orders=ls.size(chosen,{k:v[-1] for k,v in short.items()},self.book.cash);status='INTENT' if len(orders)==len(chosen) else 'LOT_SKIP'
            if status=='INTENT':self.request(orders)
            else:orders=[]
        self.evaluated.append([end,status,orders])
    def state(self):return dict(super().state(),history_mode=MODE,prior_seed=SEED)
def main():
    global MODE,SEED,DAY
    data,dates=m.rel.load(Path(sys.argv[1]));out=Path(sys.argv[2]);out.mkdir(exist_ok=False)
    protected=[P/x for x in ('Trading_Prospective_Plan_01.json','Chappy_Trading_Lab_v1.1.0-rc1.py','Chappy_Trading_Research_Lab_v0.5.0.py','Chappy_Trading_Latency_Study_v0.1.py','Chappy_Trading_Pipeline_Study_v0.2.py')];before={x.name:hashlib.sha256(x.read_bytes()).hexdigest() for x in protected}
    baseline={(int(x['lag_min']),int(x['cost']),x['rule'],x['day']):x for x in csv.DictReader((P/'Trading_Round20_Latency/daily.csv').open(encoding='utf-8-sig'))}
    daily=[];fills=[];summary=[];signals=[];regress=0;fill_checks=0
    for MODE in (tuple(sys.argv[3:]) or MODES):
        for lag in (0,900):
            f.LAG=lag;f.QUOTE_SILENCE=360;m.NEXT_CLOSE=True
            for mult in (1,2):
                lat.MULT=mult
                for rule in RULES:
                    group=[]
                    for i,DAY in enumerate(dates):
                        SEED={k:[float(b.c) for d in dates[:i] for b in data[k][d]] if MODE=='PRIOR_DAYS' else [] for k in m.SYMS}
                        ev,source=lat.events(data,DAY,rule,lag);g=Gate()
                        for e in ev:g.apply(e)
                        assert not g.fault and not g.book.legs and not g.pending
                        ls.audit(g.book);c=Counter(x[1] for x in g.evaluated);opens=sum(x['action']=='OPEN' for x in g.book.fills)
                        for x in g.book.fills:
                            ts=int(x['ts']);assert x['raw']==source[x['symbol'],ts];fill_checks+=1
                            if x['action']=='OPEN':assert sum(ts==rec['end']+lag+300 and dec[1]=='INTENT' and [x['symbol'],x['side'],x['qty']] in [list(o) for o in dec[2]] for rec,dec in zip(g.diagnostics,g.evaluated,strict=True))==1
                        for rec,dec in zip(g.diagnostics,g.evaluated,strict=True):
                            assert rec['received']==rec['end']+lag+1
                            if mult==1 and (rec['candidate'] or (DAY=='2026-11-04' and rec['end']==14400)):
                                signals.append(dict(mode=MODE,lag_min=lag//60,rule=rule,day=DAY,end=rec['end'],received=rec['received'],local_bars=rec['bars'],rsi_bars=rec['rsi_bars'],short_bars=rec['short_bars'],status=dec[1],candidate=json.dumps(rec['candidate']),mitsubishi_rsi=rec['features'].get('8058.T',[None])[0]))
                        row=dict(mode=MODE,lag_min=lag//60,cost=mult,rule=rule,day=DAY,inputs=len(ev),decisions=len(g.evaluated),warmup=c['WARMUP'],signals=sum(bool(x['candidate']) for x in g.diagnostics),intents=c['INTENT'],opens=opens,pnl=g.book.cash-ls.CAP,gross=sum(x['gross'] for x in g.book.fills),dd=g.book.dd)
                        if MODE=='SESSION':
                            old=baseline[lag//60,mult,rule,DAY];assert abs(float(old['pnl'])-row['pnl'])<1e-6 and all(int(old[k])==row[k] for k in ('opens','decisions','signals','intents'));regress+=1
                        daily.append(row);group.append(row);fills.extend(dict(mode=MODE,lag_min=lag//60,cost=mult,rule=rule,day=DAY,**x) for x in g.book.fills)
                    pnl=sum(x['pnl'] for x in group);summary.append(dict(mode=MODE,lag_min=lag//60,cost=mult,rule=rule,pnl_sum=pnl,opens=sum(x['opens'] for x in group),signals=sum(x['signals'] for x in group),warmup=sum(x['warmup'] for x in group),positive_days=sum(x['pnl']>0 for x in group),without_nov4=pnl-next(x['pnl'] for x in group if x['day']=='2026-11-04'),worst_excluding_day=pnl-max(x['pnl'] for x in group)))
        print(MODE,'done',flush=True)
    assert before=={x.name:hashlib.sha256(x.read_bytes()).hexdigest() for x in protected}
    for name,rows in [('daily',daily),('fills',fills),('summary',summary),('signals',signals)]:m.write(out/(name+'.csv'),rows)
    report=dict(accounts=len(daily),inputs=sum(x['inputs'] for x in daily),fills=fill_checks,decisions=sum(x['decisions'] for x in daily),independent_rsi_checks=CHECKS,regression_accounts=regress,protected_sha=before,notes='Daily separate accounts. Prior days preloaded complete known dates strictly earlier; no missing date reconstruction. Intraday confirmed history only, late discarded bars not retroactively inserted. DAY/PRIOR_DAYS short returns can span gaps, MIXED requires 7 current-session bars. No true quotes or live trading.')
    (out/'manifest.json').write_text(json.dumps(report,indent=2));print(report)
if __name__=='__main__':main()
