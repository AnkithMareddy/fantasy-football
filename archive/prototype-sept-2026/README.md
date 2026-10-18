# Prototype, September 2026

These files were recovered from `~/fantasy-2026`, the folder this pipeline was
first built in before it moved here. They are frozen on purpose: nothing in the
live pipeline imports them, and they are kept only because they show how the
model actually changed under pressure during the first week of the season.

## The season simulator, in four versions

| File | Lines | What it was |
|---|---|---|
| `runseason_v1.py` | 122 | First working sim. 4,000 seasons, every week simulated, generic injury rule. |
| `runseason_v2.py` | 172 | Real results lock in for completed weeks; researched injury return weeks arrive. |
| `runseason_v3.py` | 200 | Realistic weekly variance (gamma draws) replaces the too-narrow normal draws. |
| `../../runseason.py` | 247 | Current. Lineups are chosen by projection before kickoff, not after seeing scores. |

Each jump came from finding something wrong, not from adding a feature. See
[docs/EVOLUTION.md](../../docs/EVOLUTION.md) for what each one fixed and what it
did to the numbers.

## `refresh_v1.py`

The first live-data puller, before it tracked per-starter game state, injury
status, or the in-progress week.

## `draft_board_scored.json`

The draft-day valuation board: 155 players scored under this league's exact
rules, with ADP and value over replacement. This is the artifact the live draft
ran on, and the direct ancestor of `board.json`.
