# FloodAdapt-ABM × DYNAMO-M coupling — Unified Development Architecture & Phases

**Date:** 2026-07-09
**Status:** Unified Proposal & Roadmap (Consolidated from all previous phases)
**Scope:** Full architectural history, completed steps, Phase 4b-pre (de-risking), Phase 4b-full roadmap, and beyond.

---

## 1. Project Purpose & Repositories

Two repositories collaborate to answer one research question: *how do policy incentives and lived flood experience shape household-level adaptation, and hence long-term coastal flood risk, under sea-level rise (SLR)?*

| Repository | Role |
|---|---|
| **FloodAdapt-ABM** | Lightweight Monte-Carlo simulation engine. Turns a precomputed FloodAdapt (SFINCS+FIAT) impact lookup table into building-level damage time series and adaptation decisions under an SLR scenario. |
| **DYNAMO-M** | Global honeybees/Mesa-style ABM of coastal household migration & adaptation. Supplies the Subjective Expected Utility (SEU) decision science that replaces FloodAdapt-ABM's naive rule. |

The two stages of FloodAdapt-ABM share exactly one interface: the NetCDF lookup table (dims `object_id × slr × strategy × event`; vars `total_damage`, `inun_depth`; attrs `max_pot_dmg`, `freq`, `primary_object_type`). This seam remains the backbone of the coupling and must stay stable.

## 2. Objective & MVP Scope

The Minimum Viable Product replaces FloodAdapt-ABM's simple reactive rule ("if damage/max_pot_dmg > 0.3 then floodproof") with DYNAMO-M's SEU household decision framework, while KEEPING FloodAdapt-ABM's own elevation assumption (an adapted household's damages are read from the `floodproof_all_0` strategy in the lookup table).

*   **IN:** households = residential buildings only (substring 'RES'); dry flood-proofing vs do-nothing; SEU with CRRA utility, exceedance-curve integration, risk-perception decay, affordability cap, loan amortisation, adaptation lifespan (75 y).
*   **OUT (future extensions):** insurance (calcEU_insure), migration + gravity model, government/dike CBA agent, population/GDP dynamics, variable floodproof height.
*   **BYPASSED by design:** DYNAMO-M's internal hazard physics. All flood depths and damages come from the SFINCS/FIAT lookup table.

## 3. Target Architecture (Strategy Pattern)

The delivered and frozen architecture uses a Strategy Pattern. `SimulationEngine` owns the time loops and data, while the decision rules are completely pluggable.

```text
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

### Connection & Coupling Design (One Timestep)
The `DecisionRule.should_adapt(...)` seam is the stable coupling contract. Per (sequence, year) the engine performs:
1.  Draw year events (Bernoulli + cap).
2.  Prepare damages at current SLR (cubic/linear interp).
3.  Calculate realised damage and `was_flooded` mask.
4.  Update flood experience (risk perception decay).
5.  **DELEGATED TO RULE:** `adapt = rule.should_adapt(state, total_damage, full_catalog, freqs, max_pot_dmg, costs)`
6.  Update state (`is_adapted`, `time_adapted`).
7.  Store history.

## 4. Completed Phases & Steps Taken (Phases 1-4b Scaffold)

The following early phases have been completed and validated.

*   **Phase 1 - Validate the SEU science:** Validated the ported SEU logic against native DYNAMO-M (battery of 6 tests including risk perception decay, affordability, and lifespan resets).
*   **Phase 2 - Consolidate event & time logic:** Extracted inline event drawing and year loops into the core engine. Hardened NetCDF accessors.
*   **Phase 3 - Unified SimulationEngine + DecisionRule:** Built the Strategy pattern architecture. Made `ThresholdRule` and `SEURule` pluggable. Implemented `time_adapted` tracking and lifespan-dryproof reset logic.
*   **Phase 4a - Live DYNAMO-M SEU parity:** Built `DynamoLiveRule` as a parity oracle, importing DYNAMO-M's native `DecisionModule` directly to guarantee the ported `SEURule` hasn't drifted.
*   **Phase 4b (Scaffold) - Mesa-native driving:** Integrated the Mesa-native time step driver without full `CoastalNode` data populations, proving bit-for-bit parity across engines.

## 5. Current State Assessment (as of 2026-07-09)

*   **Unified SimulationEngine + DecisionRule (Phases 2+3):** Done, gated. `ThresholdRule` reproduces legacy output bit-for-bit.
*   **Phase 4a & 4b (Scaffold):** Done, gated. Decisions identical across 5 configs. 104/104 tests pass.
*   **Phase 4b-full (Bind real honeybees SLRModel):** Not started. De-risking tasks required first.
*   **Verification:** Verified real-table execution (61k objects) successfully.

## 6. Recommended Roadmap (Next Steps to Take)

### Phase 4b-pre — De-risking & Hygiene (Do before 4b-full)
These steps are required to close documentation gaps and de-risk the environment lift:
1.  **PRE.1:** Pin honeybees + mesa versions in isolated environment. (DONE)
2.  **PRE.2:** Run gates on real Charleston table; profile `engine.step()`. (DONE)
3.  **PRE.3:** Fix shared-engine design wart in `FloodAdaptSLRModel`. (DONE)
4.  **PRE.4:** Prototype the lookup-table → `CoastalNode` adapter against frozen synthetic nodes. (DONE)
5.  **HYG.1-4 & VER.1-3:** Update README, purge local absolute paths, add CI, run verifications. (DONE)

### Phase 4b-full — Binding the real honeybees SLRModel
*Required effort: 20-40 hours. Pure infrastructure integration, no new science.*
1.  Pin honeybees/mesa versions; verify config compatibility. (Moved to PRE.1)
2.  Populate `SLRModel`: `config_path`, `settings_path`, geojson `study_area`, `args`.
3.  Write lookup-table adapter: map `object_id ↔ CoastalNode`, `property_value ↔ node.wealth`, per-event damages → node arrays.
4.  Route adapt decisions: `CoastalNode.step()` → `DynamoLiveRule.should_adapt` → node state.
5.  Integrate sub-systems: gravity CWD, `spin_up_flag`, low-memory `.npz` paging, reporter.
6.  Execute 4b-full gate: 4b-full ≡ 4b-scaffold bit-for-bit on a deterministic node population.

### Phase 5 — Extending decision rules (Future)
Implement `calcEU_insure` (insurance), migration + gravity, and government/dike CBA as new rules, without touching the core engine.

## 7. Definition of Done

*   **Science validated:** V1–V6 pass on `SimulationEngine` + `SEURule`.
*   **Backwards compatible:** `ThresholdRule` reproduces legacy output.
*   **Single source of truth:** One interpolation kernel, one event generator, one time loop, one pluggable decision interface.
*   **Reproducible:** Verification bundles vendored in-repo, portable, and executed by CI on every push.
*   **Scale-aware:** The engine runs gracefully on the real Charleston table (61k+ objects).
*   **Extension-ready:** New decision science logic can be added as isolated rules.
