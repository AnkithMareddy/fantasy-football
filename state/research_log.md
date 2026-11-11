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
