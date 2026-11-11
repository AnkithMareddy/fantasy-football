# Research log

Why an override changed, and the source. The override files record *what* changed;
this records *why*.

This exists because the reasoning used to live only in the scheduled run's chat
session. On 2026-11-10, cleaning up old sessions would have destroyed it: a single run
had moved five players' return weeks with seven cited sources — A.J. Brown 9 to 12 on a
knee flare-up plus New England's bye, DeVonta Smith 10 to 11, Kyle Monangai 9 to 11 on
turf toe plus Chicago's bye — and `state/injury_overrides.json` held only the numbers.
That run even noted "these were data updates, not model changes, so I didn't add
anything to model_changelog.md", which was correct and is exactly why a second log was
needed.

Appended by the scheduled routine. Newest at the bottom. Keep entries to a line each:
player, what changed, why, source.

## 2026-11-10 (Tue evening, quiet refresh)
- Jalen Hurts: return_week 10 → 11. Still IR on Sleeper; Eagles bye is Week 10, so Week 11 is the earliest game. No activation news found. Source: https://www.nfl.com/schedules/2026/by-team/philadelphia-eagles
- Jordyn Tyson, Breece Hall: return_week 9 confirmed — both scored in Week 9 (3.0, 10.2 per Sleeper). No change.
- David Montgomery: kept at Week 10. Ruled out Week 9; reports say no return before Nov 15 at CLE, still week-to-week, hasn't practiced. Source: https://www.thefantasyfootballers.com/news/645916/david-montgomery-will-miss-sundays-game/
- TreVeyon Henderson: kept at Week 10. Still Out on Sleeper; no Week 10 practice report yet (first one is Wednesday).

## 2026-11-11 (Wed, post-waiver pre-slate — Week 10)

Thursday's game is WAS @ NYG, so the lock-in decision this week is a Giants
backfield question on a short week.

- Cam Skattebo (RB, NYG — uaintgotjuicehoeido): Sleeper lifted his Out designation. Hamstring from Week 7 vs HOU, missed Week 9 vs PHI. Limited Mon, FULL Tue, head coach called him "full go" for Thursday and said they chose not to limit him because of the short week. No game-status designation. START. Sources: https://www.giants.com/news/giants-vs-commanders-week-10-injury-report-qb-j-j-mccarthy-rb-cam-skattebo-limited , https://www.cbssports.com/nfl/news/cam-skattebo-injury-update-giants-rb-thursday-night-commanders/
- Devin Singletary (RB, NYG — same roster): not on the injury report at all. Took 93% of snaps and 21 carries in Week 9 only because Skattebo was out, and turned that into 31 yards (1.5 YPC). With Skattebo full, the Week 9 volume does not carry over. SIT. Source: https://www.thefantasyfootballers.com/analysis/select-snap-count-observations-transactions-for-week-10-fantasy-football/
- TreVeyon Henderson (RB, NE — kisiluv): return_week 10 → 12. Has not practised at all in November; neurological symptoms that required hospitalisation; out for Munich. Sleeper moved him Out → Questionable, but the beat reporting says he is not playing, so the designation is not a return signal. NE's bye is Week 11, so Week 12 at LAC is the earliest game. Sources: https://www.nbcsports.com/fantasy/football/news/nfl-week-10-injury-report-pats-backfield-in-flux-plus-gardner-minshew-michael-wilson-puka-nacua-injuries , https://www.nfl.com/schedules/2026/by-team/new-england-patriots
- Rhamondre Stevenson (RB, NE — zachschumann): new override, return_week 12. Knee tendon injury from the Week 9 GB loss, ruled out for Week 10, reported multi-week. Week 11 bye pushes the earliest game to Week 12. Source: as above.
- A.J. Brown (WR, NE — J2Money): return_week stays 12 despite Sleeper moving him Out → Questionable. Knee flare-up on top of the ankle, two games missed, expected to travel to Munich but likely held out through the Week 11 bye. A designation change is not a return. Sources: https://www.profootballrumors.com/2026/11/patriots-wr-a-j-brown-could-miss-week-10-with-knee-issue , https://www.espn.com/nfl/story/_/id/50329240/patriots-wr-aj-brown-ankle-knee-listed-questionable
- Puka Nacua (WR, LAR — raymondfeltons): Questionable → DOUBTFUL. The only downgrade on the board this week and the one the news scan got backwards (see model_changelog). Source: https://www.nbcsports.com/fantasy/football/news/nfl-week-10-injury-report-pats-backfield-in-flux-plus-gardner-minshew-michael-wilson-puka-nacua-injuries
- Corey Kiner (RB, NE — uaintgotjuicehoeido): in line for the bulk of New England's backfield work with Stevenson and Henderson both out, 15+ carries floated. Tempered by 11 snaps last week and Detroit allowing the second-fewest RB fantasy points. Flex-range, not a lock. Source: https://www.rotoballer.com/player-news/corey-kiner-could-lead-patriots-backfield-in-week-10/1988390
- Christian McCaffrey (RB, SF): hamstring called minor, practised in full and came off the report. No change. Source: https://sports.yahoo.com/articles/nfl-week-10-injury-report-192420951.html
- Patrick Mahomes (QB, KC): day-to-day with a right elbow strain, MRI showed no major injury, Reid positive. Matters to this league only through Travis Kelce (uaintgotjuicehoeido) and Rashee Rice (zachschumann) — Justin Fields starting would cut both. Sunday decision, not Thursday. Source: https://www.foxsports.com/stories/nfl/patrick-mahomes-elbow-injury-update-chiefs
- J.K. Dobbins (RB, DEN — uaintgotjuicehoeido): Denver is on bye in Week 10. Unstartable, no injury involved.
- No change: Trey McBride, Chris Olave, DK Metcalf, Ollie Gordon II, Jameson Williams — none on an injury report. Gordon draws Indianapolis, bottom-third against RBs; Williams draws a New England defence allowing among the most fantasy points per game to receivers.
