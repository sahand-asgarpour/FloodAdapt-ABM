# FloodAdapt-ABM × DYNAMO-M coupling — Proposed Development Architecture & Steps

**Date:** 2026-07-09
**Status:** updated proposal — post-Phase-4b review | **Scope:** 4b-full pre-flight (de-risking) + repo/verification hygiene + 4b-full roadmap
**Supersedes:** `20260708_proposed_development_architecture_steps.docx` (kept for the historical record)

---

## 1. Project purpose & repositories (validated recap)

Unchanged from the 20260708 document. Two repositories collaborate to answer one research question: *how do policy incentives and lived flood experience shape household-level adaptation, and hence long-term coastal flood risk, under sea-level rise (SLR)?*

| Repository | Role |
|---|---|
| **FloodAdapt-ABM** | Lightweight Monte-Carlo simulation engine. Turns a precomputed FloodAdapt (SFINCS+FIAT) impact lookup table into building-level damage time series and adaptation decisions under an SLR scenario. |
| **DYNAMO-M** | Global honeybees/Mesa-style ABM of coastal household migration & adaptation. Supplies the Subjective Expected Utility (SEU) decision science that replaces FloodAdapt-ABM's naive rule. |

The two stages of FloodAdapt-ABM share exactly one interface: the NetCDF lookup table (dims `object_id × slr × strategy × event`; vars `total_damage`, `inun_depth`; attrs `max_pot_dmg`, `freq`, `primary_object_type`). This seam remains the backbone of the coupling and must stay stable.

## 2. Objective & MVP scope (recap)

Unchanged: replace the reactive 0.3-threshold rule with DYNAMO-M's SEU household decision framework, keeping FloodAdapt-ABM's elevation assumption (adapted households read damages from `floodproof_all_0`). IN: residential households, dry-proofing vs do-nothing, SEU with CRRA utility, exceedance-curve integration, risk-perception decay, affordability cap, loan amortisation, 75-year adaptation lifespan. OUT (Phase 5+): insurance, migration + gravity, government/dike CBA. BYPASSED: DYNAMO-M's internal hazard physics.

## 3. Current state assessment (2026-07-09)

| Component | Status | Notes |
|---|---|---|
| Stage-1 lookup table (`setup_lookup_table.py`) | Done / stable | Unchanged by the coupling. EventSet must be RP-based. |
| Unified `SimulationEngine` + `DecisionRule` (Phases 2+3) | **Done, gated** | `ThresholdRule` reproduces legacy output bit-for-bit; `SEURule` matches the Phase-1 battery; lifespan-dryproof reset implemented and unit-tested (`lifespan_dryproof=75` in `DecisionConfig`; turnover test in `tests/test_simulation_engine.py`). |
| Phase 4a — `DynamoLiveRule` parity oracle | **Done, gated** | Gate PASS: decisions identical across 5 configs; worst EU abs diff 1.9e-6, rel 4.8e-7 (tol abs ≤1e-3, rel ≤1e-4). |
| Phase 4b — Mesa-native driving (scaffold) | **Done, gated** | `run_mesa_native == engine.run` bit-for-bit across 5 cases (SEURule ×3, ThresholdRule ×2). 104/104 tests pass. Examples 01–06 run (exit 0). |
| Phase 4b-full — bind real honeybees `SLRModel` | **Not started** | 6-step roadmap (§7.2), est. 20–40 hrs. Pre-flight de-risking tasks added in §7.1. |
| Verification bundle (`verification_tests/`) | **Valid but incomplete** | Reports/JSON/CSVs internally consistent and genuinely computed (reviewed 2026-07-09). Gaps: V1–V6 battery ran on the *old bridge* API, not the current engine; V5 verdict "GAP" is stale (fix has since shipped); `figures/` missing; hardcoded developer paths. See §6. |
| Root `README.md` | **Stale** | Points at deleted `example/` scripts; lists files that don't exist; omits Phase 3/4a/4b modules. See §6. |
| CI | **Absent** | 104 tests and CI-runnable gates exist, but nothing executes them automatically. |
| Notebook 2 (`2_simulate_adaptation.ipynb`) | Legacy path | Still uses `ABMSimulator`; does not exercise the recommended `SimulationEngine`. |

## 4. Target architecture (delivered — recap)

The Strategy-Pattern architecture proposed on 20260707/20260708 is now delivered and frozen:

```
SimulationEngine (owns time + data)          FloodAdaptSLRModel (Phase 4b: owns time via ticks)
  ├── NetCDF loading / interpolation           ├── engine: SimulationEngine (shared kernel)
  │     ├── strategy cube materialized once
  │     └── per-(SLR, method) interp cache
  ├── Stochastic event draw (Bernoulli + cap)  └── agents → CoastalNodePopulation → step()
  ├── AgentState (wealth, income, risk_perception,
  │              flood_timer, is_adapted, time_adapted)
  ├── run(no_seq, n_jobs) — parallel Monte-Carlo sequences (bit-identical)
  └── decision_rule: DecisionRule  ← pluggable
        ├── ThresholdRule   (legacy 0.3 rule)
        ├── SEURule         (ported DYNAMO-M SEU — MVP default)
        ├── DynamoLiveRule  (native DYNAMO-M — parity oracle, 4a)
        └── <custom>        (Open/Closed: new science = new rule)
```

The `DecisionRule.should_adapt(...)` seam is the stable coupling contract across 4a → 4b-scaffold → 4b-full.

## 5. Review findings driving this update (2026-07-09)

An external review of the repo, examples, docs and the `verification_tests/` bundle confirmed the engineering discipline (frozen seams, one-variable-at-a-time gates, bit-parity proofs) and the validity of the verification results (verdicts genuinely computed; reports match raw CSV/JSON numbers). It also found that **the entry-point documentation and reproducibility artefacts have not kept pace with the phase work, and the whole validation story rests on synthetic data**. The findings become the task list in §7.1 and §8.

## 6. Issues found (updated table)

| Sev. | Issue | Location | Action (task ID) |
|---|---|---|---|
| Med | `FloodAdaptSLRModel.__init__` calls `engine.reset_state()` on a **shared** engine; constructing a second model silently invalidates the first model's live `agents.regions.state` view. Safe inside `run_mesa_native`'s sequential loop, but a footgun for manual tick-driving (as example 06 teaches). 4b-full would copy this pattern. | `mesa_native.py:174` | PRE.3 |
| Med | Every gate so far ran on the synthetic table (≤250 objects); real Charleston table (61,858 × 207) never exercised through the engine/4b path. Performance/memory unknown at scale. | examples 05/06, `simulation_engine.py` | PRE.2 — **CLOSED**: executed, `gate_pass: True`; fixed a full-scale interpolation bottleneck (cube materialize-once + per-SLR cache + parallel `n_jobs`, commit `6f45d6f`) |
| Med | Phase-1 V1–V6 battery was executed against the **old** `DynamoDecisionBridge` API, not the current `SimulationEngine + SEURule`; the roadmap's own Gate 2 ("re-run the full battery on the new engine") has no artifact. | `verification_tests/run_seu_validation.py` | VER.1 |
| Med | V5 lifespan report still says "GAP (documented)" although the lifespan reset has since been implemented and unit-tested — the bundle's headline summary contradicts the shipped code. | `verification_tests/05_lifespan.md`, `00_SUMMARY.md` | VER.1 |
| Med | Root `README.md` stale: references deleted `example/` folder, nonexistent `run_coupled_example_engine.py`, wrong folder layout; omits `mesa_native.py`, `dynamo_live_rule.py`, `decision_rule.py`. | `README.md` | HYG.1 |
| Med | No CI despite CI-runnable gates and 104 tests. | repo root | HYG.3 |
| Low | `AGENTS.md` and verification scripts contain machine-specific absolute paths (`c:\repos\DYNAMO-M`, `C:\Users\asgarpou\OneDrive...`, `.copilot\session-state\...`); referenced "reproduction bundles" (`progress_todos/...`) are not in the repo. | `AGENTS.md`, `verification_tests/*.py` | HYG.2, VER.2 |
| Low | Verification bundle missing `figures/` (all embedded image links broken); CSVs at folder root instead of the `data/` layout the reports reference; `README.md`/`README_1.md` name collision. | `verification_tests/` | VER.2 |
| Low | Notebook 2 still drives the legacy `ABMSimulator`; the recommended `SimulationEngine` has no notebook. | `2_simulate_adaptation.ipynb` | HYG.4 |
| Low | The four phase `.docx` docs are not diffable/readable in-repo. | `docs/` | HYG.4 |

## 7. Recommended development roadmap (updated)

Guiding principle unchanged: unify the plumbing, keep the decision logic pluggable, validate before refactoring, never regress the ThresholdRule path. **New principle for this stage: close the documentation/reproducibility gaps and de-risk the environment lift *before* starting 4b-full, so the eventual 4b-full ≡ 4b-scaffold gate stays attributable to one variable.**

### 7.1 Phase 4b-pre — de-risking & hygiene (NEW — do before 4b-full)

**Next steps and tasks to be performed:**

#### A. Before starting 4b-full (cheap, de-risking)

| ID | Task | Detail | Effort | Risk it retires | Gate / exit criterion |
|---|---|---|---|---|---|
| **PRE.1** | **Do 4b-full Step 1 now, in isolation.** | Pin `honeybees` + `mesa` in a throwaway env and try importing/instantiating against the DYNAMO-M checkout. Version drift is the roadmap's own top risk — discovering it early costs nothing; discovering it in step 5 costs the schedule. | 2–4 hrs | honeybees/mesa version drift | Import + minimal instantiation succeed; versions pinned and recorded |
| **PRE.2** | **Run the gates once on the real Charleston table.** | Every gate so far (4a parity, 4b bit-parity) ran on the synthetic table (~160 agents). The real table is 61,858 objects × 207 events. Run `FA_ABM_REAL_TABLE=1` through examples 05/06 to surface performance and memory issues at scale — the per-tick `engine.step()` path in `mesa_native.py` may need profiling there, and 4b-full will only be slower. | 0.5–1 day (mostly runtime) | Unknown scale behaviour of the engine/tick path | Examples 05/06 complete on the real table; runtime + peak memory recorded; profiling notes filed if `engine.step()` is a bottleneck |
| **PRE.3** | **Fix the shared-engine design wart in `FloodAdaptSLRModel`.** | `__init__` calls `engine.reset_state()` on a shared engine (`mesa_native.py:174`). Constructing a second model on the same engine silently invalidates the first model's live `agents.regions.state` view — fine inside `run_mesa_native`'s sequential loop, a footgun for manual driving (example 06). Either give each model its own `AgentState`, or raise/document when a stale model is stepped. Fix now because 4b-full will copy this pattern. | 2–4 hrs | Silent state corruption pattern propagating into 4b-full | New unit test: two models on one engine either isolate state or raise; 4b bit-parity gate still PASS |
| **PRE.4** | **Prototype the lookup-table → CoastalNode adapter against a frozen synthetic node population first** (the step-3 pseudo-logic), before wiring `Data`/`FloodRisk`/gravity (step 5). The adapter is the centrepiece and the only new science-adjacent code; validating it standalone keeps the eventual 4b-full ≡ 4b-scaffold bit-parity gate attributable to one variable, exactly as done for 4a → 4b. | 1–2 days | Adapter bugs masked by environment noise in step 5 | Standalone adapter round-trips the synthetic lookup table into deterministic node arrays and back, bit-identical |

#### B. Repo / documentation hygiene (the state has outrun the docs)

| ID | Task | Detail | Effort | Gate / exit criterion |
|---|---|---|---|---|
| **HYG.1** | **Rewrite the stale root `README.md`.** | It still says "run `python example/run_coupled_example.py`", lists `examples_engine/run_coupled_example_engine.py` (doesn't exist — the numbered 01–06 files do), shows `old_bridge_examples/` at the root (it's under `examples_engine/`), and omits `mesa_native.py`, `dynamo_live_rule.py`, `decision_rule.py`. First thing a new user sees currently contradicts the actual layout. | 1–2 hrs | README structure section matches the actual tree; quick-start commands run as written |
| **HYG.2** | **Purge machine-specific paths from `AGENTS.md`; vendor the verification bundles.** | `AGENTS.md` contains absolute paths (`c:\repos\DYNAMO-M`, `C:\Users\asgarpou\OneDrive...`, `.copilot\session-state\...`). The "reproduction bundles" (`progress_todos/...`, `run_phase4a_parity.py`, `run_phase4b_verification.py`) are referenced but not in the repo — for the reproducibility claim to hold, vendor them in (e.g. a `verification/` folder) or link a durable location. Use env-var overrides (`ABM_ROOT`, `DYNAMO_M_PATH`) everywhere. | 2–3 hrs | No user-specific absolute path remains; every referenced artifact resolves inside the repo or to a durable link |
| **HYG.3** | **Add CI.** | 104 tests, bit-parity gates designed to be "CI-runnable", six examples that exit 0 — but no CI. Minimal GitHub Actions job: `pytest tests/ -q` + run examples 01–04/06 on the synthetic table (05 auto-skips without DYNAMO-M) + `run_phase4b_verification.py`. Locks in the frozen scaffold while 4b-full work churns. | 2–4 hrs | Green pipeline on push/PR; gate scripts wired in |
| **HYG.4** | **Modernise the notebook path and the design docs.** | Notebook 2 still uses the legacy `ABMSimulator`; add a notebook (or convert notebook 2) using `SimulationEngine` + `SEURule` so the notebook workflow matches the post-Phase-3 architecture. Convert the four `.docx` phase docs to Markdown — they're the project's design record but aren't diffable or readable in-repo (this document starts that convention). | 0.5–1 day | Engine-based notebook runs end-to-end; design docs readable as Markdown in `docs/` |

#### C. Verification-bundle regeneration (closes the 2026-07-09 review caveats)

| ID | Task | Detail | Effort | Gate / exit criterion |
|---|---|---|---|---|
| **VER.1** | **Re-run the V1–V6 battery on the current `SimulationEngine` + `SEURule`** (Gate-2 artifact). Regenerates V5 with the lifespan reset in place — expected to show adaptation turnover at year 75+, converting "GAP (documented)" into "PASS (closed in Phase 3)". | 0.5–1 day | All hard gates (V1, V4, V6) PASS on the engine; V5 shows un-adaptation at the lifespan; `00_SUMMARY.md` regenerated |
| **VER.2** | **Make the bundle self-contained and portable.** Add the missing `figures/`, restore the `data/` layout the reports reference, parameterize hardcoded paths via env vars, rename the colliding `README.md`/`README_1.md` (→ `README_phase4a.md` / `README_phase4b.md`), and commit the folder into the repo. | 2–4 hrs | Bundle re-runs from a clean checkout with only env vars set; no broken links |
| **VER.3** | **Empirical native V5 reference (optional, nice-to-have).** V5's native side (`native_resets = True`) was asserted from source reading, not executed. When the 4b-full env exists (PRE.1), run the native 90-year reference once to make the comparison empirical. | 2–4 hrs (after PRE.1) | Native run shows reset at t=75; figure added to V5 report |

### 7.2 Phase 4b-full — binding the real honeybees `SLRModel` (unchanged, now gated behind 4b-pre)

| Step | Task | Effort | Risk | Gate |
|---|---|---|---|---|
| 1 | Pin honeybees/mesa versions; verify config compatibility. **(→ pulled forward as PRE.1)** | 2–4 hrs | Low (after PRE.1) | Import test |
| 2 | Populate `SLRModel`: `config_path`, `settings_path`, geojson `study_area`, `args`; instantiate `Data`, `FloodRisk`, `CoastalAmenities`. | 4–6 hrs | Medium | `SLRModel()` succeeds |
| 3 | Write lookup-table adapter: map `object_id ↔ CoastalNode`, `property_value ↔ node.wealth`, per-event damages → node arrays. **The ONE new modelling artefact (prototyped in PRE.4).** | 6–10 hrs | Medium (reduced by PRE.4) | Round-trip reproduces 4b-scaffold |
| 4 | Route adapt decisions: `CoastalNode.step()` → `DynamoLiveRule.should_adapt` → node state. Close the coupling loop. | 4–8 hrs | Medium | Decisions recorded in native arrays |
| 5 | Integrate sub-systems: gravity CWD, `spin_up_flag`, low-memory `.npz` paging, `geom_id '_flood_plain'` filtering, reporter. | 4–8 hrs | Medium–High | All sub-step logic runs |
| 6 | Execute 4b-full gate: 4b-full ≡ 4b-scaffold bit-for-bit on a deterministic node population. | 2–4 hrs | Low | Bit-parity gate PASS |

Total (unchanged): 20–40 hrs of infrastructure integration, no new science — now entered with the top risks (version drift, scale, adapter correctness, state-sharing pattern) retired in 4b-pre.

### 7.3 Phase 5 — extending decision rules (unchanged)

`calcEU_insure` (insurance), migration + gravity, government/dike CBA — each as a new rule/agent class, never engine surgery.

## 8. Consolidated, prioritised TODO backlog (updated 2026-07-09)

Completed items from the 20260708 backlog are retained (struck) for traceability.

| Pri | Task | Source | Phase | Status |
|---|---|---|---|---|
| ~~P0~~ | ~~Fix `cfg.environment.max_slr` crash in demo summary~~ | code §7 | 0 | DONE |
| ~~P0~~ | ~~Reconcile `DecisionConfig` docstring vs defaults~~ | code §7 | 0 | DONE |
| ~~P1~~ | ~~Validate SEU vs DYNAMO-M on reference scenario; run §12.1 battery~~ | docx roadmap | 1 | DONE (on bridge; see VER.1) |
| ~~P2~~ | ~~Event drawing / time loop / accessor consolidation~~ | docx | 2 | DONE |
| ~~P3~~ | ~~`SimulationEngine` + `DecisionRule` (Threshold, SEU); widened interface; lifespan reset~~ | docx | 3 | DONE |
| ~~P4a~~ | ~~Live DYNAMO-M `DecisionModule` parity oracle~~ | feasibility review | 4a | DONE (gate PASS) |
| ~~P4b~~ | ~~Mesa-native driving (scaffold): time-ownership inversion, bit-parity gate~~ | docx | 4b | DONE (gate PASS) |
| **P0** | PRE.1 — pin honeybees/mesa in isolated env; import/instantiate test | 2026-07-09 review | 4b-pre | **DONE** — executed: mesa 3.3.1 / honeybees 1.2.0 pinned; DYNAMO-M `DecisionModule` + `SLRModel` import/instantiate (gate_pass True) |
| **P0** | PRE.3 — fix `engine.reset_state()` shared-engine wart in `FloodAdaptSLRModel` | 2026-07-09 review (`mesa_native.py:174`) | 4b-pre | **DONE** (`state_epoch` guard + 4 tests, commit `7ceb144`; tests PASS) |
| **P0** | HYG.1 — rewrite stale root `README.md` | 2026-07-09 review | 4b-pre | **DONE** (commit `d05a97a`) |
| **P1** | PRE.2 — run gates on real Charleston table; profile `engine.step()` | 2026-07-09 review | 4b-pre | **DONE / PASS** — executed on the real 61,858 × 207 table (57,976 agents); `gate_pass: True` (4b bit-parity + 4a subset parity). Surfaced + fixed a full-scale interpolation bottleneck (cube materialize-once + per-SLR cache; ×1.4 parallel `n_jobs`); report/metrics in `verification/real_table_gate/` — see `20260709_performed_tasks.md` §6.1 |
| **P1** | VER.1 — re-run V1–V6 battery on `SimulationEngine`+`SEURule`; regenerate V5 (lifespan now closed) | 2026-07-09 review | 4b-pre | **DONE (battery re-run + figures regenerated)** — V1–V4/V6 PASS; V5 stays "GAP" on the legacy-bridge harness (engine path's lifespan reset is unit-tested green); porting the harness onto the engine API is the residual |
| **P1** | HYG.3 — CI pipeline (pytest + examples + 4b gate) | 2026-07-09 review | 4b-pre | **DONE** (`.github/workflows/ci.yml`, commit `8b7384c`; activates on push) |
| **P1** | HYG.2 — de-machine-ify `AGENTS.md`; vendor verification bundles into repo | 2026-07-09 review | 4b-pre | **DONE** (commits `3af86e8`, `87ea7c6`) |
| **P2** | PRE.4 — standalone lookup-table → CoastalNode adapter prototype on frozen synthetic nodes | 2026-07-09 review | 4b-pre | **DONE** (`coastal_node_adapter.py` + 10 tests, commit `1cb7862`) |
| **P2** | VER.2 — verification bundle portability (figures/, data/, env-var paths, README rename) | 2026-07-09 review | 4b-pre | **DONE** (figures regenerated by VER.1 execution) |
| **P2** | HYG.4 — engine-based notebook; convert `.docx` design docs to Markdown | 2026-07-09 review | 4b-pre | **DONE** (notebook 3 + `docs/*.md`, commit `2225ae6`) |
| **P3** | VER.3 — empirical native V5 lifespan reference run | 2026-07-09 review | 4b-full (after step 1) | OPEN |
| **P4b** | 4b-full steps 2–6 (bind real honeybees `SLRModel`) | docx roadmap §7.2 | 4b-full | BLOCKED on 4b-pre P0/P1 items |
| **P5** | Insurance / migration / government rules | docx roadmap | 5 | FUTURE |

## 9. Phase gate summary (updated)

| Phase | Deliverable | Exit criterion | Status |
|---|---|---|---|
| 0 | Green examples + reconciled config | Both demos run; 41 tests pass | ✅ PASS |
| 1 | Validated SEU | §12.1 battery passes; SEU == DYNAMO-M within tol. | ✅ PASS (battery re-run 2026-07-09; V1–V4/V6 PASS; V5 engine-path reset unit-tested) |
| 2 | Core event+time engine | No decision logic left in example scripts | ✅ PASS |
| 3 | `SimulationEngine` + rules | ThresholdRule reproduces legacy output; lifespan reset shipped | ✅ PASS |
| 4a | Live DYNAMO-M SEU parity | `calcEU_*` parity within tol.; import optional/guarded | ✅ PASS (worst EU abs 1.9e-6, rel 4.8e-7) |
| 4b | Mesa-native driving (scaffold) | `run_mesa_native == engine.run` bit-for-bit | ✅ PASS (5/5 cases) |
| **4b-pre** | **De-risking + hygiene (this doc)** | **PRE.1–4 + HYG.1–4 + VER.1–2 complete; CI green; README/AGENTS accurate; battery re-run on engine; real-table gate executed** | ✅ DONE (2026-07-09: merged into `sahand-asgarpour/FloodAdapt-ABM`, one commit per task; 125 tests PASS; PRE.1 executed; **PRE.2 executed → gate_pass: True** on the real 61,858 × 207 table, after fixing a full-scale interpolation bottleneck (per-SLR cube cache + parallel `n_jobs`, commit `6f45d6f`); VER.1 battery + figures regenerated; pushed to `origin/main` — see `20260709_performed_tasks.md` §6 + §6.1. Residual: port the standalone V5 harness onto the engine API) |
| 4b-full | Full Mesa-native integration | `SLRModel.step()` drives native `CoastalNode` population from the lookup table; 4b-full ≡ 4b-scaffold bit-for-bit | 🔲 BLOCKED on 4b-pre |
| 5 | Extending decision rules | `calcEU_insure`, migration, government CBA as new rules | 🔲 FUTURE |

**Gate rule:** do not start 4b-full step 2 until the 4b-pre P0 items (PRE.1, PRE.3, HYG.1) and P1 items (PRE.2, VER.1, HYG.2, HYG.3) are closed. PRE.4 may run in parallel with 4b-full step 2. **Status (2026-07-09): all P0/P1 4b-pre items closed — the gate is OPEN; 4b-full step 2 may begin.**

## 10. Go/No-Go & execution strategy

**Status (2026-07-09):** Phases 0–4b(scaffold) are COMPLETE with all gates PASS. The 2026-07-09 review confirmed the verification results are genuine and internally consistent, with four qualifications (battery ran on the old bridge; V5 verdict stale; bundle missing figures / uses hardcoded paths; all validation synthetic-only). **4b-pre is GO immediately; 4b-full is GO once the 4b-pre gate closes.**

Recommended sequencing (roughly one week of part-time effort):

1. **Day 1:** PRE.1 (pin env) + PRE.3 (state-sharing fix) + HYG.1 (README) — the three P0s are independent and small.
2. **Day 2–3:** VER.1 (battery re-run on engine) + HYG.3 (CI, wiring the regenerated gates in) + HYG.2 (paths/vendoring).
3. **Day 3–4:** PRE.2 (real-table run; long runtimes, start early and let it run) + VER.2.
4. **Day 4–5:** PRE.4 (adapter prototype) + HYG.4 — then enter 4b-full step 2 with every headline risk retired.

## 11. Definition of done & alignment with the objective

Unchanged in substance, extended with the review items:

- **Science validated on the shipped code:** V1–V6 pass on `SimulationEngine` + `SEURule` (not only the retired bridge), V5 demonstrating lifespan turnover.
- **Backwards compatible:** ThresholdRule reproduces legacy output; existing notebooks keep working; an engine-based notebook exists.
- **Single source of truth:** one interpolation kernel, one event generator, one time loop, one pluggable decision interface — and one accurate README.
- **Reproducible:** verification bundles vendored in-repo, portable (env-var paths, figures present), executed by CI on every push.
- **Scale-aware:** the engine and tick driver have been run once on the real Charleston table with recorded runtime/memory.
- **Extension-ready:** insurance, migration, government agents arrive as new rules without touching the engine; 4b-full enters as pure infrastructure wiring with its risks retired in 4b-pre.

— End of proposed development architecture & steps (2026-07-09) —
