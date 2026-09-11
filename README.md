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
| `board.json` | preseason projections |
| `state/injury_overrides.json` | researched injury return weeks, maintained by the report run |
| `state/role_overrides.json` | evidenced role changes, maintained by the report run |
| `state/model_changelog.md` | every model change; read before explaining an odds move |
| `recipients.txt` | phone numbers for the text report (gitignored) |

## Schedule

A Claude scheduled task, **Fantasy report text (ShowMeYourTDs)**, runs every Monday, Tuesday, and Friday at 9:00 AM:

1. Researches injuries and news.
2. Updates the override files.
3. Re-runs the model.
4. Fact-checks the report, then texts it.

The Claude app must be open. `sudo pmset -a disablesleep 1` keeps the Mac awake with the lid closed.
