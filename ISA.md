---
phase: climbing
progress: 26/28
principal_stated_goal: "I merged #6, please start phase 4."
---

# Durf heilig te zijn

## Problem

Eight to fifteen people (thirteen-year-olds plus leaders) each need to be matched to a saint they recognize themselves in, from a curated set of 89, before the game afternoon of Saturday 11 October 2026. The design lives in `docs/design/plan-heiligen-welkomstspel.md` and `docs/design/rubric.md`. Phase 3 of that plan is the deterministic core: the question bank, the scoring and matching, and a simulation that shows the matching spreads over the set instead of handing everyone the same few saints.

## Vision

Jelle answers twelve either-or questions as three different kinds of teenager, and each time the top three reads like that teenager: the quiet reader gets Thérèse or Edith Stein, the joker who organizes everything gets Filippus Neri or Don Bosco, never the same three saints for everyone. The simulation report tells him in one screen whether the set is healthy and which saints never come up, so he knows which records to look at before Thursday.

## Out of Scope

- The game screens and voting (phase 5), deployment (phase 6); `/tv` comes with phase 5.
- Changing saint records; the simulation reports on them, Jelle edits them through git.

## Goal

Phase 4 of the plan (the quiz app, LLM layer and game state, on top of the phase 3 scoring):

Phase 3, done:  a question bank of 24 either-or questions (four per axis) plus the interest question, the deterministic scoring and matching exactly as `rubric.md` specifies, and a reproducible simulation of 200 fictional teen profiles checked against the plan's requirements, plus a way for Jelle to play the quiz himself.

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
- [x] ISC-13: The simulation report checks interest coverage and both-sides-per-axis per gender preference, not only over the whole set (review finding: among the 31 women, "Techniek, bouwen en computers" has 0 saints and "Sport en buiten bewegen" 1).
- [x] ISC-14: `profiel()` rejects an unknown question id and more than two answers per axis with a clear error, so a kid's axis score stays within −2..+2.
- [x] ISC-15: Tests fail when a spread threshold comparison is inverted, and when the gender filter or exclusion runs after slicing to n.
- [x] ISC-16: The data directory is configurable through `DURFHEILIG_DATA`, so a non-editable install (the phase 6 Docker image) can point at it; tested by loading all data from a copied directory.
- [x] ISC-17: Ranking uses each saint's relative score (z-score of the match score against that saint's own mean and spread over every answer pattern and every 2- or 3-interest pick); over that reference distribution every saint's relative score has mean 0 and standard deviation 1.
- [ ] ISC-18: Every gender preference has at least 5 saints per interest. After the claude.ai supplement (8 new saints, 4 returned from the dropped list, 7 interests added, merged by `pipeline/merge_aanvulling.py`) only women with "Sport en buiten bewegen" fall short: 4 of 5.
- [x] ISC-19: Both LLM calls validate their JSON against the candidate list (3 follow-up questions; exactly 3 distinct chosen saints, none rejected, none outside the candidates), retry once, then fall back to deterministic output (follow-up questions from the question bank, top-3 from the ranking with a standard explanation), so a failing API never stops the game. Tested with a fake client for valid, malformed, wrong-saint, duplicate, short and network-error answers.
- [x] ISC-20: The prompt data holds only profile, interests, the kid's own text and the candidates' records, never a username, nickname or name; the kid's text sits in its own JSON field the prompt calls data, not instructions; the Gemini key travels in a header, never in the URL or an error message.
- [x] ISC-21: Every route returns 401 without `Remote-User`; `/beheer` also requires group `admins` (compared exactly, not as a substring); the app reads no other identity header.
- [x] ISC-22: A kid can close the app at any step and resume at that step with earlier answers intact.
- [x] ISC-23: A saint confirmed by one player never appears in another player's top-3, enforced where the match is stored, not only in the ranking.
- [x] ISC-24: The "Mijn heilige" page shows a player's own three saints with explanation and chosen saint, and nobody else's.
- [x] ISC-25: A leader overview shows who has finished and which explanations are flagged, to leaders only.
- [x] ISC-26: Leaders (group `durfheilig-leiding` or `admins`) can download everything the app stores as JSON and wipe the whole group behind a typed confirmation; after a wipe the kids' answers are in neither the database file nor its write-ahead log; a request started from another site or with a wrong word wipes nothing; kids get 403 on both routes.
- [x] ISC-27: The Dockerfile installs production dependencies from `uv.lock`, runs as uid 10001, publishes no port, reads the Gemini key from an env file only, answers its health check, and refuses to build when the lock points at the box's offline `/opt/wheels`.
- [ ] ISC-28: A kid logged in through Authelia reaches the quiz at `https://durfheiligtezijn.hopsakee.top`, gets 403 on `/beheer`, and a leader gets in. Deployed files are staged in the server repo PR; needs Jelle's host steps (below).

## Anti-claims

- [x] A1: No saint record in `data/heiligen.json` is modified by any phase 3 code.
- [x] A2: No network access and no LLM call anywhere in phase 3 code (as of the phase 3 merge; `llm.py` is phase 4).
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
- Finding, acted on 2026-10-07 after Jelle's "Yes, do both": the rubric formula concentrates first choices on a few saints (Paus Leo I 11.5%, Bernadette 15.0% at n=200; about 13% at n=2000). Two causes measured: saints with a single interest get the full interest score whenever a kid picks it, and saints with middling axis scores sit closest to the average profile. Centring each saint's score on its own mean and spread over all possible profiles (a z-score) roughly halves it (6.7% / 8.6% / 4.0% at n=2000). Jelle approved; `rubric.md` § Matching records it. The match score stays the rubric's 0.7/0.3 total; only the ranking is relative.

- Follow-up answers do not enter `profiel()` (its cap of 2 answers per axis stays). The LLM's questions name which candidates rise per answer (`stijgt_bij_min/plus`); the final LLM call sees the answers, and the fallback orders the top-12 by number of rises, then by relative score. Bank-based fallback questions use the 2 undrawn questions per axis, on the three axes where the top-12 differ most.
- Only `speler`, `invulling` and `match` exist so far; `groep`, `ronde`, `spelronde`, `bord` and `stem` come with phase 5 (the September/June comparison needs `ronde`, phase 6).
- Uniqueness of the chosen saint is a database constraint; a lost race quietly yields a fresh top-3 rather than an error.
- `/beheer` checks `Remote-Groups` for `admins` as defence in depth next to the Authelia rule; no other identity header is read.
- Images come from `data/afbeeldingen/<bestand>` when present, otherwise from Wikimedia Commons by filename. The box cannot fetch them, so local copies are a host-side step.

- Local testing uses `python -m durfheilig.dev`: an ASGI layer that turns a chosen cookie into `Remote-User`/`Remote-Groups`, bound to 127.0.0.1. The production entry and the Docker image never start or import it (tested).

## Verification

- ISC-1–8, ISC-12: `uv run pytest` 33 passed (tests/test_data.py, tests/test_scoring.py, tests/test_simulatie.py).
- ISC-9: two runs of `python -m durfheilig.simulatie`, `cmp` identical.
- ISC-10: `docs/simulatie/rapport.md` checks table, 12 rows (4 checks × 3 gender preferences) with pass/fail.
- ISC-11: scripted stdin through `python -m durfheilig.speel --seed 1` printed profile, top-3 with `wat_voor_mens`, places 4–12.
- ISC-13–17: `uv run pytest` 47 passed. Mutants each fail at least one test: inverted 4% check, inverted 60% check, filter after slice, interest coverage counted over all groups, both-sides check disabled, answer validation removed. Second independent review recomputed the z-score reference by brute force for all 77 saints (max error 1.1e-16).
- A1: `git status data/` shows only the new `vragen.json`. A2: grep for network imports in `src/` empty.

## Not yet specified

- (resolved in phase 4, see Decisions) How the 3 LLM follow-up questions change the ranking.

## Remaining Work

- [ ] [none] Phase 6: `DATA_DIR` in tests and `REPO` (default report path) still resolve from the source tree; fine for development, not for tests inside a non-editable image.

- [x] [none] Review findings on the question bank: dd4, av3, dl4, vs2 and vs3 rewritten (dd4, vs2 and vs3 twice, after the second review); all 58 icons unique (tested).

- [ ] [none] The 4% first-choice check stays above its noise floor at n=200 (4.5% man, 6.0% vrouw). After centring, n=2000 gives 6.7% / 8.6% / 4.0% against floors of 3.2% / 4.2% / 1.9%. Whether to keep 4% literally or make it relative to group size is Jelle's call.
- [ ] [none] A3: Jelle plays the quiz three times as different types and judges the questions and top-3.
- [ ] [none] Gemini prompts are untested against the real model (no key in the box); the key and model name go in as secrets, then Jelle and family run the quiz locally.
- [ ] [none] Images are not local yet (see Decisions); the plan wants resized local copies with maker and licence.
- [ ] [none] Leaders splitting the reading of explanations (and not voting in the round of a player whose explanation they read) is not built; `/beheer` only lists progress and flags.
- [ ] [none] The lock covers Linux only (no macOS `apsw` build in the box's wheel store); on the Mac add `sys_platform == 'darwin'` back under `[tool.uv] environments` and run `uv lock` once.
- [ ] [none] The 12 saints added from the supplement are claude.ai output, read by me only for structure, validation and sensitive themes; Jelle's review of their texts (Gianna Beretta Molla's story is about abortion and a mother's death, Germaine Cousin's about abuse) is still open. The 77 older records have no `afbeelding.soort`; the new ones carry `heilige`.
- [ ] [none] `uv.lock` in the repo was made in the offline box and points at `/opt/wheels`. Jelle regenerates it on the Mac (`uv lock`, against PyPI); until it is merged the server build refuses.
- [ ] [none] Host steps for the first deploy: DNS record at OVH, `GEMINI_API_KEY` and `GEMINI_MODEL` in the laptop `.env`, groups and accounts in `users_database.yml`, then a full `server-deploy.sh` (Authelia needs a restart for the new rules).
- [ ] [none] No backup job covers `/db/spel.db`; leaders download `/beheer/export` before wiping. Every container on the `hup` network can reach the app and forge `Remote-User` (same as bg3 and jonkies-tody); a per-app network would close it.
- [ ] [none] The September/June comparison screen is not built.
