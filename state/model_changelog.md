# Model changelog
Read this before explaining any change in odds between reports. Newest first.

## 2026-09-10 (Thu night) - model rebuild
- Rosters pulled live from Sleeper every run (was: draft-day rosters). Three teams that drafted no kicker (kisiluv, joshsandorra, Gujju8) now have one. This was the main cause of this team's drop from the preseason 75% playoff odds to 64%.
- Players on IR, Out, PUP, suspended or NA now start the simulation unavailable. Researched return weeks in state/injury_overrides.json override the generic rule (4 weeks for IR-type statuses, 1 week for Out or Doubtful).
- Weekly scoring variance raised to realistic levels: a team's weekly score now swings ~18-20 pts (was ~11). This pulls extreme odds toward the middle.
- Lineups are chosen by projection before games, not after seeing scores. This removed a hindsight bias worth +3-4 pts/week.
- The in-progress week uses real points already scored, plus the best lineup from players who haven't played.
- Simulations raised from 4,000 to 10,000 seasons.
- Net for uaintgotjuicehoeido: 4th / 64% playoffs / 10% title in the Thu 11 PM text (old model) became 3rd / 61% / 11% (new model). That change came from these model fixes, not sampling noise.
