"""Paper-only synthetic upstream-to-durable-book integration. No network.
Requires previous study modules alongside. Uses a separate journal schema semantics;
never open an existing Round13/14 journal with this pipeline. Run with NEW output dir.
"""
import csv, hashlib, importlib.util, json, math, sys, tempfile
from pathlib import Path
from types import SimpleNamespace
P=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('pipeline_durable',P/'Chappy_Trading_Durability_Study_v0.1.py');d=importlib.util.module_from_spec(spec);sys.modules[spec.name]=d;spec.loader.exec_module(d)
r=d.r; f=r.f; ls=r.ls
RULES=('NO_TRADE','PAIR','MOMENTUM_LONG','MOMENTUM_SHORT')
class PipelineGate(r.Gate):
    def __init__(self):
        super().__init__();self.rule=None;self.provisional={};self.evaluated=[]
    def state(self):
        return dict(super().state(),pipeline_version=1,rule=self.rule,provisional=sorted((k,t,*v) for (k,t),v in self.provisional.items()),evaluated=self.evaluated)
    def decide(self):
        end=self.sync;start=self.session[0]
        series={k:[SimpleNamespace(c=self.history[k,t][0]) for t in range(start+f.STEP,end+1,f.STEP)] for k in self.symbols}
        if len(next(iter(series.values())))<16:
            self.evaluated.append([end,'WARMUP',[]]);return
        # Generic peer count for synthetic three-symbol universe; old helper requires six.
        ret={k:100*(v[-1].c/v[-7].c-1) for k,v in series.items()};features={}
        for k,v in series.items():
            others=[x for a,x in ret.items() if a!=k];peer=sum(others)/len(others)
            prev=ls.port.r.core.rsi([b.c for b in v[:-1]],14)[-1]
            features[k]=(prev,v[-1].c/v[-2].c-1,peer,ret[k]-peer,ret[k],sum(x>0 for x in others))
        if self.rule in ('PAIR','NO_TRADE'):chosen=ls.choose(features,self.rule)
        elif self.rule=='MOMENTUM_LONG':
            k=min(features,key=lambda k:(-features[k][4],k));chosen=[(k,1,1)] if features[k][4]>.3 else []
        else:
            k=min(features,key=lambda k:(features[k][4],k));chosen=[(k,-1,1)] if features[k][4]<-.3 else []
        if self.book.legs or self.pending or not self.eligible():
            self.evaluated.append([end,'BUSY_OR_BLOCKED',[]]);return
        px={k:v[-1].c for k,v in series.items()};orders=ls.size(chosen,px,self.book.cash)
        if not chosen:self.evaluated.append([end,'NO_SIGNAL',[]]);return
        if len(orders)!=len(chosen):self.evaluated.append([end,'LOT_SKIP',[]]);return
        self.evaluated.append([end,'INTENT',orders]);self.request(orders)
    def apply(self,e):
        kind=e['kind']; now=e['now']
        if kind=='configure':
            if self.clock!=-1 or self.rule is not None or now!=0 or e['rule'] not in RULES:raise ValueError('bad configuration')
            self.advance(now);self.rule=e['rule'];return
        if self.rule is None:raise ValueError('configuration required')
        if kind in ('bar','request'):raise ValueError('upstream bypass forbidden')
        if kind!='observe':
            previous=self.session;super().apply(e)
            if previous!=self.session:self.provisional.clear()
            if kind=='recover':self.provisional.clear()
            return
        previous=self.session;self.advance(now)
        if previous!=self.session:self.provisional.clear()
        k,end,px,vol=e['symbol'],e['end'],e['price'],e['volume']
        if k not in self.symbols or type(end)!=int or end%f.STEP or type(px) not in (int,float) or not math.isfinite(px) or px<=0 or type(vol)!=int or vol<0:
            self.halt('INVALID_OBSERVATION');return
        key=k,end;value=(px,vol)
        if key in self.history:
            if self.history[key]!=value:self.halt('CONFIRMED_CORRECTION')
            else:self.log('DUPLICATE_OBSERVATION',symbol=k,stamp=end)
            return
        if self.fault or not self.session or not self.session[0]<end<=self.session[1] or end>now or now-end<f.LAG:
            self.log('UNCONFIRMED',symbol=k,stamp=end);return
        if vol==0:
            self.provisional.pop(key,None);self.log('UNCONFIRMED_ZERO_VOLUME',symbol=k,stamp=end);return
        if end!=self.last.get(k,self.session[0])+f.STEP:
            self.halt('UPSTREAM_GAP');return
        old=self.provisional.get(key)
        if old is None or old[:2]!=value:
            self.provisional[key]=(*value,now);self.log('PROVISIONAL',symbol=k,stamp=end);return
        if now<=old[2]:self.log('SAME_RECEIPT',symbol=k,stamp=end);return
        del self.provisional[key];n=self.decisions;self.bar(k,end,px,vol)
        if self.decisions>n:self.decide()
# The imported r module is private to this script; replay uses this same Gate class.
r.Gate=PipelineGate

def observe(j,k,end,now,price=1000,volume=100):j.send('observe',now,symbol=k,end=end,price=price,volume=volume)
def q(j,k,t,price=1000,stamp=None):j.send('quote',t,symbol=k,price=price,stamp=t if stamp is None else stamp)
def market_price(k,i):return 1000+({'A':4,'B':-4,'C':0}[k])*i

def stream(j,until=7199,omit=None,change=None,reverse=False):
    events=[]
    for i in range(1,21):
        end=i*300;arrival=end+900
        for k in j.g.symbols:
            for rep in (0,1):
                if omit==(k,i,rep):continue
                price=market_price(k,i)
                if change==(k,i,rep):price+=1
                events.append((arrival+rep,0,k,dict(kind='observe',symbol=k,end=end,price=price,volume=100)))
    for t in range(1202,7200,60):
        for k in j.g.symbols:events.append((t,1,k,dict(kind='quote',symbol=k,price=market_price(k,max(1,t//300)),stamp=t)))
    events.extend((t,2,'',dict(kind='tick')) for t in (7140,7199))
    for t,priority,k,e in sorted(events,key=lambda x:(x[0],x[1],(-ord(x[2]) if reverse else ord(x[2])) if x[2] else 0)):
        if j.g.clock<t<=until or j.g.clock==t and t<=until:j.send(now=t,**e)

def tests(out):
    rows=[];views=[];decisions=[];fills=[];events=[]
    with tempfile.TemporaryDirectory() as td:
        root=Path(td)
        def run(name,rule,fn):
            db=root/(name+'.db');a=root/(name+'.anchor.db')
            with d.Durable(db,a,create=True) as j:
                j.send('configure',0,rule=rule);fn(j);before=r.digest(j.g.state());seq=j.j.seq;head=j.j.head
                if not j.g.book.legs:ls.audit(j.g.book)
                rows.append(dict(case=name,rule=rule,result='PASS',inputs=seq,decisions=j.g.decisions,intents=sum(x[1]=='INTENT' for x in j.g.evaluated),fills=len(j.g.book.fills),open_legs=len(j.g.book.legs),fault=j.g.fault or '',cash=j.g.book.cash))
                decisions.extend(dict(case=name,end=x[0],status=x[1],orders=json.dumps(x[2])) for x in j.g.evaluated)
                fills.extend(dict(case=name,**x) for x in j.g.book.fills);events.extend(dict(case=name,**x) for x in j.g.events);views.append(dict(case=name,**d.status(j.g,j.g.clock)))
            with d.Durable(db,a) as j:assert r.digest(j.g.state())==before and j.j.seq==seq and j.j.head==head
            return rows[-1]
        def healthy(j,rule,reverse=False):
            stream(j,reverse=reverse);assert not j.g.fault and not j.g.book.legs and not j.g.pending
            opens=[x for x in j.g.book.fills if x['action']=='OPEN'];closes=[x for x in j.g.book.fills if x['action']=='CLOSE'];n=0 if rule=='NO_TRADE' else 2 if rule=='PAIR' else 1
            assert len(opens)==len(closes)==n and j.g.decisions==20
            if n:
                assert all(int(x['ts'])>5701 for x in opens) and all(x['reason']=='SESSION_CUTOFF' for x in closes)
                assert {x['side'] for x in opens}==({-1,1} if n==2 else {1} if rule=='MOMENTUM_LONG' else {-1})
        for rule in RULES:run(rule.lower(),rule,lambda j,rule=rule:healthy(j,rule))
        a=run('reverse_arrival_order','PAIR',lambda j:healthy(j,'PAIR',True));assert math.isclose(a['cash'],rows[1]['cash'],abs_tol=1e-7)
        def provisional(j):
            observe(j,'A',300,1199);assert not j.g.provisional
            observe(j,'A',300,1200,1000,0);assert not j.g.provisional
            observe(j,'A',300,1201);observe(j,'A',300,1201);assert not j.g.history
            observe(j,'A',300,1202,1001);assert not j.g.history
            observe(j,'A',300,1203,1001,0);assert not j.g.provisional
            observe(j,'A',300,1204,1001);assert not j.g.history
            observe(j,'A',300,1205,1001);assert j.g.history['A',300]==(1001,100) and j.g.decisions==0
            observe(j,'B',300,1205);observe(j,'C',300,1205);observe(j,'B',300,1206);assert j.g.decisions==0
            observe(j,'C',300,1206);assert j.g.decisions==1
            observe(j,'C',300,1207);assert j.g.decisions==1
        run('confirmation_revisions_duplicates','PAIR',provisional)
        def correction(j):
            stream(j,until=5702);assert len(j.g.book.legs)==2
            observe(j,'A',4800,5703,999);assert j.g.fault=='CONFIRMED_CORRECTION' and j.g.exit
            q(j,'A',5704);q(j,'B',5705);assert not j.g.book.legs
        run('confirmed_correction_with_exposure','PAIR',correction)
        def missing(j):
            stream(j,until=5821,omit=('C',16,1));j.send('tick',5821);assert j.g.fault=='SYNC_TIMEOUT' and not j.g.book.fills
        run('missing_confirmation','PAIR',missing)
        def gap(j):
            observe(j,'A',600,1500);assert j.g.fault # initial bar not received by deadline
        run('gap_or_timeout','PAIR',gap)
        def late(j):
            stream(j,until=5701);assert j.g.pending and not j.g.book.legs
            q(j,'A',5702,1000,5700);q(j,'B',5702,1000,5700);assert not j.g.book.legs
            q(j,'A',5703);q(j,'B',5704);assert len(j.g.book.legs)==2
            j.send('recover',5705);q(j,'A',5706);q(j,'B',5707);assert not j.g.book.legs
        run('pre_intent_quotes_not_used','PAIR',late)
        def restart(j):
            observe(j,'A',300,1200);assert j.g.provisional
            j.send('recover',1201);assert not j.g.provisional and j.g.fault=='RESTART_REVIEW';observe(j,'A',300,1202);assert not j.g.history
        run('recovery_discards_provisional','PAIR',restart)
        def bad(j):
            observe(j,'A',300,1200,-1);assert j.g.fault=='INVALID_OBSERVATION' and not j.g.book.fills
        run('invalid_observation','PAIR',bad)
        def bypass(j):
            try:j.send('bar',1200,symbol='A',end=300,price=1000)
            except ValueError:pass
            else:raise AssertionError('bypass accepted')
            assert j.failed and j.j.seq==1 and not j.g.history
        run('raw_bar_bypass_rejected','PAIR',bypass)
        def pending_skew(j):
            stream(j,until=5701);assert j.g.pending
            # First next bar only becomes eligible at 6000, while pending expires at 6001.
            observe(j,'A',5100,6000,1068);observe(j,'A',5100,6001,1068);assert not j.g.pending and not j.g.book.fills
            q(j,'A',6002);q(j,'B',6002);assert not j.g.book.fills
        run('new_bar_cancels_pending','PAIR',pending_skew)
        for mode in ('pending','partial_exit','unresolved'):
            name='reopen_'+mode;db=root/(name+'.db');a=root/(name+'.anchor.db')
            with d.Durable(db,a,create=True) as j:
                j.send('configure',0,rule='PAIR');stream(j,until=5701 if mode=='pending' else 5702)
                if mode=='pending':assert j.g.pending and not j.g.book.legs
                else:
                    assert len(j.g.book.legs)==2
                    j.send('recover',5703);q(j,'A',5704);assert len(j.g.book.legs)==1
                before=r.digest(j.g.state());n=len(j.g.book.fills)
            with d.Durable(db,a) as j:
                assert r.digest(j.g.state())==before
                try:j.send('tick',5705)
                except ValueError:pass
                else:raise AssertionError('restart bypass')
                j.send('recover',5705);assert j.g.pending is None
                q(j,'A',5706);q(j,'B',5706,stamp=5705);assert len(j.g.book.fills)==n
                if mode=='partial_exit':q(j,'B',5707);assert len(j.g.book.fills)==n+1
                if mode=='unresolved':
                    assert len(j.g.book.legs)==1 and d.status(j.g,5706)['equity'] is None
                else:assert not j.g.book.legs;ls.audit(j.g.book)
                before=r.digest(j.g.state());seq=j.j.seq;head=j.j.head
                rows.append(dict(case=name,rule='PAIR',result='PASS',inputs=seq,decisions=j.g.decisions,intents=sum(x[1]=='INTENT' for x in j.g.evaluated),fills=len(j.g.book.fills),open_legs=len(j.g.book.legs),fault=j.g.fault or '',cash=j.g.book.cash))
                decisions.extend(dict(case=name,end=x[0],status=x[1],orders=json.dumps(x[2])) for x in j.g.evaluated)
                fills.extend(dict(case=name,**x) for x in j.g.book.fills);events.extend(dict(case=name,**x) for x in j.g.events);views.append(dict(case=name,**d.status(j.g,j.g.clock)))
            with d.Durable(db,a) as j:assert r.digest(j.g.state())==before and j.j.seq==seq and j.j.head==head
    out.mkdir(exist_ok=False)
    for name,data in [('scenarios.csv',rows),('decisions.csv',decisions),('fills.csv',fills),('events.csv',events)]:
        with (out/name).open('x',encoding='utf-8-sig',newline='') as h:
            w=csv.DictWriter(h,fieldnames=list(dict.fromkeys(k for row in data for k in row)));w.writeheader();w.writerows(data)
    (out/'views.json').write_text(json.dumps(views,indent=2),encoding='utf-8')
    print(json.dumps(dict(scenarios=len(rows),inputs=sum(x['inputs'] for x in rows),decisions=len(decisions),fills=len(fills),events=len(events),replayed=len(rows)),indent=2))
if __name__=='__main__':tests(Path(sys.argv[1]))
