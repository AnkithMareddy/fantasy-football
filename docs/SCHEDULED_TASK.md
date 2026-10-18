# One scheduled task for everything

This replaces the four separate Claude scheduled tasks (Sunday 8 AM start/sit,
the Thu/Sun/Mon 11 PM post-slate report, the Tuesday recap, and the nightly site
refresh) with a single task. The prompt below checks the day and time and
decides what to do, so the behavior is the same as before.

## Setup in the Claude app

1. Create one scheduled task with the project folder `~/fantasy-football`.
2. Schedule: **every day at 8:00 AM and 11:00 PM**. If the app only allows one
   time per task, use **every day at 11:00 PM**. The prompt then folds the
   Sunday start/sit into Saturday night and the Tuesday recap into Monday night.
3. Paste the prompt below.
4. Turn off, then delete, the four old fantasy tasks.

The Mac still needs to be awake with the lid open for it to fire (see README).

## Prompt

```text
You run the ShowMeYourTDs fantasy pipeline in ~/fantasy-football. Read README.md
first; it describes every script and file. Check the local day and time
(`date`) and do exactly ONE of the modes below.

MODE A — Sunday morning (Sunday before noon): START/SIT.
  Research injury and inactive news for the user's roster (uaintgotjuicehoeido)
  and this week's opponents. Update state/injury_overrides.json and
  state/role_overrides.json only with evidenced changes. Run ./update.sh. Lead
  the report with the start/sit call from state/latest_startsit.txt, then
  odds and waiver notes. Fact-check, then text it with ./send_text.sh.
  Deploy the site with ./deploy_site.sh.

MODE B — Thursday, Sunday or Monday night (after 6 PM): POST-SLATE REPORT.
  Research injuries and news, update the override files, run ./update.sh.
  Write the per-manager report: what happened, injuries/role changes with
  owners named, league-wide waiver pickups and every team's FAAB
  (state/latest_waivers.txt), a start/sit note, playoff/title odds. Fact-check,
  text it with ./send_text.sh, deploy the site with ./deploy_site.sh.
  ON MONDAY NIGHT ONLY, also do MODE C's recap after the report.

MODE C — Tuesday morning (Tuesday before noon): LEAGUE RECAP.
  Skip this mode if Monday night's run already wrote this week's recap file.
  No new research. Run ./update.sh, deploy the site, and write a league-wide
  recap (all 6 matchups, standings, top performers, playoff/title odds for all
  12 teams) plus a draft X thread. Save both as local files in reports/.
  NEVER text or post these; the user sends them by hand.

MODE D — Tuesday, Wednesday, Friday or Saturday night: QUIET REFRESH.
  Check for real injury/status news, especially any injury_overrides.json
  entry whose return_week has arrived. Update override files only if
  warranted, run ./update.sh, deploy the site. No text, no report file, and no
  notification unless something actually changed.
  ON SATURDAY NIGHT, if this task only runs once a day, also do MODE A's
  start/sit research and text it, since there is no Sunday morning run.

Any other morning: do nothing and stop immediately.

Always: if a data pull fails, do not guess or fabricate; say in one sentence
what failed and stop. Log any model change in state/model_changelog.md.
```
