#!/usr/bin/env python3
"""Pulls real highlight clips and recap articles from ESPN's public game-summary endpoint —
never hosts or re-clips any video ourselves, only links out to ESPN's own pages. Tags each clip
with any of our rostered players named in its headline, and their fantasy owner, so the site can
filter highlights by team/player without needing a play-by-play parser of our own.

Run after gameday.py (reuses its game-fetching pattern). Writes state/highlights.json."""
import json, re, subprocess, os
from collections import defaultdict

os.chdir(os.path.dirname(os.path.abspath(__file__)))
SB = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"
SUM = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/summary?event="

def get(u):
    out = subprocess.run(['curl', '-s', '--max-time', '30', u], capture_output=True, text=True)
    return json.loads(out.stdout)

def norm(x):
    x = x.lower().replace('.', '').replace("'", '').replace('-', ' ')
    x = re.sub(r'\b(jr|sr|ii|iii|iv)\b', '', x)
    return ' '.join(x.split())

rost = json.load(open('sleeper/rosters.json'))
slot = json.load(open('sleeper/slot_name.json'))
OWN = {}          # normalized player name -> owning team
ROSTER_NAMES = []  # (normalized name, display name) for substring matching against headlines
for s, pl in rost.items():
    for p in pl:
        n = norm(p['name'])
        OWN[n] = slot[s]
        ROSTER_NAMES.append((n, p['name']))
# match longer names first so "Josh Allen" doesn't get shadowed by a shorter partial elsewhere
ROSTER_NAMES.sort(key=lambda t: -len(t[0]))

sb = get(SB)
wk = sb.get('week', {}).get('number', 1)
games = [(e['id'], e.get('shortName', '')) for e in sb.get('events', [])
         if e['competitions'][0]['status']['type']['name'] in
         ('STATUS_FINAL', 'STATUS_IN_PROGRESS', 'STATUS_END_PERIOD', 'STATUS_HALFTIME')]

highlights = []
recaps = []
for eid, short in games:
    try:
        d = get(SUM + eid)
    except Exception:
        continue
    header_links = {l.get('rel', [None])[0]: l['href'] for l in d.get('header', {}).get('links', [])}
    article = d.get('article')
    if article:
        recaps.append({'game': short, 'headline': article.get('headline'),
                       'link': header_links.get('recap') or header_links.get('summary')})
    for v in d.get('videos', []):
        headline = v.get('headline', '')
        if 'Game Highlights' in headline:
            kind = 'recap'
        else:
            kind = 'play'
        web = (v.get('links', {}) or {}).get('web', {}).get('href')
        if not web:
            continue
        players, owners = [], set()
        remaining = headline
        for nname, dname in ROSTER_NAMES:
            if nname and nname in norm(remaining):
                players.append(dname)
                owners.add(OWN[nname])
                remaining = remaining.replace(dname, '')   # avoid double-tagging shared last names
        highlights.append({
            'game': short, 'kind': kind, 'headline': headline,
            'video_url': web, 'thumbnail': v.get('thumbnail'),
            'players': players, 'owners': sorted(owners),
        })

# recap-type first (one per game, sets the scene), then individual plays
highlights.sort(key=lambda h: (h['kind'] != 'recap', h['game']))
json.dump({'week': wk, 'highlights': highlights, 'recaps': recaps},
          open('state/highlights.json', 'w'), indent=1)

tagged = sum(1 for h in highlights if h['owners'])
print(f"WEEK {wk} HIGHLIGHTS — {len(highlights)} clips from {len(games)} game(s), "
     f"{tagged} tagged to a rostered player, {len(recaps)} recap articles")
for h in highlights[:20]:
    tag = f"  [{', '.join(h['owners'])}]" if h['owners'] else ""
    print(f"  ({h['kind']}) {h['headline']}{tag}")
