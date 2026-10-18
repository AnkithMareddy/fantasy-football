import json, random, statistics, os
from collections import defaultdict
D=json.load(open('season_input.json')); teams=D['teams']; SCHED=D['sched']
NAMES=list(SCHED.keys())
# weeks that are already played use the REAL scores, not simulated ones
ACT={}
if os.path.exists('state/actuals.json'):
    ACT={int(k):v for k,v in json.load(open('state/actuals.json')).items()}
CV={'QB':0.28,'RB':0.42,'WR':0.40,'TE':0.40,'K':0.34,'DEF':0.55}
SLOTS=[('QB',1),('RB',2),('WR',2),('TE',1)]
N=4000
rnd=random.Random(20260907); gauss=rnd.gauss; rand=rnd.random

wk_scores={t:[[] for _ in range(14)] for t in NAMES}
wk_wins  ={t:[0]*14 for t in NAMES}
season_w ={t:[] for t in NAMES}
season_pf={t:[] for t in NAMES}
made_po  ={t:0 for t in NAMES}
titles   ={t:0 for t in NAMES}
byes     ={t:0 for t in NAMES}
games_missed=defaultdict(list)

def dur():
    r=rand()
    if r<0.42: return 1
    if r<0.68: return 2
    if r<0.82: return 3
    if r<0.90: return 5
    if r<0.96: return 8
    return 17                      # season-ending

for s in range(N):
    out={t:{} for t in NAMES}      # player idx -> weeks remaining out
    # players already hurt start the simulated season unavailable
    for t in NAMES:
        for i,p in enumerate(teams[t]):
            st=(p.get('inj') or '').upper()
            if p.get('ir') or st in ('IR','PUP','SUS','NA','COV'): out[t][i]=4
            elif st in ('OUT','DOUBTFUL'): out[t][i]=1
    missed=defaultdict(int)
    wins={t:0 for t in NAMES}; pf={t:0.0 for t in NAMES}
    wkpts={t:[0.0]*14 for t in NAMES}
    for w in range(1,15):
        if w in ACT:
            for t in NAMES:
                wkpts[t][w-1]=float(ACT[w].get(t,0.0)); pf[t]+=wkpts[t][w-1]
            for t in NAMES:
                if wkpts[t][w-1]>wkpts[SCHED[t][w-1]][w-1]: wins[t]+=1; wk_wins[t][w-1]+=1
            continue
        for t in NAMES:
            R=teams[t]; avail=defaultdict(list)
            for i,p in enumerate(R):
                o=out[t].get(i,0)
                if o>0:
                    out[t][i]=o-1; missed[(t,p['n'])]+=1; continue
                if p['bye']==w: continue
                if rand()<p['hz']:
                    out[t][i]=dur(); missed[(t,p['n'])]+=1; continue
                v=gauss(p['ppg'], p['ppg']*CV[p['pos']])
                avail[p['pos']].append(v if v>0 else 0.0)
            for k in avail: avail[k].sort(reverse=True)
            tot=0.0; used=defaultdict(int)
            for pos,n in SLOTS:
                g=avail[pos][:n]; tot+=sum(g); used[pos]=len(g)
            flex=[]
            for pos in ('RB','WR','TE'): flex+=avail[pos][used[pos]:]
            if flex: tot+=max(flex)
            for pos in ('K','DEF'):
                if avail[pos]: tot+=avail[pos][0]
            wkpts[t][w-1]=tot; pf[t]+=tot
        for t in NAMES:
            o=SCHED[t][w-1]
            if wkpts[t][w-1]>wkpts[o][w-1]: wins[t]+=1; wk_wins[t][w-1]+=1
    for t in NAMES:
        for w in range(14): wk_scores[t][w].append(wkpts[t][w])
        season_w[t].append(wins[t]); season_pf[t].append(pf[t])
    for (t,n),g in missed.items(): games_missed[(t,n)].append(g)
    seeds=sorted(NAMES, key=lambda t:(-wins[t], -pf[t]))[:6]
    for t in seeds: made_po[t]+=1
    for t in seeds[:2]: byes[t]+=1
    def play(a,b):
        sa=sum(gauss(statistics.fmean(wk_scores[a][-1] or [110]),18) for _ in range(1))
        return a
    # playoff rounds use fresh weekly draws from each roster's distribution
    def score(t):
        R=teams[t]; avail=defaultdict(list)
        for p in R:
            if rand()>0.93: continue
            v=gauss(p['ppg'], p['ppg']*CV[p['pos']])
            avail[p['pos']].append(v if v>0 else 0.0)
        for k in avail: avail[k].sort(reverse=True)
        tot=0.0; used=defaultdict(int)
        for pos,n in SLOTS:
            g=avail[pos][:n]; tot+=sum(g); used[pos]=len(g)
        fl=[]
        for pos in ('RB','WR','TE'): fl+=avail[pos][used[pos]:]
        if fl: tot+=max(fl)
        for pos in ('K','DEF'):
            if avail[pos]: tot+=avail[pos][0]
        return tot
    r1a = seeds[2] if score(seeds[2])>score(seeds[5]) else seeds[5]
    r1b = seeds[3] if score(seeds[3])>score(seeds[4]) else seeds[4]
    s1  = seeds[0] if score(seeds[0])>score(r1b) else r1b
    s2  = seeds[1] if score(seeds[1])>score(r1a) else r1a
    champ = s1 if score(s1)>score(s2) else s2
    titles[champ]+=1

out={'weekly':{},'season':{}}
for t in NAMES:
    out['weekly'][t]=[{'med':statistics.median(wk_scores[t][w]),
                       'mean':statistics.fmean(wk_scores[t][w]),
                       'winpct':wk_wins[t][w]/N} for w in range(14)]
    out['season'][t]={'w':statistics.fmean(season_w[t]),'pf':statistics.fmean(season_pf[t]),
                      'po':made_po[t]/N,'bye':byes[t]/N,'title':titles[t]/N}
json.dump(out, open('season_out.json','w'))
print(f"{'TEAM':<22}{'W-L':>9}{'PF':>8}{'PLAYOFF%':>10}{'BYE%':>8}{'TITLE%':>8}")
print('-'*65)
for t,d in sorted(out['season'].items(), key=lambda kv:-kv[1]['po']):
    print(f"{t:<22}{d['w']:>5.1f}-{14-d['w']:<4.1f}{d['pf']:>8.0f}{d['po']*100:>9.1f}%{d['bye']*100:>7.1f}%{d['title']*100:>7.1f}%")
print("\n=== HARSH INJURY MODEL: expected games missed (key players) ===")
gm=sorted(((statistics.fmean(v),t,n) for (t,n),v in games_missed.items() if len(v)>N*0.25), reverse=True)
for g,t,n in gm[:18]: print(f"  {n:<24}{t:<22}{g:>5.1f} games")
