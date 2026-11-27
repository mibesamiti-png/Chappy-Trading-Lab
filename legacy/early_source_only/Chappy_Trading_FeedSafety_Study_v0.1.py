# -*- coding: utf-8 -*-
"""Synthetic multi-symbol feed safety study, no live network, broker or real orders.
Run: python Chappy_Trading_FeedSafety_Study_v0.1.py OUTPUT_DIR
Times are seconds on an artificial market clock; stamp = bar END. Confirmed feed
is a separate input from hypothetical execution quotes. Upstream confirmation
(two observations, volume, etc.) is NOT implemented here. A gap or correction
latches a fault until operator review. No stale-price exit or retroactive fill.
"""
import argparse,csv,json,math,hashlib,importlib.util,sys
from pathlib import Path
from dataclasses import dataclass
P=Path(__file__).with_name('Chappy_Trading_LongShort_Study_v0.1.py')
spec=importlib.util.spec_from_file_location('feedsafety_ls',P);ls=importlib.util.module_from_spec(spec);sys.modules[spec.name]=ls;spec.loader.exec_module(ls)
STEP=300; LAG=900; GRACE=120; QUOTE_MAX=5; QUOTE_SILENCE=180
@dataclass(frozen=True)
class Bar:
    end:int
    price:float
    volume:int=100
class Gate:
    def __init__(self,symbols=('A','B','C'),first_end=300,session_end=3600):
        self.symbols=tuple(symbols);self.first=first_end;self.end=session_end;self.next=first_end
        self.last={k:None for k in symbols};self.history={k:{} for k in symbols};self.clock=-1
        self.book=ls.Book();self.pending=None;self.exit_requested=None;self.fault=None;self.closed=False;self.last_sync=None;self.last_quote={};self.events=[];self.decision_count=0
    def log(self,kind,**kw):self.events.append(dict(now=self.clock,kind=kind,**kw))
    def stop(self,why):
        if self.fault is None:self.fault=why;self.log('HALT',reason=why)
        if self.pending is not None:self.log('CANCEL',reason=why);self.pending=None
        if self.book.legs and self.exit_requested is None:self.exit_requested=self.clock;self.log('EXIT_REQUEST',reason=why)
    def advance(self,now):
        if not isinstance(now,int) or now<self.clock:raise ValueError('nonmonotonic clock')
        self.clock=now
        if now>=self.end:
            if not self.closed:self.closed=True;self.stop('SESSION_END')
        elif not self.fault and now>self.next+LAG+GRACE:self.stop('SYNC_TIMEOUT')
        if not self.fault and self.book.legs and any(now-self.last_quote.get(k,-10**9)>QUOTE_SILENCE for k,s in self.book.legs):self.stop('EXECUTION_FEED_TIMEOUT')
        if self.pending and now-self.pending[3]>STEP:self.log('CANCEL',reason='ORDER_EXPIRED');self.pending=None
    def ingest(self,k,bar,now):
        self.advance(now)
        if k not in self.history:raise ValueError('unknown symbol')
        if not isinstance(bar.end,int) or bar.end<self.first or bar.end>self.end or (bar.end-self.first)%STEP or bar.end>now or not math.isfinite(bar.price) or bar.price<=0 or bar.volume<=0:
            self.stop('INVALID_BAR');return
        h=self.history[k]
        if bar.end in h:
            if h[bar.end]!=bar:self.stop('CONFIRMED_CORRECTION')
            else:self.log('DUPLICATE',symbol=k,stamp=bar.end)
            return
        expected=self.first if self.last[k] is None else self.last[k]+STEP
        if bar.end!=expected:self.stop('GAP_OR_REORDER');return
        h[bar.end]=bar;self.last[k]=bar.end;self.log('RECEIVE',symbol=k,stamp=bar.end)
        if self.fault:return
        # All symbols must have the same latest confirmed stamp. Never select an
        # older common prefix when any symbol already has a newer bar.
        if len(set(self.last.values()))!=1:
            if self.pending:self.log('CANCEL',reason='UNSYNC');self.pending=None
            return
        stamp=self.last[k]
        if stamp!=self.next:self.stop('MISSED_SYNC');return
        if now-stamp>LAG+GRACE:self.stop('STALE_SNAPSHOT');return
        self.last_sync=stamp;self.next=stamp+STEP;self.decision_count+=1
        self.log('SYNC',stamp=stamp)
    def request(self,k,side,qty,now):
        self.advance(now)
        if self.fault or self.closed or self.pending or self.book.legs or self.last_sync is None or len(set(self.last.values()))!=1 or next(iter(self.last.values()))!=self.last_sync or now-self.last_sync>LAG+GRACE:
            self.log('REJECT_INTENT');return False
        if k not in self.symbols or side not in (-1,1) or qty<=0 or qty%ls.LOT:raise ValueError('invalid order')
        self.pending=(k,side,qty,now);self.log('INTENT',symbol=k,side=side,qty=qty,stamp=self.last_sync);return True
    def quote(self,k,price,stamp,now):
        self.advance(now)
        if k not in self.symbols or not isinstance(stamp,int) or stamp>now or now-stamp>QUOTE_MAX or not math.isfinite(price) or price<=0:
            self.log('REJECT_QUOTE',symbol=k,stamp=stamp);return
        if k in self.last_quote and stamp<=self.last_quote[k]:
            self.log('REJECT_QUOTE_REPLAY',symbol=k,stamp=stamp);return
        self.last_quote[k]=stamp
        # Independently assumed execution quote. Never use delayed signal price.
        if self.exit_requested is not None and stamp>self.exit_requested:
            for key,leg in list(self.book.legs.items()):
                if leg.symbol==k:self.book.close(key,leg.qty,{k:price},str(now),'SAFETY_EXIT');self.log('EXIT_FILL',symbol=k,stamp=stamp,price=price)
            if not self.book.legs:self.exit_requested=None
        if self.book.legs:
            # Only a single position is supported; mark only with its own fresh quote.
            key=next(iter(self.book.legs))
            if key[0]==k:
                self.book.mark({k:price})
                if self.book.margin_breach({k:price}):self.book.margin_calls+=1 if self.fault is None else 0;self.stop('MARGIN')
        if self.pending:
            sym,side,qty,created=self.pending
            if sym==k and stamp>created:
                self.pending=None
                if self.fault or len(set(self.last.values()))!=1 or next(iter(self.last.values()))!=self.last_sync or now-self.last_sync>LAG+GRACE:
                    self.log('CANCEL',reason='UNSYNC_AT_EXECUTION');return
                if self.book.enter([(k,side,qty)],{k:price},str(now),'ENTRY'):
                    self.log('ENTRY_FILL',symbol=k,stamp=stamp,price=price)
                else:self.log('REJECT_BOOK')
    def status(self):return 'UNRESOLVED_EXPOSURE' if self.book.legs else ('HALTED_FLAT' if self.fault else 'FLAT')

def selftest():
    rows=[];events=[]
    def run(name,fn):
        g=Gate();fn(g)
        if not g.book.legs:ls.audit(g.book)
        rows.append(dict(case=name,result='PASS',fault=g.fault or '',syncs=g.decision_count,entries=sum(x['action']=='OPEN' for x in g.book.fills),exits=sum(x['action']=='CLOSE' for x in g.book.fills),status=g.status(),cash=g.book.cash,open_legs=len(g.book.legs)))
        events.extend(dict(case=name,**x) for x in g.events)
    def sync(g,end=300,t=1200):
        for i,k in enumerate(g.symbols):g.ingest(k,Bar(end,1000+i),t+i*10)
    def enter(g,side=1):
        sync(g);assert g.request('A',side,400,1220);g.quote('A',1010,1221,1221);assert len(g.book.legs)==1
    def normal(g):
        sync(g);assert g.decision_count==1 and g.request('A',1,400,1220)
        g.quote('A',999,1220,1220);assert not g.book.legs
        g.quote('A',1010,1221,1221);assert g.book.legs and g.book.fills[0]['raw']==1010
        g.advance(1621);assert g.fault=='SYNC_TIMEOUT';g.quote('A',1030,1622,1622);assert not g.book.legs
    def skew(g):
        g.ingest('A',Bar(300,1000),1200);g.ingest('B',Bar(300,1001),1210);assert not g.request('A',1,400,1210);g.ingest('C',Bar(300,1002),1319);assert g.decision_count==1 and not g.fault
    def missing(g):
        g.ingest('A',Bar(300,1000),1200);g.ingest('B',Bar(300,1001),1210);g.advance(1321);g.ingest('C',Bar(300,1002),1322);assert g.fault=='SYNC_TIMEOUT' and g.decision_count==0 and not g.request('A',1,400,1322)
    def dup(g):
        sync(g);g.ingest('A',Bar(300,1000),1221);assert g.decision_count==1 and not g.fault
    def correct(g):
        sync(g);assert g.request('A',1,400,1220);g.ingest('A',Bar(300,999),1221);assert g.fault=='CONFIRMED_CORRECTION' and g.pending is None;g.quote('A',1000,1222,1222);assert not g.book.legs
    def gap(g):
        sync(g);g.ingest('A',Bar(900,1000),1800);assert g.fault is not None and not g.request('A',1,400,1800)
    def gap_fast(g):
        sync(g);g.ingest('A',Bar(900,1000),1221);assert g.fault=='GAP_OR_REORDER'
    def mixed(g):
        sync(g);g.ingest('A',Bar(600,1001),1500);assert not g.request('A',1,400,1500);g.ingest('B',Bar(600,1002),1510);g.ingest('C',Bar(600,1003),1520);assert g.decision_count==2 and g.request('A',1,400,1520)
    def pending_timeout(g):
        sync(g);assert g.request('A',1,400,1220);g.advance(1621);g.quote('A',1000,1622,1622);assert g.pending is None and not g.book.legs
    def stale_exit(g):
        enter(g);g.advance(1621);g.quote('A',1100,1600,1622);g.quote('B',1100,1622,1622);assert g.status()=='UNRESOLVED_EXPOSURE';g.quote('A',900,1623,1623);assert g.status()=='HALTED_FLAT' and g.book.fills[-1]['raw']==900
    def unresolved(g):
        enter(g);g.advance(1621);g.advance(3600);assert g.status()=='UNRESOLVED_EXPOSURE'
    def margin(g):
        enter(g,-1);g.quote('A',4000,1222,1222);assert g.fault=='MARGIN' and g.book.legs;g.quote('A',4000,1223,1223);assert not g.book.legs and g.book.cash<0
    def bad(g):
        g.ingest('A',Bar(300,float('nan')),1200);assert g.fault=='INVALID_BAR'
    def session(g):
        # Near session end with custom earlier end: no stale close, explicit fresh quote after cutoff.
        g.end=1250;enter(g);g.advance(1250);assert g.fault=='SESSION_END';g.quote('A',1010,1251,1251);assert not g.book.legs
    def expired(g):
        sync(g);assert g.request('A',1,400,1220);g.quote('A',1010,1521,1521);assert g.pending is None and not g.book.legs
    def quote_replay(g):
        enter(g,-1);g.quote('A',1020,1225,1225);g.quote('A',4000,1224,1226);assert g.fault is None and g.book.legs
        g.quote('A',4000,1225,1226);assert g.fault is None
        g.advance(1621);g.quote('A',1020,1622,1622);assert not g.book.legs
    def expiry_without_quotes(g):
        sync(g);assert g.request('A',1,400,1220);g.advance(1521);assert g.pending is None and not g.book.legs
    def recovered_skew_pending(g):
        sync(g);assert g.request('A',1,400,1220);g.ingest('A',Bar(600,1000),1500);g.ingest('B',Bar(600,1001),1501);g.ingest('C',Bar(600,1002),1502);g.quote('A',1000,1503,1503);assert not g.book.legs and g.pending is None and not g.fault
    def execution_silence(g):
        enter(g);g.advance(1402);assert g.fault=='EXECUTION_FEED_TIMEOUT' and g.status()=='UNRESOLVED_EXPOSURE';g.quote('A',990,1403,1403);assert g.status()=='HALTED_FLAT'
    def reordered_clock(g):
        g.advance(1200)
        try:g.advance(1199)
        except ValueError:pass
        else:raise AssertionError('clock moved backwards')
    def fill_skew(g):
        sync(g);assert g.request('A',1,400,1220);g.ingest('A',Bar(600,1000),1500);g.quote('A',1010,1501,1501);assert not g.book.legs and g.pending is None
    for name,fn in [('normal_and_no_retro_fill',normal),('recoverable_skew',skew),('missing_symbol',missing),('duplicate',dup),('correction_cancels',correct),('late_gap',gap),('gap_before_timeout',gap_fast),('mixed_timestamp',mixed),('pending_timeout',pending_timeout),('stale_exit_quote',stale_exit),('no_exit_quote',unresolved),('short_margin_gap',margin),('invalid_bar',bad),('session_close',session),('order_expiry',expired),('clock_reorder',reordered_clock),('execution_during_skew',fill_skew),('quote_replay',quote_replay),('expiry_without_quotes',expiry_without_quotes),('recovered_skew_pending',recovered_skew_pending),('execution_feed_silence',execution_silence)]:run(name,fn)
    return rows,events

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('output',type=Path);a=p.parse_args();rows,events=selftest();a.output.mkdir(exist_ok=False)
    for name,data in [('scenarios.csv',rows),('events.csv',events)]:
        fields=list(dict.fromkeys(k for row in data for k in row));
        with (a.output/name).open('x',newline='',encoding='utf-8-sig') as f:w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(data)
    m=dict(mode='SYNTHETIC_ONLY',scenarios=len(rows),events=len(events),bar_seconds=STEP,assumed_delay_seconds=LAG,grace_seconds=GRACE,quote_max_age_seconds=QUOTE_MAX,quote_silence_seconds=QUOTE_SILENCE,unresolved=sum(r['open_legs']>0 for r in rows),notes='Independent hypothetical execution quote, not a broker; no live feed. Confirmed bars supplied by caller. No persistent state, reconnect, actual market execution or intrabar reproduction. No future pilot data accessed.')
    (a.output/'manifest.json').write_text(json.dumps(m,indent=2),encoding='utf-8');print(json.dumps(m,indent=2))
if __name__=='__main__':main()
