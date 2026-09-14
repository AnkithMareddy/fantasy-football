# ShowMeYourTDs fantasy football

Season model and post-slate reports for my Sleeper league: ShowMeYourTDs, 12 teams, half PPR, redraft. Sleeper league ID `1385346462094741504`, my team is `uaintgotjuicehoeido`.

## What it does

- Pulls live rosters, standings, results, and the in-progress week from the Sleeper and ESPN public APIs.
- Simulates the rest of the season 10,000 times:
  - completed weeks use real scores
  - the current week uses points already scored
  - injured players return on researched dates, with a harsh injury model on top
- Produces playoff, bye, #1 seed, finals, and title odds for all 12 teams.
- Texts a written report through Messages after each NFL slate.

## Running it

```bash
./update.sh
```

Runs the whole pipeline and writes results to `state/latest_*.txt`. To text a report:

```bash
./send_text.sh reports/<file>.txt
```

## Files

| File | Purpose |
|---|---|
| `refresh.py` | live league data from Sleeper and ESPN |
| `season.py` | builds the model input from rosters, projections, and role overrides |
| `runseason.py` | season simulation |
| `league_table.py` | phone-friendly league odds and this week's matchups |
| `gameday.py` | box scores under league scoring, injuries, free agents who produced |
| `startsit.py` | conservative-floor start/sit call for the user's own lineup |
| `board.json` | preseason projections |
| `state/injury_overrides.json` | researched injury return weeks, maintained by the report run |
| `state/role_overrides.json` | evidenced role changes, maintained by the report run |
| `state/model_changelog.md` | every model change; read before explaining an odds move |
| `recipients.txt` | phone numbers for the text report (gitignored) |

## Schedule

Two Claude scheduled tasks:

- **Fantasy report text (ShowMeYourTDs)** — Sunday, Tuesday, and Friday at 8-9 AM. Researches injuries and news, updates the override files, re-runs the model, includes a start/sit call for the user's lineup, fact-checks, then texts the user and their co-manager. Sunday's run (8 AM, ahead of the early kickoffs) is the one that actually matters for lineup decisions — Tuesday and Friday are post-slate recaps where the roster's likely already locked or played.
- **Fantasy league recap (forward to group chat)** — Tuesday at 9:30 AM, after Monday Night Football wraps up. Re-runs the model (no new research), then writes a league-wide recap — all 6 matchups, standings, top performers, and updated playoff/title odds for all 12 teams — meant to be forwarded to the whole league's group chat. Texted to the same numbers in `recipients.txt`.

Both need the Claude app open and the Mac awake. `sudo pmset -a disablesleep 1` and `sudo pmset -a displaysleep 0` keep it from idle-sleeping, but a MacBook with the lid closed and no external display still force-sleeps regardless — leave the lid open (or attach an external display while on power) for these to fire reliably.
