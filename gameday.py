#!/usr/bin/env python3
"""Post-game pipeline. Run after any slate:  python3 gameday.py [week]
Pulls every completed NFL game, scores every player under THIS league's rules,
extracts injuries, maps to league rosters, flags waiver targets, and writes state."""
import json, sys, re, os, subprocess
from collections import defaultdict

SB="https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"
SUM="https://site.api.espn.com/apis/site/v2/sports/football/nfl/summary?event="
def get(u):
    out=subprocess.run(['curl','-s','--max-time','30',u],capture_output=True,text=True)
    return json.loads(out.stdout)
def norm(x):
    x=x.lower().replace('.','').replace("'",'').replace('-',' ')
    x=re.sub(r'\b(jr|sr|ii|iii|iv)\b','',x); return ' '.join(x.split())

# ---- league scoring ----
def pts(s):
    return (s.get('pyd',0)*0.04 + s.get('ptd',0)*4 - s.get('int',0)*2
          + s.get('ryd',0)*0.10 + s.get('rtd',0)*6
          + s.get('rec',0)*0.5 + s.get('reyd',0)*0.10 + s.get('retd',0)*6
          - s.get('fl',0)*2)

rost=json.load(open('sleeper/rosters.json')); slot=json.load(open('sleeper/slot_name.json'))
OWN={}
for s,pl in rost.items():
    for p in pl: OWN[norm(p['name'])]=slot[s]

week = int(sys.argv[1]) if len(sys.argv)>1 else None
sb=get(SB)
wk = week or sb.get('week',{}).get('number',1)
games=[]
for e in sb.get('events',[]):
    st=e['competitions'][0]['status']['type']['name']
    if st in ('STATUS_FINAL','STATUS_IN_PROGRESS','STATUS_END_PERIOD','STATUS_HALFTIME'):
        games.append((e['id'], st, e.get('shortName','')))

stats=defaultdict(lambda: defaultdict(float)); meta={}; injuries=[]
for eid, st, nm in games:
    try: d=get(SUM+eid)
    except Exception as ex:
        print(f"  ! could not fetch {nm}: {ex}"); continue
    for inj in d.get('injuries',[]):
        ab=inj.get('team',{}).get('abbreviation')
        for it in inj.get('injuries',[]):
            a=it.get('athlete',{}); det=(it.get('details') or {})
            if it.get('status') and 'Coach' not in str(det.get('type','')):
                injuries.append({'team':ab,'player':a.get('displayName','?'),
                                 'status':it.get('status'),'type':det.get('type',''),
                                 'game':nm})
    for team in d.get('boxscore',{}).get('players',[]):
        ab=team['team']['abbreviation']
        for cat in team.get('statistics',[]):
            c=cat.get('name'); labs=[l.upper() for l in cat.get('labels',[])]
            for a in cat.get('athletes',[]):
                pn=a['athlete']['displayName']; k=norm(pn)
                meta[k]={'name':pn,'team':ab,'game':nm,'status':st}
                v=dict(zip(labs, a.get('stats',[])))
                def num(x):
                    try: return float(str(x).split('/')[0])
                    except: return 0.0
                if c=='passing':
                    ca=str(v.get('C/ATT','0/0')).split('/')
                    stats[k]['pyd']+=num(v.get('YDS')); stats[k]['ptd']+=num(v.get('TD'))
                    stats[k]['int']+=num(v.get('INT')); stats[k]['cmp']+=num(ca[0])
                    stats[k]['att']+=num(ca[1] if len(ca)>1 else 0)
                elif c=='rushing':
                    stats[k]['car']+=num(v.get('CAR')); stats[k]['ryd']+=num(v.get('YDS'))
                    stats[k]['rtd']+=num(v.get('TD'))
                elif c=='receiving':
                    stats[k]['rec']+=num(v.get('REC')); stats[k]['reyd']+=num(v.get('YDS'))
                    stats[k]['retd']+=num(v.get('TD')); stats[k]['tgt']+=num(v.get('TGTS'))
                elif c=='fumbles':
                    stats[k]['fl']+=num(v.get('LOST'))

rows=[]
for k,s in stats.items():
    fp=pts(s)
    rows.append({'k':k,'name':meta[k]['name'],'team':meta[k]['team'],'game':meta[k]['game'],
                 'status':meta[k]['status'],'fp':round(fp,1),
                 'own':OWN.get(k),'car':s.get('car',0),'tgt':s.get('tgt',0),
                 'rec':s.get('rec',0),'ryd':s.get('ryd',0),'reyd':s.get('reyd',0)})
rows.sort(key=lambda r:-r['fp'])
state={'week':wk,'games':[g[2] for g in games],'players':rows,'injuries':injuries}
os.makedirs('state',exist_ok=True)
json.dump(state, open(f'state/week{wk}.json','w'), indent=1)

print(f"WEEK {wk} — {len(games)} game(s) with data: {', '.join(g[2] for g in games)}\n")
print("=== TOP FANTASY PERFORMERS (this league's scoring) ===")
print(f"  {'PLAYER':<24}{'TM':<5}{'PTS':>6}   OWNER")
for r in rows[:14]:
    print(f"  {r['name']:<24}{r['team']:<5}{r['fp']:>6.1f}   {r['own'] or '** FREE AGENT **'}")
print("\n=== INJURIES ===")
for i in injuries:
    o=OWN.get(norm(i['player']))
    print(f"  {i['team']:<4}{i['player']:<24}{i['status']:<14}{i['type']:<14}{o or ''}")
print("\n=== FREE AGENTS WHO PRODUCED ===")
fa=[r for r in rows if not r['own'] and r['fp']>=4]
for r in fa[:10]:
    print(f"  {r['name']:<24}{r['team']:<5}{r['fp']:>6.1f}  car {r['car']:.0f} tgt {r['tgt']:.0f}")
if not fa: print("  (none yet)")
