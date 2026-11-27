"""R62: audit verified synthetic replay; no market data, orders, or performance claims."""
import argparse, copy, hashlib, importlib.util, json, sys, tempfile
from pathlib import Path
from collections import Counter
P=Path(__file__).with_name('Chappy_Trading_Durable_Replay_v0.1.py')
PIN='c35aaefdee534453a8f2c656c317f629a0213ef290b32ce99a1400b175f24312'
if hashlib.sha256(P.read_bytes()).hexdigest()!=PIN:raise RuntimeError('R61 hash mismatch')
spec=importlib.util.spec_from_file_location('r61',P);d=importlib.util.module_from_spec(spec);sys.modules[spec.name]=d;spec.loader.exec_module(d)
e=d.r;r=e.r;need=r.need

def review(records,expected_head,cutoff):
    need(type(cutoff) is int and cutoff>=0,'cutoff')
    need(isinstance(expected_head,str) and len(expected_head)==64,'external head required')
    full=e.restore(records,expected_head)
    events=[x['event'] for x in full['records'] if x['event']['at']<=cutoff]
    prefix=e.seal(events);s=prefix['result'];a=r.review.audit(s['journal'],s['journal_head'],cutoff)
    # R60 has only one allocation and no earlier orders. Reconstruct its actual plan,
    # not a guess based on which intents or fills happened to arrive.
    g=r.recovery.Gate();j=r.j48.Journal();p=None;ph=None;health=None;held=dict.fromkeys(r.SYMBOLS,0)
    for x in events:
        t=x['at'];v=x['data'];k=x['kind']
        if k=='tick':
            health=g.tick(t,r.recovery.dep.feed(v['changes'],t),r.recovery.snapshot(t,r.CAP,held),v['external'],v['approval'],tuple(v['exit_requested']))
        elif k=='observe':j.observations(t,v['rows'])
        elif k=='allocate':
            p,ph=r.allocate(j,g,health,t,r.CAP,held,v['scores'],v['uncertainty'],v['scenarios']);need(s['plans']=={str(t):ph},'plan reconstruction mismatch');break
        else:raise ValueError('unsupported pre-allocation event')
    need(len(a['rows'])==(len(r.SYMBOLS) if p else 0),'decision universe mismatch')
    rows=[]; net=0; realized=0; open_cost=0; fees=0
    for row in a['rows']:
        symbol=row['symbol'];selected=symbol in p['allocation']['held'];fs=[f for f in s['fills'] if f['symbol']==symbol]
        buys=[f for f in fs if f['side']=='BUY'];sells=[f for f in fs if f['side']=='SELL'];need(len(buys)<=1 and len(sells)<=1,'single round only')
        intents=[x['data'] for x in events if x['kind']=='intent' and x['data']['symbol']==symbol and x['data']['side']=='BUY'];need(len(intents)<=1,'multiple entries')
        order=intents[0]['order'] if intents else None
        if order:need(selected and intents[0]['plan_sha']==ph,'unbound intent')
        if buys:need(buys[0]['plan_sha']==ph and buys[0]['order']==order,'unbound buy')
        bc=sum(f['qty']*f['price']*100+f['fee_cents'] for f in buys);sp=sum(f['qty']*f['price']*100-f['fee_cents'] for f in sells)
        fee=sum(f['fee_cents'] for f in fs);fees+=fee;net+=sp-bc
        if sells:
            need(buys and buys[0]['qty']==sells[0]['qty'] and s['held'][symbol]==0,'closed quantity mismatch');status='CLOSED';pnl=sp-bc;realized+=pnl
        elif buys:
            status='OPEN_POSITION';pnl=None;open_cost+=bc
        else:
            status=('CANCELLED' if order and s['terminal'].get(order)=='CANCELLED' else 'PENDING' if order else 'SELECTED_NO_INTENT' if selected else 'NOT_SELECTED' if row['gate']=='RESEARCH_ELIGIBLE' else 'GATE_BLOCKED');pnl=None
        rows.append({**row,'selected':selected,'allocation_exclusion':p['exclusions'].get(symbol),'entry_order':order,'status':status,'realized_pnl_cents':pnl,'fees_cents':fee,'open_cost_cents':bc if status=='OPEN_POSITION' else 0,'fills':fs})
    need(r.CAP+net==s['cash_cents'] and net==realized-open_cost,'cash reconciliation')
    need(sum(len(x['fills']) for x in rows)==len(s['fills']),'unattributed fill')
    return {'scope':'synthetic single allocation; no mark-to-market or causal attribution','cutoff':cutoff,'source_head':expected_head,'prefix_head':prefix['head'],'last_event_at':events[-1]['at'] if events else None,'plan_sha':ph,'hypothesis_summary':a['summary'],'rows':rows,'execution_summary':{'statuses':dict(Counter(x['status'] for x in rows)),'cash_cents':s['cash_cents'],'realized_pnl_cents':realized,'closed_count':sum(x['status']=='CLOSED' for x in rows),'open_cost_cents':open_cost,'fees_cents':fees,'pending_orders':s['pending'],'held':s['held']},'live_adoption':False}

def from_store(path,expected_head,cutoff):
    store=d.Store(path)
    try:v=store.inspect();return review(v['records'],expected_head,cutoff)
    finally:store.close()

def self_test():
    tests=[];examples={}
    def ck(n,x,y=True):
        if x!=y:raise AssertionError((n,x,y))
        tests.append({'name':n,'pass':True})
    def reject(n,fn):
        try:fn()
        except (ValueError,KeyError,TypeError):ck(n,True)
        else:ck(n,False)
    for case in ('normal','cancel'):
        ev=e.fixture(case=='cancel');v=e.seal(ev);rec=v['records'];h=v['head'];a=review(rec,h,145);examples[case]=a;by={x['symbol']:x for x in a['rows']};summary=a['execution_summary']
        ck(case+' all hypotheses',a['hypothesis_summary']['decisions'],3);ck(case+' unresolved A',by['A']['observed_outcome'],'EXPIRED_UNRESOLVED');ck(case+' A not selected',by['A']['status'],'NOT_SELECTED');ck(case+' A no pnl',by['A']['realized_pnl_cents'],None);ck(case+' B confirmed',by['B']['observed_outcome'],'CONFIRMED_OBSERVED');ck(case+' B profit',by['B']['realized_pnl_cents'],189790);ck(case+' C refuted',by['C']['observed_outcome'],'REFUTED');ck(case+' C status',by['C']['status'],'CANCELLED' if case=='cancel' else 'CLOSED');ck(case+' C pnl',by['C']['realized_pnl_cents'],None if case=='cancel' else -139880);ck(case+' realized',summary['realized_pnl_cents'],189790 if case=='cancel' else 49910);ck(case+' cash',summary['cash_cents'],v['result']['cash_cents']);ck(case+' closed count',summary['closed_count'],1 if case=='cancel' else 2);ck(case+' fees',summary['fees_cents'],20210 if case=='cancel' else 40090);ck(case+' denominator',a['hypothesis_summary']['confirmed_over_resolved'],'1/2');ck(case+' full denominator',a['hypothesis_summary']['confirmed_over_eligible'],'1/3');ck(case+' before deadline',review(rec,h,140)['rows'][0]['observed_outcome'],'OPEN_UNRESOLVED');ck(case+' cutoff115',review(rec,h,115)['execution_summary']['realized_pnl_cents'],0);ck(case+' open cost',review(rec,h,115)['execution_summary']['open_cost_cents'],10010000 if case=='cancel' else 20020000)
        for i in range(len(ev)+1):
            q=e.seal(ev[:i]);out=review(q['records'],q['head'],ev[i-1]['at'] if i else 0);ck(case+' prefix '+str(i),out['execution_summary']['cash_cents'],q['result']['cash_cents'])
        for t in (0,100,110,115,120,125,140):
            q=e.seal([x for x in ev if x['at']<=t]);u=review(rec,h,t);w=review(q['records'],q['head'],t);u.pop('source_head');w.pop('source_head');ck(case+' temporal '+str(t),u,w)
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'audit.db';store=d.Store(path,True);store.authorize(e.Z,[]);head=e.Z
            for x in ev:head=store.append(x,head)['head']
            store.close();ck(case+' reopened report',from_store(path,h,145),a);reject(case+' wrong db head',lambda:from_store(path,e.Z,145))
        reject(case+' bad head',lambda:review(rec,e.Z,145));reject(case+' truncation',lambda:review(rec[:-1],h,145));bad=copy.deepcopy(rec);bad[-1]['state_sha']=e.Z;reject(case+' tamper',lambda:review(bad,h,145));reject(case+' negative cutoff',lambda:review(rec,h,-1));reject(case+' bool cutoff',lambda:review(rec,h,True))
    return {'test_count':len(tests),'tests':tests},examples
if __name__=='__main__':
    ap=argparse.ArgumentParser();g=ap.add_mutually_exclusive_group(required=True);g.add_argument('--self-test',action='store_true');g.add_argument('--example',action='store_true');args=ap.parse_args();t,x=self_test();print(json.dumps(t if args.self_test else x,sort_keys=True,indent=2))
