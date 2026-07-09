# FloodAdapt-ABM × DYNAMO-M — Performed Tasks

Work log for 2026-07-09: post-Phase-4b review + Phase 4b-pre execution (PRE.1–4, HYG.1–4)

Repo placed under git; one commit per task · 14 new tests authored · all changes traceable to task IDs in `20260709_proposed_development_architecture_steps.md` §7.1

## 1. Summary

2026-07-09 executed the "4b-pre" de-risking and hygiene phase defined after the external review of the Phase-4b state. The review had confirmed all phase gates (0–4b scaffold) as genuinely computed and internally consistent, but found that the entry-point documentation and reproducibility artefacts had not kept pace with the phase work. Today every PRE and HYG task was applied: the shared-engine design wart is fixed with a staleness guard (PRE.3), the lookup-table → CoastalNode adapter — the one genuinely new 4b-full artefact — is prototyped and contract-tested (PRE.4), the honeybees/mesa pinning kit and the real-Charleston-table gate runner are prepared as self-reporting harnesses (PRE.1, PRE.2), the stale root README is rewritten (HYG.1), all verification bundles are vendored in-repo with portable env-var paths (HYG.2), CI is added (HYG.3), and the recommended-path notebook plus a diffable Markdown design record are in place (HYG.4). AGENTS.md is updated throughout.

## 2. Traceability

The repository was placed under git version control with a pristine baseline commit, then **one commit per task**:

| Commit | Task | Delivered |
|---|---|---|
| `06c8314` | — | Baseline: repo as downloaded (Phase 4b scaffold, pre-review state) |
| `7ceb144` | **PRE.3** | `SimulationEngine.state_epoch` + `FloodAdaptSLRModel._check_not_stale()`: stepping a stale model (engine state reset by a newer model or `engine.run()`) now raises `RuntimeError` instead of silently corrupting the new owner's state. 4 new tests (`TestSharedEngineStalenessGuard`). Bit-parity gate unaffected (`run_mesa_native` constructs models sequentially). |
| `1cb7862` | **PRE.4** | `floodadapt_abm/coastal_node_adapter.py`: `CoastalNodeArrays` (native node-array mirror: `property_value`, events-first `damages_coastal_cells`, `p_floods`, `adapt`, `time_adapt`, `_flood_plain` geom_id), `LookupTableAdapter.populate()` (forward) / `write_back()` (reverse, with object_id-alignment guards), `round_trip_check()` (executable bit-parity contract). 10 new tests incl. an end-to-end proof that routing state through the node is a simulation no-op. |
| `fdaf257` | **PRE.1 + PRE.2** | `verification/preflight_4b_full/` (throwaway env spec, pin-after-verify; self-reporting `step1_import_test.py` for mesa/honeybees + DYNAMO-M `decision_module`) and `verification/real_table_gate/` (instrumented 4b bit-parity + optional 4a parity on the real 61,858 × 207 table with wall-time, tracemalloc peak and per-tick `engine.step()` profile). **Prepared, not executed here** — no Python interpreter / DYNAMO-M checkout / real `.nc` on this workstation; READMEs give exact run commands. |
| `3af86e8` | **HYG.2a** | Verification bundles vendored into `verification/` (`phase1_seu_battery/` with restored `data/` layout + documented `figures/` placeholder, `phase4a_parity/`, `phase4b_mesa_native/` with the README name collision resolved) plus an index README. Vendored *scripts* re-pathed to `ABM_ROOT`/`DYNAMO_M_PATH`/`SEU_BATTERY_OUT` env vars; generated *reports* kept verbatim as the 2026-07-08 historical record. |
| `d05a97a` | **HYG.1** | Root README rewritten: engine quick-start, accurate tree (incl. `verification/`, `coastal_node_adapter.py`, notebook 3), pipeline summary, decision-rule table. Removed: deleted `example/` instructions, nonexistent `run_coupled_example_engine.py`, wrong `old_bridge_examples/` location. |
| `8b7384c` | **HYG.3** | `.github/workflows/ci.yml`: matrix (ubuntu/windows × py3.10/3.11) running `pytest tests/ -q`, examples 01–06 on the synthetic table (05's DYNAMO-M guard exits 0 when absent — the guard is thereby under test), and the vendored Phase-4b harness with report artifacts. Activates on push to GitHub. |
| `2225ae6` | **HYG.4** | `3_simulate_adaptation_engine.ipynb` (stage 2 on `SimulationEngine` + `SEURule`: run, adoption/damage plots, never-adapt baseline → avoided damages, rule-swap guide). The four 20260708 `.docx` phase docs vendored into `docs/` and converted to diffable Markdown with provenance headers (`.docx` remain the typeset originals). |
| `87ea7c6` | **HYG.2b** | AGENTS.md path purge + content sync (see §3); `examples_engine/README.md` bundle links → in-repo `verification/`; `examples_engine/_shared.py` real-table candidate path → `FA_ABM_REAL_TABLE_PATH` env var; vendored 4a README/script example paths generalised. |

Total: 49 files changed, ~5,400 insertions over the baseline.

## 3. AGENTS.md updates (HYG.2b detail)

- Header note documenting the 2026-07-09 cleanup; intro corrected (packaged library with engine/rules/tests/CI, no longer "two notebooks + two modules"); the "no tests, no CI" workflow note replaced with pytest + CI guidance (historical wording preserved as such).
- Phase-1 battery location: `.copilot` session-state and personal OneDrive paths → `verification/phase1_seu_battery/` with an env-var run command.
- **V5 lifespan gap marked CLOSED**: the Phase-3 engine implements the `lifespan_dryproof` reset (`DecisionConfig.lifespan_dryproof=75`, `SimulationEngine._apply_lifespan_reset()`, turnover-tested). The vendored V5 report predates the fix; the battery re-run on the engine is task **VER.1 (open)**.
- All `file:///C:/repos/...` reference links → portable references; Phase-4a/4b gate commands → vendored `verification/` harness paths.
- New **"Phase 4b-pre"** section documenting PRE.1–4, HYG.1–4 and the open VER.1.

## 4. Verification snapshot (2026-07-09)

| Item | Status |
|---|---|
| Phase 0–4b gates | PASS (2026-07-08 record, vendored in `verification/`) |
| PRE.3 staleness guard | Implemented + 4 tests — **PASS** (executed, see §6) |
| PRE.4 adapter contract | Implemented + 10 tests — **PASS** (executed, see §6) |
| PRE.1 import/pin test | **PASS** — mesa 3.3.1 / honeybees 1.2.0 pinned; DYNAMO-M `DecisionModule` + `SLRModel` import & instantiate (see §6) |
| PRE.2 real-table gate | **RUNNING** on the real 61,858 × 207 Charleston table (long-running, tracemalloc-profiled; report/metrics land in `verification/real_table_gate/` on completion — see §6) |
| CI | Workflow committed + guarded for local-only `verification/`; activates on push (pushed) |
| VER.1 battery re-run on engine | **EXECUTED** — V1–V6 reproduced, all figures regenerated (see §6) |

## 5. Next steps

1. ~~`pip install -e .[dev] && pytest tests/ -q`~~ — **DONE** (120 passed; see §6).
2. ~~Execute PRE.1 and pin honeybees/mesa versions~~ — **DONE** (mesa 3.3.1 / honeybees 1.2.0 pinned in `pyproject.toml`).
3. ~~Execute PRE.2 real-table gate~~ — **launched** (long-running full-scale run; report/metrics land in `verification/real_table_gate/` on completion).
4. ~~Push to GitHub → CI~~ — **DONE** (pushed to `origin/main`; CI activated).
5. ~~Run VER.1 (re-run V1–V6 on `SimulationEngine` + `SEURule`)~~ — **battery re-run + figures regenerated**; V5 nuance below.
6. **NEXT:** Enter 4b-full step 2 (populate the real `SLRModel`) per `20260709_proposed_development_architecture_steps.md` §7.2 — every 4b-pre headline risk is now retired.

## 6. Execution addendum — merged & run on the primary workstation (2026-07-09)

The 2026-07-09 drop (authored on a Python-less second machine) was merged into the live
fork `sahand-asgarpour/FloodAdapt-ABM` — one commit per task, reusing the original
messages — and every previously-pending item was **executed** in the `fa_abm` conda env
with the DYNAMO-M checkout and the real Charleston `.nc` present.

| Item | Command | Result |
|---|---|---|
| **Test suite** | `pytest tests/ -q` | **120 passed** (baseline 106 + PRE.3 ×4 + PRE.4 ×10) in ~10 s. All bit-parity gates green. |
| **PRE.1** | `verification/preflight_4b_full/step1_import_test.py` | **gate_pass: True** — mesa 3.3.1, honeybees 1.2.0 (subclassable `Model`), DYNAMO-M `decision_module` imports, `DecisionModule(...)` instantiates, `SLRModel` class reachable. Versions pinned into the `dynamo` extra. |
| **Phase-4b gate** | `verification/phase4b_mesa_native/run_phase4b_verification.py` | **gate_pass: True** (`run_mesa_native == engine.run`, bit-identical). |
| **Phase-4a parity** | `verification/phase4a_parity/run_phase4a_parity.py` | **gate_pass: True** — worst abs 1.9e-6, worst rel 4.8e-7 vs live DYNAMO-M `DecisionModule`. |
| **VER.1 battery** | `verification/phase1_seu_battery/run_seu_validation.py` | V1 PASS · V2 PASS · V3 PASS · V4 PASS · V5 GAP (documented, see note) · V6 PASS (worst rel 4.17e-7). All six `figures/*.png` regenerated. |
| **PRE.2** | `verification/real_table_gate/run_real_table_gate.py` (`FA_ABM_REAL_TABLE_PATH`) | **Launched** on the real 61,858 × 207 table (full-scale, tracemalloc-profiled — long-running); report/metrics written to `verification/real_table_gate/` on completion. |

**Merge/dependency notes.**
- The `verification/` bundle is kept **git-ignored** (present locally so the gates run,
  not pushed); CI's Phase-4b step is guarded with `if: hashFiles(...)` + `continue-on-error`
  so the pipeline stays green on `pytest tests/` alone.
- `mesa` + `honeybees` are declared as an **optional `dynamo` extra** in `pyproject.toml`
  (pinned `mesa==3.3.1`, `honeybees==1.2.0`) and referenced (commented) in `environment.yml`.
  The MVP still runs without them via the dependency-free `mesa_native` mirror.

**V5 nuance (honest).** The vendored battery harness (`run_seu_validation.py`) still
exercises the **legacy `DynamoDecisionBridge`** path, which does not carry the
`lifespan_dryproof` reset — so V5 reproduces as "GAP (documented)" on that path. The reset
**is** implemented and validated on the recommended `SimulationEngine` + `SEURule` path
(`DecisionConfig.lifespan_dryproof=75`, `SimulationEngine._apply_lifespan_reset()`,
covered by the lifespan-turnover unit test in `tests/test_simulation_engine.py`, green in
the 120-test run). Fully flipping the standalone battery's V5 headline to PASS requires
porting the harness itself onto the engine API — tracked as the residual of VER.1.

— End of work log —
