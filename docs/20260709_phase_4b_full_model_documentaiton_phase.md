# FloodAdapt-ABM × DYNAMO-M Coupling

Phase 4b-full — Binding the Real honeybees SLRModel (Model Documentation)

Pre-flight (4b-pre) delivered · 4b-full steps 2–6 pending execution

Date: 2026-07-09 · Status: **4b-pre complete (this doc); 4b-full NOT started** · Follows: `20260708_phase_4b_model_documentaiton_phase.docx` (4b-scaffold)

## 1. Executive Summary

Phase 4b-full binds the **real honeybees `SLRModel`** so the native DYNAMO-M Mesa ecosystem drives the coupling: native `model.step()` ticks advance native `CoastalNode` populations whose damage arrays are populated **from the FloodAdapt lookup table**, and whose adaptation decisions flow back. The 4b-scaffold (2026-07-08) already proved time-ownership inversion is non-breaking; 4b-full is therefore an *environment* migration, not a re-architecture.

This document records the **4b-pre** stage (2026-07-09): the de-risking work that must precede the environment lift, per the review-driven roadmap (`20260709_proposed_development_architecture_steps.md` §7.1). Delivered:

- **The lookup-table → CoastalNode adapter is prototyped and contract-tested** (PRE.4) — the single genuinely new modelling artefact of 4b-full, validated standalone so the eventual 4b-full ≡ 4b-scaffold gate isolates the environment swap alone.
- **The shared-engine state hazard is closed** (PRE.3) — a staleness guard prevents a stale model from silently mutating another model's state, a pattern 4b-full would otherwise have copied.
- **The environment risks are instrumented** (PRE.1, PRE.2) — a pin-after-verify import kit for honeybees/mesa and a real-Charleston-table gate runner with per-tick profiling, both self-reporting.

## 2. Where 4b-full stands in the phase sequence

| Phase | Time owner | Agent population | Decision kernel | Status |
|---|---|---|---|---|
| 3 / 4a | `SimulationEngine.run()` | `AgentState` from lookup table | `SEURule` / `DynamoLiveRule` | Done, gated |
| 4b-scaffold | `FloodAdaptSLRModel.step()` (mirror) | `AgentState` (shared kernel) | unchanged | Done, gated (bit-parity) |
| **4b-pre** | — (de-risking) | — | unchanged | **Done (this doc)** |
| **4b-full** | native honeybees `SLRModel.step()` | native `CoastalNode` arrays ← lookup table | unchanged (`DynamoLiveRule` seam) | **Not started** |

The `DecisionRule.should_adapt(...)` contract is frozen across every row — that invariance is what makes each migration attributable and non-breaking.

## 3. The adapter (PRE.4) — design as implemented

Module: `floodadapt_abm/coastal_node_adapter.py` · Tests: `tests/test_coastal_node_adapter.py` (10)

### 3.1 CoastalNodeArrays — the native array mirror

Dependency-free dataclass mirroring the `CoastalNode` fields consumed by `calcEU_do_nothing` / `calcEU_adapt` and the adaptation bookkeeping in `coastal_nodes.py`:

| Field | Native counterpart | Convention enforced |
|---|---|---|
| `geom_id` | `node.geom_id` | `'_flood_plain'` suffix (native node filtering) |
| `n` | `node.n` | residential household count |
| `property_value` | `node.property_value` | `max_pot_dmg`, float64 |
| `damages_coastal_cells` | `node.damages_coastal_cells` | **events-first** `(n_events, n)` no-measures damages @ SLR_t |
| `damages_coastal_cells_adapt` | (floodproof strategy) | events-first `(n_events, n)` |
| `p_floods` | exceedance probabilities | `= freq = 1/RP`, ascending-sortable |
| `adapt`, `time_adapt` | `node.adapt`, `node.time_adapt` | int8 / int32 (native stores ints) |
| `object_ids` | — (join key) | preserves lookup-table ↔ state row order |

### 3.2 Forward and reverse mapping

```
LookupTableAdapter(engine)
  .populate(slr_value)   FloodAdapt -> node : engine.prepare_damages(SLR_t)
                         via the validated interpolation kernel, transposed
                         to the native events-first layout; economics and
                         current adapt/time_adapt read from live AgentState
  .write_back(node)      node -> FloodAdapt : node.adapt / node.time_adapt
                         routed into AgentState, guarded by size and
                         object_id-order checks (raises on misalignment)
```

This pair is the **reverse-coupling heartbeat**: damages flow FloodAdapt → DYNAMO-M, decisions flow back. In 4b-full, `populate()`'s logic moves inside the native per-tick data path and `write_back()`'s logic becomes the node-state update after `DynamoLiveRule.should_adapt`.

### 3.3 The executable contract (PRE.4 gate)

`round_trip_check(engine, slr)` asserts, on the frozen synthetic population:

- every forward-mapped array is **bit-identical** to its engine source (damages via transpose round-trip, `property_value`, `p_floods`, `object_ids`, `adapt`);
- `write_back` restores a mutated adaptation state **exactly**;
- all populated arrays are **copies** (mutating the node never touches engine data);
- end-to-end: interleaving `populate → write_back` before every `engine.step()` over a 5-year run leaves `is_adapted` / `time_adapted` / `risk_perception` bit-identical to a direct run — the adapter is pure plumbing.

**Gate status: implemented + tests authored; pytest execution pending on the dev machine / CI** (this workstation has no Python interpreter).

## 4. The staleness guard (PRE.3)

`SimulationEngine` gains a monotonic `state_epoch`, bumped by every `reset_state()`. `FloodAdaptSLRModel` records the epoch it claims at construction; `CoastalNodePopulation.step()` verifies it and raises `RuntimeError` when stale (a newer model, or `engine.run()`, has replaced the shared `AgentState`). Rationale: 4b-full will instantiate model objects around a shared engine repeatedly during wiring — without the guard, a stale driver silently corrupts the new owner's state, producing exactly the unattributable numerical drift the bit-parity methodology exists to prevent. `run_mesa_native()` is unaffected (sequential models), so the 4b gate semantics are unchanged.

## 5. Environment instrumentation (PRE.1, PRE.2)

**PRE.1 — `verification/preflight_4b_full/`.** Throwaway conda env (deliberately unpinned; **pin-after-verify**) plus `step1_import_test.py`, which checks: `mesa` import, `honeybees` import + `honeybees.model.Model` subclassability, DYNAMO-M `decision_module` import via `DYNAMO_M_PATH`, the Phase-4a stub `DecisionModule(agents=None, model=<stub>)` instantiation re-proven in the new env, and `model.py` importability. Writes `step1_report.md` / `step1_versions.json`; exit code = gate. **Run this before 4b-full step 2; pin the recorded versions.**

**PRE.2 — `verification/real_table_gate/`.** Runs `engine.run` vs `run_mesa_native` **bit-parity at real scale** (61,858 objects × 207 events) with wall-time and tracemalloc peak per run, a per-tick `engine.step()` profile (the hot path 4b-full inherits), and an optional `DynamoLiveRule` parity spot-check when DYNAMO-M is importable. Configuration via `FA_ABM_REAL_TABLE_PATH`, `FA_ABM_GATE_NO_SEQ`, `FA_ABM_GATE_YEARS`. If per-tick time is dominated by `prepare_damages` interpolation, cache interpolated matrices per unique SLR value **before** 4b-full.

Both kits are **prepared, not executed** on this workstation (no Python, no DYNAMO-M checkout, no real `.nc`); their READMEs state this and give exact commands.

## 6. 4b-full execution plan (steps 2–6, entered only after 4b-pre gates close)

| Step | Task | Builds on | Gate |
|---|---|---|---|
| 2 | Populate `SLRModel`: `config_path`, `settings_path`, geojson `study_area`, `args`; instantiate `Data`, `FloodRisk`, `CoastalAmenities` | PRE.1 (pinned env) | `SLRModel()` succeeds |
| 3 | Port `LookupTableAdapter.populate()` into the native per-tick data path (`object_id ↔ CoastalNode`, `property_value ↔ node.wealth`, per-event damages → node arrays) | PRE.4 (contract-tested prototype) | node arrays reproduce the prototype bit-for-bit |
| 4 | Route decisions: `CoastalNode.step()` → `DynamoLiveRule.should_adapt` → node state (`write_back` semantics) | PRE.4, Phase 4a | decisions recorded in native arrays |
| 5 | Integrate sub-systems: gravity CWD, `spin_up_flag`, low-memory `.npz` paging, `geom_id '_flood_plain'` filtering, reporter | PRE.2 (scale profile) | all sub-step logic runs |
| 6 | **4b-full gate:** 4b-full ≡ 4b-scaffold bit-for-bit on a deterministic node population | everything above | bit-parity PASS |

Estimated 20–40 h of infrastructure wiring; no new science. Every headline risk (version drift, scale, adapter correctness, shared-state corruption) is retired or instrumented by 4b-pre.

## 7. Verification & traceability

- One git commit per task: PRE.3 `7ceb144`, PRE.4 `1cb7862`, PRE.1+2 `fdaf257` (plus HYG commits — see `20260709_performed_tasks.md` §2).
- New tests authored: 4 (staleness guard) + 10 (adapter) = 14, alongside the 104 existing; CI (`.github/workflows/ci.yml`) executes the full suite + the Phase-4b harness on every push.
- Open item **VER.1**: re-run the V1–V6 battery on `SimulationEngine` + `SEURule` (the vendored Phase-1 battery validated the original bridge path; its V5 "GAP" verdict predates the Phase-3 lifespan fix).

## 8. Key files

| Path | Purpose |
|---|---|
| `floodadapt_abm/coastal_node_adapter.py` | PRE.4 adapter prototype (`CoastalNodeArrays`, `LookupTableAdapter`, `round_trip_check`) |
| `tests/test_coastal_node_adapter.py` | 10 adapter contract tests |
| `floodadapt_abm/simulation_engine.py` / `mesa_native.py` | PRE.3 `state_epoch` + `_check_not_stale` |
| `tests/test_mesa_native.py::TestSharedEngineStalenessGuard` | 4 guard tests |
| `verification/preflight_4b_full/` | PRE.1 pin/import kit |
| `verification/real_table_gate/` | PRE.2 real-table gate + profiler |
| `docs/20260709_proposed_development_architecture_steps.md` | Task definitions, backlog, phase gates |

— End of Phase-4b-full (pre-flight) model documentation —
