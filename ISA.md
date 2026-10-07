---
phase: climbing
progress: 12/16
principal_stated_goal: "I merged. Please go ahead building phase 3."
---

# Durf heilig te zijn

## Problem

Eight to fifteen people (thirteen-year-olds plus leaders) each need to be matched to a saint they recognize themselves in, from a curated set of 77, before the game afternoon of Saturday 11 October 2026. The design lives in `docs/design/plan-heiligen-welkomstspel.md` and `docs/design/rubric.md`. Phase 3 of that plan is the deterministic core: the question bank, the scoring and matching, and a simulation that shows the matching spreads over the set instead of handing everyone the same few saints.

## Vision

Jelle answers twelve either-or questions as three different kinds of teenager, and each time the top three reads like that teenager: the quiet reader gets Thérèse or Edith Stein, the joker who organizes everything gets Filippus Neri or Don Bosco, never the same three saints for everyone. The simulation report tells him in one screen whether the set is healthy and which saints never come up, so he knows which records to look at before Thursday.

## Out of Scope

- The quiz web app, the LLM follow-up questions and explanations (phase 4).
- The game screens and voting (phase 5), deployment (phase 6).
- Changing saint records; the simulation reports on them, Jelle edits them through git.

## Goal

Phase 3 of the plan: a question bank of 24 either-or questions (four per axis) plus the interest question, the deterministic scoring and matching exactly as `rubric.md` specifies, and a reproducible simulation of 200 fictional teen profiles checked against the plan's requirements, plus a way for Jelle to play the quiz himself.

## Claims

- [x] ISC-1: `data/vragen.json` holds exactly 4 either-or questions per axis (24 total) and one interest question listing exactly the 10 interests from `data/heiligen.json`; every question has a question text, two answers and an icon per answer.
- [x] ISC-2: For every axis, the − answer and + answer of each question map to the poles named in `rubric.md` (− for samen_alleen is "alleen"), checked against the rubric's example saints' signs in the data.
- [x] ISC-3: Loading the data validates every saint: six axis keys, scores in {−2..2} or null, ≥4 known axes, 1–3 interests from the list, gender in {mannelijk, vrouwelijk}; an invalid record fails loudly with its qid.
- [x] ISC-4: Two answers on one axis produce a profile score of −2, 0 or +2 (each answer ±1), and an axis with no answers is absent from the profile.
- [x] ISC-5: The match score equals 0.7 × mean over the saint's known axes of `1 − |kid − saint| / 4` plus 0.3 × shared interests / number of the saint's interests, verified against a hand-computed case.
- [x] ISC-6: The gender filter runs before matching: preference "man" returns only male saints, "vrouw" only female, "maakt niet uit" all.
- [x] ISC-7: Saints passed as already chosen never appear in a top-N (each saint once on the board).
- [x] ISC-8: Ties are broken deterministically but not by name or list order, so equal-scoring saints are not systematically favoured.
- [x] ISC-9: The simulation is reproducible: the same seed produces a byte-identical report.
- [x] ISC-10: The simulation report checks and states pass/fail for each plan requirement: no saint above 4% of first choices; ≥60% of the set in some top-3; per gender preference the same two checks against that group's eligible saints; ≥5 saints per interest; saints on both sides of every axis.
- [x] ISC-11: A terminal quiz (`python -m durfheilig.speel`) lets Jelle answer gender preference, 12 questions (2 per axis, randomly drawn from 4) and 2–3 interests, and prints the top-3 with names, match scores and `wat_voor_mens`, plus the top-12.
- [x] ISC-12: `pytest` passes, and runs offline from the box's wheel store.
- [ ] ISC-13: The simulation report checks interest coverage and both-sides-per-axis per gender preference, not only over the whole set (review finding: among the 31 women, "Techniek, bouwen en computers" has 0 saints and "Sport en buiten bewegen" 1).
- [ ] ISC-14: `profiel()` rejects an unknown question id and more than two answers per axis with a clear error, so a kid's axis score stays within −2..+2.
- [ ] ISC-15: Tests fail when a spread threshold comparison is inverted, and when the gender filter or exclusion runs after slicing to n.
- [ ] ISC-16: The data files are found when the package is installed non-editable (Docker image in phase 6).

## Anti-claims

- [x] A1: No saint record in `data/heiligen.json` is modified by any phase 3 code.
- [x] A2: No network access and no LLM call anywhere in phase 3 code.
- [ ] A3: No question answer is flattering on one side only; both answers name something a teenager would be happy to say about themselves (reviewed by Jelle when he plays).

## Test Strategy

| ISC | type | probe |
|---|---|---|
| ISC-1, ISC-2, ISC-3 | bash | `uv run pytest tests/test_data.py` |
| ISC-4 – ISC-8 | bash | `uv run pytest tests/test_scoring.py` |
| ISC-9, ISC-10 | bash | run `python -m durfheilig.simulatie` twice, `cmp` the reports, read the checks table |
| ISC-11 | bash | scripted stdin through `python -m durfheilig.speel` |
| ISC-12 | bash | `uv run pytest` |
| A1 | bash | `git diff --stat data/heiligen.json` is empty |
| A2 | bash | grep for `urllib`, `requests`, `httpx`, `socket` in `src/` |
| A3 | manual | Jelle plays the quiz three times |

## Decisions

- Axis sign convention follows `rubric.md`, not the key name: for `samen_alleen` the − pole is "alleen", + is "samen"; for the other five axes − is the first word in the key.
- Fictional profiles answer each question 50/50 and pick 2–3 interests uniformly. That tests spread, not realism; recognition is tested in the dress rehearsal.
- "First choice" in the simulation is the deterministic rank 1, standing in for the kid's pick among the LLM's top-3.
- Each gender preference gets its own 200 profiles, so "comparable per gender preference" is checked by applying the same two spread thresholds to each group.
- The report shows a noise floor next to the 4% check: the highest share a uniformly random matcher reaches at the same n. At n=200 that floor is already above 4% for "man" (4.5%) and "vrouw" (6.0%), so the check as written cannot pass for those groups by noise alone.
- Finding, not yet acted on: the rubric formula concentrates first choices on a few saints (Paus Leo I 11.5%, Bernadette 15.0% at n=200; about 13% at n=2000). Two causes measured: saints with a single interest get the full interest score whenever a kid picks it, and saints with middling axis scores sit closest to the average profile. Centring each saint's score on its own mean and spread over all possible profiles (a z-score) roughly halves it (6.7% / 8.6% / 4.0% at n=2000). Changing the formula is a rubric change and waits for Jelle.

## Verification

- ISC-1–8, ISC-12: `uv run pytest` 33 passed (tests/test_data.py, tests/test_scoring.py, tests/test_simulatie.py).
- ISC-9: two runs of `python -m durfheilig.simulatie`, `cmp` identical.
- ISC-10: `docs/simulatie/rapport.md` checks table, 8 rows with pass/fail.
- ISC-11: scripted stdin through `python -m durfheilig.speel --seed 1` printed profile, top-3 with `wat_voor_mens`, places 4–12.
- A1: `git status data/` shows only the new `vragen.json`. A2: grep for network imports in `src/` empty.

## Remaining Work

- [ ] [none] Review findings on the question bank (vs2, dl4, av3 tilt toward one side; vs3 and dd4 load on a second axis; two duplicate icons): rewrite after Jelle has played the quiz.

- [ ] [none] Jelle decides on the concentration finding (per-saint centring, and a noise-aware threshold or n=2000) before phase 4 uses the ranking.
- [ ] [none] A3: Jelle plays the quiz three times as different types and judges the questions and top-3.
