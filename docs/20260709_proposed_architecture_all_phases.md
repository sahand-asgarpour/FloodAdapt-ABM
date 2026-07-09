# FloodAdapt-ABM × DYNAMO-M coupling — Unified Development Architecture, Phases & Progress

**Date:** 2026-07-09
**Status:** Canonical, standalone proposal + roadmap + progress record (consolidates every prior version)
**Scope:** Project purpose · MVP scope · target architecture · coupling contract · SEU decision science · completed phases (0 → 4b-scaffold → 4b-pre) · engine performance · issues & resolutions · 4b-full / Phase-5 roadmap · day-by-day progress log

**This document is the single source of truth.** It absorbs the full content of the
dated design docs, work logs and phase model-documentation. The dated per-day
artifacts are retained *locally* for traceability under `docs/progress/` (see the
[document map](#18-document-map--traceability)) but are not required reading —
everything material is reproduced here. Deep, formal detail lives in the two
sibling tracked docs, kept in lock-step with this one:

- [`coupling_architecture.md`](coupling_architecture.md) — full architecture reference (MVP scope, bridge signature, complete SEU math §4, UML/sequence/data-flow diagrams, walkthrough, gate history).
- [`AGENTS.md`](AGENTS.md) — operational guide (data requirements, NetCDF schema, gotchas, phase history, engine performance contract).

---

## 1. Project purpose & repositories

Two repositories collaborate to answer one research question: *how do policy
incentives and lived flood experience shape household-level adaptation, and hence
long-term coastal flood risk, under sea-level rise (SLR)?*

| Repository | Role | Key artefacts |
|---|---|---|
| **FloodAdapt-ABM** | Lightweight Monte-Carlo simulation engine. Turns a precomputed FloodAdapt (SFINCS+FIAT) impact lookup table into building-level damage time series and adaptation decisions under an SLR scenario. | `setup_lookup_table.py` (stage 1), `simulation_engine.py`, `decision_rule.py`, `_core/dynamo_decision_bridge.py`, `_core/lookup_utils.py`, `mesa_native.py`, `coastal_node_adapter.py`, `examples_engine/`, `tests/` |
| **DYNAMO-M** | Global honeybees/Mesa-style ABM of coastal household migration & adaptation. Supplies the Subjective Expected Utility (SEU) decision science that replaces FloodAdapt-ABM's naive rule. | `decision_module.py`, `agents/coastal_nodes.py`, `hazards/flooding/flood_risk.py`, `settings.yml`, `docs/adaptation_decisions_complete.md` |

The two stages of FloodAdapt-ABM share **exactly one interface**: the NetCDF lookup
table (dims `object_id × slr × strategy × event`; vars `total_damage`, `inun_depth`;
attrs `max_pot_dmg`, `freq`, `primary_object_type`). This clean seam is the backbone
of the whole coupling and must remain stable.

## 2. Objective & MVP scope

The Minimum Viable Product replaces FloodAdapt-ABM's simple reactive rule
("if `damage/max_pot_dmg > 0.3` then floodproof") with DYNAMO-M's SEU household
decision framework, while **keeping** FloodAdapt-ABM's own elevation assumption
(an adapted household's damages are read from the `floodproof_all_0` strategy in the
lookup table).

- **IN:** households = residential buildings only (substring `'RES'`); dry flood-proofing vs do-nothing; SEU with CRRA utility, exceedance-curve integration, risk-perception decay, affordability cap, loan amortisation, adaptation lifespan (75 y).
- **OUT (Phase 5+):** insurance (`calcEU_insure`), migration + gravity model, government/dike CBA agent, population/GDP dynamics, variable floodproof height.
- **BYPASSED by design:** DYNAMO-M's internal hazard physics (`interpolate_water_levels`, dike overtopping, GLOFRIS scaling). All flood depths and damages come from the SFINCS/FIAT lookup table.

**Hard requirement (`coupling_architecture.md` §1.3):** for the SEU exceedance
integral to be valid, the stage-1 EventSet should be a true return-period set
(e.g. `[2,5,10,25,50,100,250,500,1000]` yr). If a non-RP set is used, a per-household
damage-sorted exceedance curve must be derived first.

## 3. Target architecture (Strategy Pattern) — delivered & frozen

The endorsed resolution (proposed 2026-07-07/08, delivered in Phases 2–3) is a single
`SimulationEngine` that owns time + data, with a fully pluggable `DecisionRule`.
`ABMSimulator` and `DynamoDecisionBridge` remain as thin backwards-compatible layers.

```text
SimulationEngine (owns time + data)            FloodAdaptSLRModel (Phase 4b: owns time via ticks)
  ├── NetCDF loading / interpolation             ├── engine: SimulationEngine (shared kernel)
  │     ├── strategy cube materialized once       │
  │     └── per-(SLR, method) interp cache         │
  ├── Stochastic event draw (Bernoulli + cap)    └── agents → CoastalNodePopulation → step()
  ├── AgentState (wealth, income, risk_perception,
  │              flood_timer, is_adapted, time_adapted)
  ├── run(no_seq, n_jobs) — parallel Monte-Carlo sequences (bit-identical)
  └── decision_rule: DecisionRule  ← pluggable
        ├── ThresholdRule   (legacy 0.3 rule)
        ├── SEURule         (ported DYNAMO-M SEU — MVP default)
        ├── DynamoLiveRule  (native DYNAMO-M — parity oracle, Phase 4a)
        └── <custom>        (Open/Closed: new science = new rule)
```

### 3.1 The `DecisionRule` interface (stateless, vectorised, NumPy-first)

```python
class DecisionRule:
    def __init__(self, config: DecisionConfig):   # r, sigma, loan_duration,
        ...                                        # expenditure_cap, amenity_weight, lifespan_dryproof, ...
    def should_adapt(self,
        agent_state: AgentState,      # wealth, income, risk_perception, flood_timer,
                                      #   is_adapted, time_adapted
        damages_no_adapt: np.ndarray, # (n_agents, n_events)  full catalog @ SLR_t, no measures
        damages_adapt: np.ndarray,    # (n_agents, n_events)  full catalog @ SLR_t, floodproofed
        event_freqs: np.ndarray,      # (n_events,)  exceedance probs (= 1/RP)
        max_pot_dmg: np.ndarray,      # (n_agents,)
        adaptation_costs: np.ndarray, # (n_agents,)  annualised loan repayment
    ) -> np.ndarray:                  # (n_agents,) bool
        ...
```

The signature was deliberately **widened** versus the 2026-07-07 draft so that
`DynamoLiveRule` is pluggable: (1) `AgentState` carries `risk_perception` (DYNAMO-M's
`calcEU_*` consume it directly); (2) the rule receives *both* per-event damage
matrices at the current SLR (no-adapt and adapt), because the SEU is *ex-ante* and each
`calcEU_*` integrates a full exceedance curve; (3) `adaptation_costs` (annualised loan
repayment) is passed explicitly; (4) decision parameters are injected once via the
constructor from `DecisionConfig`. `ThresholdRule` ignores the extra arguments, so
backward compatibility is preserved.

### 3.2 What got unified

| Concern | Before | After (delivered) |
|---|---|---|
| Damage interpolation | 2 implementations | one `lookup_utils` kernel, called by the engine |
| Event drawing | `ABMSimulator` + inline example code | one method in `SimulationEngine` / `event_utils` (Bernoulli + **random** pool cap) |
| State tracking | 2 separate array sets | one standardised `AgentState` container |
| Year loop | nested loops / manual demo loop | single `run()` / `step()` in the engine |
| Decision logic | hardcoded in classes | pluggable `DecisionRule` |

### 3.3 Design principles enforced

- **Single Responsibility:** the engine owns time & data; the rule owns behaviour. No FloodAdapt or DYNAMO-M imports inside the rule kernels.
- **Open/Closed:** new science (insurance, migration, live DYNAMO-M) arrives as a new `DecisionRule`, not by editing the engine.
- **Backward compatibility:** `ThresholdRule` reproduces legacy `ABMSimulator` results bit-for-bit so existing notebooks keep working.
- **Vectorisation & JIT:** `_iterate_through_flood` stays `@njit`-able; no per-household Python loops in hot paths.

## 4. Connection & coupling design (one timestep)

Per `(sequence, year)` the engine performs the following; the **REPLACED** block is
the only decision-specific part and is delegated to the rule via the stable
`DecisionRule.should_adapt(...)` seam.

```text
1. year_events = sequences[s][t]                      # Bernoulli draw + random cap
2. prepare damages @ SLR_t (cubic/linear via lookup_utils):
     D_no = damage_matrix_no_measures[:, :, t]        # (n_hh, n_events)
     D_fp = damage_matrix_floodproof[:, :, t]
3. realised = where(is_adapted, D_fp, D_no) over occurring events
   total    = sum_events(realised);  was_flooded = total > 0
   --- REPLACED (decision rule) ---------------------------------------
4. update_flood_experience(was_flooded)               # flood_timer, risk_perception decay
5. adapt = rule.should_adapt(state, D_no, D_fp, freqs, max_pot_dmg, costs)
     SEURule: EU_do_nothing = ∫ U(NPV_no_action(p)) dp
              EU_adapt      = ∫ U(NPV_dryproof(p) − cost) dp   (affordability inside)
              adapt = (EU_adapt > EU_do_nothing) & ~is_adapted
     lifespan reset: time_adapted ≥ 75 → un-adapt & re-decide
   --------------------------------------------------------------------
6. is_adapted |= adapt;  time_adapted bookkeeping
7. store damage_history[s,:,t], adapted[s,:,t]
```

**Coupling contract (must stay stable across refactors):**

| Direction | Payload | Shape |
|---|---|---|
| ABM → rule | `expected_damages_no_adapt` / `_adapt` @ SLR_t | `(n_events, n_hh)` |
| ABM → rule | `p_floods` (= `freq` = 1/RP) | `(n_events,)` |
| ABM → rule | `property_value` (`max_pot_dmg`) | `(n_hh,)` |
| ABM → rule | `is_adapted`, `time_adapted`, `was_flooded` | `(n_hh,)` |
| rule → ABM | `adapt_decision` | `(n_hh,)` bool |
| rule → ABM | `risk_perception`, `EU_adapt`, `EU_do_nothing` (diagnostics) | `(n_hh,)` |

Time is driven natively — first by `SimulationEngine.run()`/`step()`, and ultimately
by DYNAMO-M's Mesa `model.step()` cycle (Phase 4b). Keeping the rule interface stable
is what makes the migration non-breaking and preserves the long-term reverse-coupling
vision (DYNAMO-M consuming external flood damages).

## 5. SEU decision science (concise)

The ported `SEURule` reproduces DYNAMO-M's household SEU. Full derivation and symbols
are in [`coupling_architecture.md`](coupling_architecture.md) §4; the essentials:

- **Expected utility of *do nothing*** (`calcEU_do_nothing`): integrate CRRA utility of
  the net-present-value wealth path over the perceived flood exceedance curve. Adapted
  agents return −∞ in the no-nothing branch (they already hold the measure).
- **Expected utility of *dry flood-proofing*** (`calcEU_adapt`): same integral on the
  `floodproof_all_0` damage curve minus the annualised loan cost; **affordability is
  encoded as `EU_adapt = −∞`** when unaffordable (never re-checked downstream, to avoid
  logic drift).
- **Decision:** `adapt = (EU_adapt > EU_do_nothing) & ~is_adapted`.
- **Risk perception** decays over time since the last flood (`flood_timer`), bounded by
  `risk_perc_max`; a flood resets the timer and raises perception.
- **Adaptation lifespan:** floodproofing has a finite life (`lifespan_dryproof = 75 y`).
  When `time_adapted ≥ lifespan_dryproof` the agent un-adapts and re-decides — reproducing
  DYNAMO-M's multi-generational turnover (native source: `coastal_nodes.py:2221–2227`).
- **`p_floods` contract:** both live methods `np.sort(p_floods)` ascending, cap perceived
  probability at 0.998, and integrate (`trapezoid`) over `[0,1]` — hence the RP-EventSet
  requirement (§2) is mandatory for the SEU/live rules.

## 6. Decision rules & phase model-documentation

| Rule | Behaviour | Use |
|---|---|---|
| `SEURule` *(default)* | ported DYNAMO-M SEU (ex-ante EU maximisation, CRRA utility, risk-perception decay, affordability cap, loan amortisation, 75-y lifespan reset) | the validated MVP science |
| `ThresholdRule` | legacy ex-post rule: adapt when `damage/max_pot_dmg > 0.3` | backward compat; reproduces `ABMSimulator` bit-for-bit |
| `DynamoLiveRule` | calls the **native** DYNAMO-M `DecisionModule` (optional, guarded via `DYNAMO_M_PATH`) | parity oracle — proves the port hasn't drifted |
| `<custom>` | subclass `DecisionRule`, implement `should_adapt(...)` | new science without engine surgery (`examples_engine/03_custom_rule.py`) |

### 6.1 Phase 4a — `DynamoLiveRule` (live parity oracle)

A thin adapter that imports DYNAMO-M's `DecisionModule` and calls `calcEU_adapt` /
`calcEU_do_nothing` with the same arrays the bridge assembles. Verified feasible in
source: those methods are near-pure array functions (depend only on the `@njit`
`IterateThroughFlood` and `self.error_terms_stay`, not on `self.model`/`self.agents`),
so **no full Mesa model is required**. Obstacles handled: (1) the module-level
`gravity_models` import is guarded as an **optional** dependency; (2) a minimal stub model
supplies `settings`/`random_module`/`args`; (3) for bit-parity, `error_interval=0`
(`error_terms_stay=1`), aligned RNG, `amenity_value=0`. **Gate PASS:** decisions identical
across 5 configs; worst EU abs diff 1.9e-6, rel 4.8e-7 (tol abs ≤1e-3, rel ≤1e-4).

### 6.2 Phase 4b — Mesa-native driving (scaffold)

Phase 4b inverts *who owns time*. A small `FloodAdaptSLRModel` advances one tick at a
time via `model.step()`, mirroring native DYNAMO-M `SLRModel.run_model()`
(`while True: self.step()`). The object graph mirrors DYNAMO-M
(`FloodAdaptSLRModel → Agents → CoastalNodePopulation → DecisionRule`); the decision
science is untouched — the same `DecisionRule.should_adapt` seam is called from a
different driver. **Gate PASS:** `run_mesa_native == engine.run` bit-for-bit across
5 cases (SEURule ×3, ThresholdRule ×2).

### 6.3 Phase 4b-full — the lookup-table → CoastalNode adapter (PRE.4, prototyped)

The adapter is the one genuinely new modelling artefact for 4b-full. Delivered as a
standalone, contract-tested prototype (`coastal_node_adapter.py`):

- `CoastalNodeArrays` — native node-array mirror: `property_value`, events-first
  `damages_coastal_cells`, `p_floods`, `adapt`, `time_adapt`, `_flood_plain` geom_id.
- `LookupTableAdapter.populate()` (forward) / `write_back()` (reverse, with object_id
  alignment guards) / `round_trip_check()` (executable bit-parity contract).
- 10 tests including an end-to-end proof that routing state through the node is a
  simulation no-op.

### 6.4 Phase 4b-pre — the shared-engine staleness guard (PRE.3)

`FloodAdaptSLRModel.__init__` calls `engine.reset_state()` on a *shared* engine; a second
model would silently invalidate the first model's live `agents.regions.state` view. Fixed
with `SimulationEngine.state_epoch` + `FloodAdaptSLRModel._check_not_stale()`: stepping a
stale model now raises `RuntimeError` instead of corrupting state. Bit-parity gate
unaffected (`run_mesa_native` constructs models sequentially). +4 tests.

## 7. Completed phases & steps

| Phase | What was done | Gate |
|---|---|---|
| **0 — Stabilise** | Fixed the `cfg.environment.max_slr` demo crash; reconciled `DecisionConfig` docstring vs defaults; green examples. | Demos run; suite passes |
| **1 — Validate SEU** | Ran the `coupling_architecture.md` §12.1 battery (degenerate risk perception → baseline; adoption vs 0.3-threshold; sensitivity sweeps; affordability → zero adoption; lifespan turnover). Cross-checked ported SEU vs native `calcEU_*`. | Battery passes; SEU == DYNAMO-M within tol (worst rel EU 4.2e-7) |
| **2 — Consolidate event & time** | Moved Bernoulli draw + cap into the core with **random** pool selection; native `run()`/`step()`; hardened `read_impacts_dataset` with an `object_id`-indexed accessor. | No decision logic in example scripts; ThresholdRule regression exact |
| **3 — SimulationEngine + rules** | Built `SimulationEngine`, `AgentState`, `DecisionRule` ABC; ported `ThresholdRule`/`SEURule`; added `eu_history`, `is_residential`; **implemented `time_adapted` + `lifespan_dryproof=75` reset**. | ThresholdRule reproduces legacy output; battery re-passes |
| **4a — Live parity** | `DynamoLiveRule` parity oracle (§6.1). | PASS (worst EU abs 1.9e-6, rel 4.8e-7) |
| **4b — Mesa-native (scaffold)** | Time-ownership inversion via `FloodAdaptSLRModel.step()` (§6.2). | PASS (5/5 bit-for-bit) |
| **4b-pre — De-risking & hygiene** | PRE.1 (pin mesa 3.3.1 / honeybees 1.2.0, import/instantiate DYNAMO-M) · PRE.2 (**real-table gate**, §9) · PRE.3 (staleness guard, §6.4) · PRE.4 (adapter prototype, §6.3) · HYG.1–4 (README rewrite, path purge + vendored `verification/`, **CI**, engine notebook + Markdown design docs) · VER.1–2 (battery re-run + figures). | All PRE/HYG/VER closed; **125 tests PASS**; CI green |

## 8. Current state assessment (2026-07-09)

| Component | Status | Notes |
|---|---|---|
| Stage-1 lookup table (`setup_lookup_table.py`) | Done / stable | Unchanged by the coupling. EventSet must be RP-based. |
| Unified `SimulationEngine` + `DecisionRule` (Phases 2+3) | **Done, gated** | `ThresholdRule` reproduces legacy output bit-for-bit; `SEURule` matches the Phase-1 battery; lifespan-dryproof reset implemented and unit-tested. |
| Phase 4a — `DynamoLiveRule` parity oracle | **Done, gated** | Decisions identical across 5 configs; worst EU abs 1.9e-6, rel 4.8e-7. |
| Phase 4b — Mesa-native driving (scaffold) | **Done, gated** | `run_mesa_native == engine.run` bit-for-bit; examples 01–06 run (exit 0). |
| Engine performance (interp cache + `n_jobs`) | **Done** | Full-scale bottleneck fixed; parallel sequences bit-identical (§9). |
| Real-table gate (PRE.2) | **Done / PASS** | `gate_pass: True` on the real 61,858 × 207 table (§9). |
| CI | **Present, green** | `.github/workflows/ci.yml`: matrix pytest + examples + vendored 4b gate. |
| Test suite | **125 passing** | bridge, engine, rules, agent state, event utils, live-parity, mesa-native, perf. |
| Phase 4b-full — bind real honeybees `SLRModel` | **Not started** | 6-step roadmap (§11.2); top risks retired by 4b-pre. |
| Notebook 2 (`2_simulate_adaptation.ipynb`) | Legacy path | Still uses `ABMSimulator`; the engine path is notebook `3_simulate_adaptation_engine.ipynb`. |

## 9. Engine performance & the real-table gate (PRE.2)

Running PRE.2 at full scale surfaced a hot-path bottleneck (>11 min). Two independent
causes were found and fixed as **committed engine improvements** (commit `6f45d6f`),
bit-identical, benefiting the coming 4b-full runs.

**Root causes.** (1) `prepare_damage_arrays()` re-interpolated the whole 61,858 × 207
catalogue on *every tick of every sequence* though the SLR trajectory is identical across
sequences (`no_seq×` redundant, ~5.5 s/call). (2) The residential subset used a boolean
`isel` on the lazily backed xarray cube — pathologically slow (~24 s first materialize).

**Fixes.**
- `lookup_utils`: split `materialize_strategy_cube()` (materialize full cube in NumPy, then mask in-memory) from `interpolate_cube_at_slr()` (unchanged `interp1d` math → bit-identical).
- Bridge: materialize each strategy cube **once**; memoise `prepare_damage_arrays` per `(SLR, method)`; cached arrays read-only; `clear_interp_cache()` frees memory.
- `SimulationEngine.run(n_jobs=N)`: run independent sequences across a thread pool of per-worker engine clones sharing a pre-warmed read-only cache. `n_jobs=1` (default) leaves the sequential path untouched; parallel output is **bit-identical** for deterministic rules. `DecisionRule.clone()` gives isolated per-worker rules.

**Measured effect (real Charleston table).**

| Metric | Before | After |
|---|---:|---:|
| First cube materialization (masked) | ~24 s | ~3.6 s |
| Interpolation per distinct SLR | ~5.5 s | ~1.0 s |
| Interpolation on repeated SLR | ~5.5 s | ~0 s (cache hit) |
| `engine.run` 4 seq × 30 y (sequential) | 116.7 s | — |
| `engine.run` 4 seq × 30 y (`n_jobs=-1`) | — | 83.3 s (×1.4, bit-identical) |

**Gate outcome.** `verification/real_table_gate/real_table_report.md`: `Gate: PASS` —
`phase4b_bit_parity_real_table: True`, `phase4a_parity_real_table_subset: True`.
57,976 residential agents (of 61,858 objects), 3 seq × 30 y; run A (parallel `engine.run`)
73.7 s / 3.3 GiB, run B (`run_mesa_native`) 119.4 s / 4.8 GiB, per-tick mean 2.62 s / max 8.96 s.

**Further speedups (noted, not required for the MVP):** process pool for the Python-bound
SEU math; float32 damage arrays; reusing prepared damages across gate runs; further
vectorising the decision kernel.

## 10. Issues found & resolutions (consolidated)

Merged from the 2026-07-08 and 2026-07-09 review tables; all rows now resolved except
where noted.

| Sev. | Issue | Location | Resolution |
|---|---|---|---|
| High | `cfg.environment.max_slr` crash in the demo summary | `run_coupled_example.py` | Fixed (Phase 0). |
| Med | `DecisionConfig` docstring defaults ≠ actual defaults | `coupling_config.py` | Reconciled to `settings.yml`; docstring authoritative (Phase 0). |
| Med | Inline event draw / cap duplicated across scripts; freq-based cap | example scripts | Moved to core; **random** pool selection (Phase 2). |
| Med | `read_impacts_dataset` assumed row order == object_id order | `setup_lookup_table.py` | `object_id`-indexed accessor + alignment assert (Phase 2). |
| Med | Shared-engine `reset_state()` footgun | `mesa_native.py:174` | `state_epoch` guard + tests (PRE.3). |
| Med | Gates only ran on the synthetic table | examples 05/06 | **PRE.2 CLOSED** — real-table gate PASS; interpolation bottleneck fixed (§9). |
| Med | V1–V6 battery ran on the old bridge API | `run_seu_validation.py` | Battery re-run + figures regenerated (VER.1); V5 nuance below. |
| Med | V5 lifespan report said "GAP" though reset shipped | `05_lifespan.md` | Reset implemented + unit-tested on the engine; standalone-harness port is the VER.1 residual. |
| Med | Stale root `README.md` | `README.md` | Rewritten (HYG.1); later extended with the performance section. |
| Med | No CI | repo root | `.github/workflows/ci.yml` (HYG.3). |
| Low | Machine-specific absolute paths; unvendored bundles | `AGENTS.md`, `verification_tests/*` | Purged to env vars; bundles vendored (HYG.2, VER.2). |
| Low | Doc paths pointed at repo root, not `floodadapt_abm/` | `coupling_architecture.md` | Repo-relative; doc relocated into this repo's `docs/`. |
| Low | Hardcoded `INITIAL_YEAR=2020` / `TIME_HORIZON=30` in the demo | `run_coupled_example.py:52` | Superseded by the engine/notebook path (derive from SLR metadata). |
| Low | `.docx` phase docs not diffable | `docs/` | Converted to Markdown; this doc is the consolidated record. |

## 11. Roadmap (next steps)

Guiding principle: unify the plumbing, keep the decision logic pluggable, validate before
refactoring, never regress the `ThresholdRule` path. 4b-full is entered as **pure
infrastructure wiring** with its top risks (version drift, scale, adapter correctness,
state sharing) already retired in 4b-pre.

### 11.1 Phase 4b-pre — de-risking & hygiene — ✅ DONE (2026-07-09)

PRE.1–4, HYG.1–4, VER.1–2 all closed (§7, §14). The 4b-pre gate is **OPEN** — 4b-full
step 2 may begin.

### 11.2 Phase 4b-full — binding the real honeybees `SLRModel` (≈20–40 hrs, no new science)

| Step | Task | Risk | Gate |
|---|---|---|---|
| 1 | Pin honeybees/mesa; verify config compatibility. **(done as PRE.1)** | Low | Import test PASS |
| 2 | Populate `SLRModel`: `config_path`, `settings_path`, geojson `study_area`, `args`; instantiate `Data`, `FloodRisk`, `CoastalAmenities`. | Medium | `SLRModel()` succeeds |
| 3 | Wire the lookup-table adapter (prototyped in PRE.4): `object_id ↔ CoastalNode`, `property_value ↔ node.wealth`, per-event damages → node arrays. | Medium | Round-trip reproduces 4b-scaffold |
| 4 | Route adapt decisions: `CoastalNode.step()` → `DynamoLiveRule.should_adapt` → node state. | Medium | Decisions recorded in native arrays |
| 5 | Integrate sub-systems: gravity CWD, `spin_up_flag`, low-memory `.npz` paging, `_flood_plain` filtering, reporter. | Medium–High | All sub-step logic runs |
| 6 | Execute the 4b-full gate: 4b-full ≡ 4b-scaffold bit-for-bit on a deterministic node population. | Low | Bit-parity gate PASS |

### 11.3 Phase 5 — extending decision rules (future)

`calcEU_insure` (insurance), migration + gravity, government/dike CBA — each as a new
rule/agent class, never engine surgery.

## 12. Phase-gate summary

| Phase | Deliverable | Exit criterion | Status |
|---|---|---|---|
| 0 | Green examples + reconciled config | Demos run; suite passes | ✅ PASS |
| 1 | Validated SEU | §12.1 battery passes; SEU == DYNAMO-M within tol | ✅ PASS |
| 2 | Core event + time engine | No decision logic in example scripts | ✅ PASS |
| 3 | `SimulationEngine` + rules | ThresholdRule reproduces legacy output; lifespan reset shipped | ✅ PASS |
| 4a | Live DYNAMO-M SEU parity | `calcEU_*` parity within tol; import optional/guarded | ✅ PASS (EU abs 1.9e-6, rel 4.8e-7) |
| 4b | Mesa-native driving (scaffold) | `run_mesa_native == engine.run` bit-for-bit | ✅ PASS (5/5) |
| 4b-pre | De-risking + hygiene | PRE.1–4 + HYG.1–4 + VER.1–2; CI green; real-table gate executed | ✅ DONE (125 tests; PRE.2 `gate_pass: True`) |
| 4b-full | Full Mesa-native integration | `SLRModel.step()` drives native `CoastalNode` population; 4b-full ≡ 4b-scaffold | 🔲 READY (gate open) |
| 5 | Extending decision rules | insurance / migration / government CBA as new rules | 🔲 FUTURE |

## 13. Consolidated TODO backlog

Completed items retained for traceability.

| Pri | Task | Phase | Status |
|---|---|---|---|
| P0 | Fix `cfg.environment.max_slr` crash; reconcile `DecisionConfig` docstring | 0 | DONE |
| P1 | Validate SEU vs DYNAMO-M; run §12.1 battery | 1 | DONE |
| P2 | Event drawing / time loop / accessor consolidation (random pool cap) | 2 | DONE |
| P3 | `SimulationEngine` + `DecisionRule`; widened interface; lifespan reset | 3 | DONE |
| P4a | Live DYNAMO-M `DecisionModule` parity oracle | 4a | DONE (gate PASS) |
| P4b | Mesa-native driving (scaffold); bit-parity gate | 4b | DONE (gate PASS) |
| P0 | PRE.1 — pin honeybees/mesa; import/instantiate | 4b-pre | DONE (mesa 3.3.1 / honeybees 1.2.0) |
| P0 | PRE.3 — shared-engine staleness guard | 4b-pre | DONE (`7ceb144`) |
| P0 | HYG.1 — rewrite stale README | 4b-pre | DONE (`d05a97a`) |
| P1 | PRE.2 — real-table gate; profile `engine.step()` | 4b-pre | DONE / PASS (`6f45d6f`) |
| P1 | VER.1 — re-run V1–V6 on engine; regenerate V5 | 4b-pre | DONE (battery + figures; V5 residual below) |
| P1 | HYG.3 — CI pipeline | 4b-pre | DONE (`8b7384c`) |
| P1 | HYG.2 — de-machine-ify `AGENTS.md`; vendor bundles | 4b-pre | DONE (`3af86e8`, `87ea7c6`) |
| P2 | PRE.4 — standalone adapter prototype | 4b-pre | DONE (`1cb7862`) |
| P2 | VER.2 — verification-bundle portability | 4b-pre | DONE |
| P2 | HYG.4 — engine notebook; `.docx` → Markdown | 4b-pre | DONE (`2225ae6`) |
| P1 | Engine performance: interp cache + `n_jobs` (+ tests) | 4b-pre | DONE (`6f45d6f`, 125 tests) |
| P3 | VER.1 residual — port the standalone V5 harness onto the engine API | 4b-pre | OPEN |
| P3 | VER.3 — empirical native V5 lifespan reference run | 4b-full (after step 1) | OPEN |
| P4b | 4b-full steps 2–6 (bind real honeybees `SLRModel`) | 4b-full | READY (gate open) |
| P5 | Insurance / migration / government rules | 5 | FUTURE |

## 14. Chronological progress log (day-by-day traceability)

Each dated artifact referenced below is retained locally under `docs/progress/` (§18).

### 2026-07-07 → 2026-07-08 — Consolidation proposal & Phase 0–3 delivery
- Authored the coupling MVP proposal and the Strategy-Pattern target architecture; reconciled doc/code drift (docstrings, event-cap semantics, method names).
- Delivered Phases 0–3: the unified `SimulationEngine` + `AgentState` + `DecisionRule` ABC; `ThresholdRule`/`SEURule` on the interface; `time_adapted` + `lifespan_dryproof=75` reset.
- Wrapped Phase 4a (`DynamoLiveRule` parity oracle) and reorganised the examples into the numbered `examples_engine/` learning path (01–06). Delivered the Phase 4b scaffold (Mesa-native driving) with the bit-parity gate.
- Artifacts: `progress/proposed_architecture/20260708_proposed_development_architecture_steps.*`, `progress/performed_tasks/20260708_performed_tasks.*`, `progress/model_documentation/20260708_phase_3__model_documentaiton.*`, `progress/model_documentation/20260708_phase_4b__model_documentaiton.*`.

### 2026-07-09 (a) — Post-Phase-4b review & 4b-pre execution
- External review confirmed the gates were genuinely computed but flagged doc/reproducibility drift and synthetic-only validation.
- Executed the full 4b-pre phase, **one commit per task**: PRE.3 staleness guard (`7ceb144`), PRE.4 adapter prototype (`1cb7862`), PRE.1+PRE.2 harnesses (`fdaf257`), HYG.2 vendoring (`3af86e8`), HYG.1 README (`d05a97a`), HYG.3 CI (`8b7384c`), HYG.4 notebook + Markdown docs (`2225ae6`), AGENTS path purge (`87ea7c6`).
- Merged into `sahand-asgarpour/FloodAdapt-ABM` and executed on the primary workstation: **120 tests pass**; PRE.1 gate PASS (mesa 3.3.1 / honeybees 1.2.0); Phase-4a and Phase-4b gates PASS; VER.1 battery re-run (V1–V4/V6 PASS, V5 GAP on the legacy harness — engine path reset unit-tested).
- Artifacts: `progress/proposed_architecture/20260709_phase_pre_4b_full_proposed_development_architecture_steps.*`, `progress/performed_tasks/20260709_performed_tasks.*`, `progress/model_documentation/20260709_phase_4b_full__model_documentaiton.*`.

### 2026-07-09 (b) — PRE.2 real-table gate + engine speedups
- Ran PRE.2 on the real 61,858 × 207 Charleston table; hit a full-scale interpolation bottleneck and fixed it with the per-SLR cube cache + `n_jobs` parallel sequences (commit `6f45d6f`, bit-identical). +5 tests → **125 pass**. Gate **PASS**.
- Fixed a NumPy-2.0 `np.trapz` bug (`2035b80`). Recorded the work across `performed_tasks` §6.1 and the architecture docs.

### 2026-07-09 (c) — Coupling-architecture relocation & docs reorg
- Moved `coupling_architecture.md` into this repo's `docs/`, refreshed it (paths, 125 tests, PRE.2 gate, engine perf), and propagated the speedups into `README.md` and `examples_engine/README.md` (commit `673c535`).
- Reorganised `docs/` into `docs/progress/{performed_tasks, proposed_architecture, model_documentation}/`; renamed the dated proposed doc to `..._phase_pre_4b_full_...` and the model docs to `*__model_documentaiton`; fixed the corrupt `.git/info/exclude`; produced this unified doc (+ Arial `.docx`).

## 15. Definition of done & alignment with the objective

- **Science validated on the shipped code:** V1–V6 on `SimulationEngine` + `SEURule` (V5 demonstrating lifespan turnover; standalone-harness V5 port is the residual).
- **Backwards compatible:** `ThresholdRule` reproduces legacy output; existing notebooks keep working; an engine-based notebook exists.
- **Single source of truth:** one interpolation kernel, one event generator, one time loop, one pluggable decision interface — and one accurate README + this consolidated design record.
- **Reproducible:** verification bundles vendored, portable (env-var paths, figures present), executed by CI on every push.
- **Scale-aware:** the engine and tick driver run on the real Charleston table (61k+ objects) with recorded runtime/memory, after the interpolation-cache + parallel-sequence speedups.
- **Extension-ready:** insurance, migration and government agents arrive as new rules without touching the engine; 4b-full enters as pure infrastructure wiring with its risks retired in 4b-pre.

## 16. Go/No-Go

Phases 0–4b (scaffold) + 4b-pre are COMPLETE with all gates PASS (125 tests). The 4b-pre
gate is **OPEN**: 4b-full step 2 (populate the real `SLRModel`) may begin — every headline
risk (version drift, scale, adapter correctness, state sharing) has been retired.

## 17. Key files

| Area | Files |
|---|---|
| Engine & rules | `floodadapt_abm/simulation_engine.py`, `decision_rule.py`, `agent_state.py`, `event_utils.py` |
| Ported kernels | `floodadapt_abm/_core/dynamo_decision_bridge.py`, `_core/lookup_utils.py` |
| Phase 4a/4b | `floodadapt_abm/dynamo_live_rule.py`, `mesa_native.py`, `coastal_node_adapter.py` |
| Stage 1 & config | `floodadapt_abm/setup_lookup_table.py`, `coupling_config.py` |
| Examples & tests | `examples_engine/01…06`, `tests/` (125) |
| Verification (local) | `verification/{phase1_seu_battery, phase4a_parity, phase4b_mesa_native, real_table_gate, preflight_4b_full}/` |
| Docs (tracked) | `docs/coupling_architecture.md`, `docs/AGENTS.md`, this file |

## 18. Document map & traceability

Tracked, canonical docs (kept in lock-step):

- `docs/20260709_proposed_architecture_all_phases.md` (+ `.docx`, Arial) — **this document**.
- `docs/coupling_architecture.md` — full architecture + SEU math reference.
- `docs/AGENTS.md` — operational guide + engine performance contract.

Local, per-day artifacts (git-excluded, retained for day-by-day traceability):

```
docs/progress/
  performed_tasks/
    20260708_performed_tasks.{md,docx}
    20260709_performed_tasks.{md,docx}
  proposed_architecture/
    20260708_proposed_development_architecture_steps.{md,docx}
    20260709_phase_pre_4b_full_proposed_development_architecture_steps.{md,docx}
  model_documentation/
    20260708_phase_3__model_documentaiton.{md,docx}
    20260708_phase_4b__model_documentaiton.{md,docx}
    20260709_phase_4b_full__model_documentaiton.{md,docx}
```

— End of unified development architecture, phases & progress (2026-07-09) —
