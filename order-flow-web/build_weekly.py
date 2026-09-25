from __future__ import annotations
import csv, hashlib, io, json, urllib.request, zipfile
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
BASE='https://data.binance.vision/data/futures/um/daily/aggTrades/{s}/{s}-aggTrades-{d}.zip'
SYMBOL='BTCUSDT'
OUT=Path(__file__).with_name('weekly-vp.json')

def get(url,timeout=90):
    req=urllib.request.Request(url,headers={'User-Agent':'order-flow-lab/0.4'})
    with urllib.request.urlopen(req,timeout=timeout) as r:return r.read()

def load_day(day):
    ds=day.isoformat(); url=BASE.format(s=SYMBOL,d=ds)
    try: blob=get(url)
    except Exception as e:
        print('skip',ds,type(e).__name__,e); return None
    try:
        chk=get(url+'.CHECKSUM').decode().strip().split()[0].lower()
        got=hashlib.sha256(blob).hexdigest().lower()
        if chk!=got: raise RuntimeError('checksum mismatch '+ds)
    except Exception as e:
        print('checksum failure',ds,e); return None
    ladder=defaultdict(lambda:[0.0,0.0])
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        names=[n for n in z.namelist() if n.lower().endswith('.csv')]
        if len(names)!=1: raise RuntimeError('unexpected zip members')
        with z.open(names[0]) as f:
            text=io.TextIOWrapper(f,encoding='utf-8',newline='')
            rd=csv.reader(text)
            first=True; idx=None
            for r in rd:
                if not r: continue
                if first:
                    first=False
                    if not r[0].lstrip('-').isdigit():
                        h={x.strip().lower():i for i,x in enumerate(r)}
                        idx=(h.get('price'),h.get('quantity'),h.get('is_buyer_maker'))
                        continue
                if idx:
                    pi,qi,mi=idx; p=float(r[pi]); q=float(r[qi]); m=r[mi].strip().lower() in ('true','1')
                else:
                    p=float(r[1]); q=float(r[2]); m=r[6].strip().lower() in ('true','1')
                k=int(p)
                if m: ladder[k][1]+=q
                else: ladder[k][0]+=q
    return ladder

def merge(days):
    out=defaultdict(lambda:[0.0,0.0]); ok=[]
    for d in days:
        lad=load_day(d)
        if lad is None: continue
        ok.append(d.isoformat())
        for k,(buy,sell) in lad.items(): out[k][0]+=buy; out[k][1]+=sell
    rows=[[k,round(v[0],8),round(v[1],8)] for k,v in sorted(out.items())]
    return ok,rows

def main():
    now=datetime.now(timezone.utc); today=now.date(); mon=today-timedelta(days=today.weekday())
    prev_start=mon-timedelta(days=7); prev=[prev_start+timedelta(days=i) for i in range(7)]
    current=[mon+timedelta(days=i) for i in range(max(0,(today-mon).days))]
    pd,pr=merge(prev); cd,cr=merge(current)
    data={'schema':'binance-vision-weekly-vp-v1','symbol':SYMBOL,'generatedAt':now.isoformat().replace('+00:00','Z'),
          'previous':{'label':prev_start.isoformat()+' to '+(mon-timedelta(days=1)).isoformat(),'days':pd,'rows':pr},
          'current':{'label':mon.isoformat()+' to archived days before '+today.isoformat(),'days':cd,'rows':cr}}
    OUT.write_text(json.dumps(data,separators=(',',':')),encoding='utf-8')
    print('wrote',OUT,'previous days',len(pd),'current days',len(cd),'rows',len(pr),len(cr))
if __name__=='__main__': main()
