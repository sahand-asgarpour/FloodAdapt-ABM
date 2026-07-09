# FloodAdapt-ABM & DYNAMO-M coupling

> **Provenance (HYG.4, 2026-07-09):** converted from `20260708_proposed_development_architecture_steps.docx` so the design record is diffable in-repo. Text extracted from the .docx XML; original heading levels and table layouts are flattened (numbered section lines promoted to headings heuristically). The .docx remains the typeset original.

Proposed Development Architecture & Steps
Status: proposal for next development phase   |   Scope: MVP consolidation + unified engine roadmap
## 1. Project purpose & repositories (validated recap)
Two repositories collaborate to answer one research question: how do policy incentives and lived flood experience shape household-level adaptation, and hence long-term coastal flood risk, under sea-level rise (SLR)?
Repository
Role
Key artefacts
FloodAdapt-ABM(c:\repos\FloodAdapt-ABM)
Lightweight Monte-Carlo simulation engine. Turns a precomputed FloodAdapt (SFINCS+FIAT) impact lookup table into building-level damage time series and adaptation decisions under an SLR scenario.
setup_lookup_table.py (stage 1), abm_simulator.py (stage 2), lookup_utils.py, coupling_config.py, dynamo_decision_bridge.py, example/*.py, tests/
DYNAMO-M(c:\repos\DYNAMO-M)
Global honeybees/Mesa-style ABM of coastal household migration & adaptation. Supplies the Subjective Expected Utility (SEU) decision science that replaces FloodAdapt-ABM's naive rule.
decision_module.py, agents/*, hazards/flooding/flood_risk.py, government_agent.py, docs/coupling_architecture.md, docs/adaptation_decisions_complete.md
The two stages of FloodAdapt-ABM share exactly one interface: the NetCDF lookup table (dims object_id x slr x strategy x event; vars total_damage, inun_depth; attrs max_pot_dmg, freq, primary_object_type). This clean seam is the backbone of the whole coupling and must remain stable.
## 2. Objective of the coupling & MVP scope
The Minimum Viable Product replaces FloodAdapt-ABM's simple reactive rule ("if damage/max_pot_dmg > 0.3 then floodproof") with DYNAMO-M's SEU household decision framework, while KEEPING FloodAdapt-ABM's own elevation assumption (an adapted household's damages are read from the 'floodproof_all_0' strategy in the lookup table).
Deliberate boundaries of the MVP (validated against coupling_architecture.md §MVP):
IN: households = residential buildings only (substring 'RES'); dry flood-proofing vs do-nothing; SEU with CRRA utility, exceedance-curve integration, risk-perception decay, affordability cap, loan amortisation, adaptation lifespan (75 y).
OUT (future extensions): insurance (calcEU_insure), migration + gravity model, government/dike CBA agent, population/GDP dynamics, variable floodproof height.
BYPASSED by design: DYNAMO-M's internal hazard physics (interpolate_water_levels, dike overtopping, GLOFRIS scaling). All flood depths and damages come from the SFINCS/FIAT lookup table.
Hard requirement (coupling_architecture.md §1.3): for the SEU exceedance integral to be valid, the stage-1 EventSet should be a true return-period set (e.g. [2,5,10,25,50,100,250,500,1000] yr). If a non-RP set is used, a per-household damage-sorted exceedance curve must be derived first.
## 3. Current state assessment (what exists today)
Component
Status
Notes
Stage-1 lookup table (setup_lookup_table.py)
Done / stable
Drives SFINCS+FIAT; unchanged by coupling. EventSet must be RP-based.
Stage-2 threshold simulator (abm_simulator.py)
Done / stable
Used by 2_simulate_adaptation.ipynb. Public API must not break.
lookup_utils.py (shared interpolation kernel)
Done
Single definition of SLR->damage interpolation, used by both paths. First correct refactor step.
coupling_config.py (@dataclass config)
Done
NetCDFMappingConfig, DecisionConfig, CouplingConfig. See §7 for doc/code drift to fix.
dynamo_decision_bridge.py (ported SEU)
Done (validated by 41 unit tests)
prepare_damage_arrays, compute_expected_annual_damages, update_flood_experience, evaluate_decisions, get_current_damages + _calc_eu_* / _iterate_through_flood kernels. Self-contained (no DYNAMO-M import).
example/run_coupled_example.py & run_trace_manual_check.py
Prototype
Manual year loop + inline event drawing. Explicitly marked as throwaway scaffolding to be pulled into the core package. Contains a latent crash (see §7).
Full MVP wiring into ABMSimulator
Pending
ABMSimulator does not yet own/call the bridge; threshold block not yet swapped; eu_history/is_residential not yet added.
Mesa-native step() integration
Not started
Long-term target for true model integration.
## 4. Proposed target architecture (Strategy Pattern)
Both ABMSimulator and DynamoDecisionBridge are the SAME simulation engine with different decision rules; everything else (NetCDF load, interpolation, stochastic event draw, state tracking, the year loop) is duplicated. The endorsed resolution (from the docx) is a single SimulationEngine with a pluggable DecisionRule.
SimulationEngine (single class)  |-- NetCDF loading (via CouplingConfig / NetCDFMappingConfig)  |-- Damage interpolation           -> lookup_utils.py  (DONE)  |-- Stochastic event draw (Bernoulli + max_events cap)  |-- State tracking (is_adapted, damage_history, flood_timer, time_adapted)  +-- decision_rule: DecisionRule    <- pluggable          |-- ThresholdRule   (dmg/max_pot_dmg > 0.3)   [legacy ABMSimulator]          |-- SEURule         (DYNAMO-M utility math, ported)   [current bridge]          +-- DynamoLiveRule  (calls live DYNAMO-M DecisionModule)                  |-- 4a: thin adapter / SEU parity oracle   [near-term, in-MVP]                  +-- 4b: full Mesa model.step() driving      [post-MVP]
The DecisionRule interface (stateless, vectorised, NumPy-first):
class DecisionRule:    def __init__(self, config: DecisionConfig):   # r, sigma, loan_duration,        ...                                        # expenditure_cap, amenity_weight, ...    def should_adapt(self,        agent_state: AgentState,      # wealth, income, risk_perception, flood_timer,                                      #   is_adapted, time_adapted        damages_no_adapt: np.ndarray, # (n_agents, n_events)  full catalog @ SLR_t, no measures        damages_adapt: np.ndarray,    # (n_agents, n_events)  full catalog @ SLR_t, floodproofed        event_freqs: np.ndarray,      # (n_events,)  exceedance probs (= 1/RP)        max_pot_dmg: np.ndarray,      # (n_agents,)        adaptation_costs: np.ndarray, # (n_agents,)  annualised loan repayment    ) -> np.ndarray:                  # (n_agents,) bool        ...
Interface change (to make DynamoLiveRule pluggable). The signature is widened versus the 20260707 draft: (1) AgentState must now carry risk_perception (not just flood_timer), because DYNAMO-M's calcEU_* consume it directly; (2) the rule receives BOTH per-event damage matrices at the current SLR (no-adapt and adapt) rather than a single matrix plus the realised damage, because the SEU is ex-ante and calcEU_adapt / calcEU_do_nothing each integrate a full exceedance curve; (3) adaptation_costs (annualised loan repayment) is passed explicitly; (4) decision parameters (r, sigma, loan_duration, expenditure_cap, amenity_weight) are injected once via the constructor from DecisionConfig. ThresholdRule ignores the extra arguments, so backward compatibility is preserved.
What gets unified (from the docx, cross-checked against code):
Concern
Before (today)
After (target)
Damage interpolation
2 implementations
lookup_utils, called by engine (DONE)
Event drawing
ABMSimulator + inline example code
1 method in SimulationEngine
State tracking
2 separate array sets
1 standardised AgentState container
Year loop
nested loops / manual demo loop
single run() / step() in engine
Decision logic
hardcoded in classes
pluggable DecisionRule
Design principles to enforce:
Single Responsibility: the engine owns time & data; the rule owns behaviour. No FloodAdapt or DYNAMO-M imports inside the rule kernels.
Open/Closed: new science (insurance, migration, live DYNAMO-M) arrives as a new DecisionRule, not by editing the engine.
Backward compatibility: ThresholdRule reproduces legacy ABMSimulator results bit-for-bit so existing notebooks keep working.
Vectorisation & JIT: keep _iterate_through_flood @njit-able; no per-household Python loops in hot paths.
## 5. Connection & coupling design (one timestep)
Per (sequence, year) the engine performs the following; the REPLACED block is the only decision-specific part and is delegated to the rule.
## 1. year_events   = sequences[s][t]                         # Bernoulli draw + cap2. prepare damages @ SLR_t (cubic/linear via lookup_utils):     D_no   = damage_matrix_no_measures[:, :, t]           # (n_hh, n_events)     D_fp   = damage_matrix_floodproof[:, :, t]3. realised  = where(is_adapted, D_fp, D_no) over occurring events   total    = sum_events(realised);  was_flooded = total > 0   --- REPLACED (decision rule) -------------------------------------------4. update_flood_experience(was_flooded)   # flood_timer, risk_perception decay5. adapt = rule.should_adapt(state, total, D_full, freqs, max_pot_dmg)     SEURule: EU_do_nothing = INT U(NPV_no_action(p)) dp              EU_adapt      = INT U(NPV_dryproof(p) - cost) dp  (afford. inside)              adapt = (EU_adapt > EU_do_nothing) & ~is_adapted     lifespan reset: time_adapted >= 75 -> un-adapt & re-decide   ------------------------------------------------------------------------6. is_adapted |= adapt;  time_adapted bookkeeping7. store damage_history[s,:,t], adapted[s,:,t]
Coupling contract (must stay stable across refactors):
Direction
Payload
Shape
ABM -> rule
expected_damages_no_adapt / _adapt @ SLR_t
(n_events, n_hh)
ABM -> rule
p_floods (= freq = 1/RP)
(n_events,)
ABM -> rule
property_value (max_pot_dmg)
(n_hh,)
ABM -> rule
is_adapted, time_adapted, was_flooded
(n_hh,)
rule -> ABM
adapt_decision
(n_hh,) bool
rule -> ABM
risk_perception, EU_adapt, EU_do_nothing (diagnostics)
(n_hh,)
Time progression: in production the manual demo loop is discarded. Time is driven natively - first by a SimulationEngine.run()/step(), and ultimately by DYNAMO-M's Mesa model.step() cycle calling the bridge each tick. Keeping the rule interface stable is what makes this migration non-breaking, and also preserves the long-term reverse-coupling vision (DYNAMO-M consuming external flood damages).
## 6. Issues found
Sev.
Issue
Location
Action
Low
Hardcoded INITIAL_YEAR=2020 / TIME_HORIZON=30 in the demo.
run_coupled_example.py:52
Derive from FloodAdapt SLR projection trajectory metadata.
## 7. Recommended development roadmap (phased)
Guiding principle (endorsed in the docx): unify the plumbing, keep the decision logic pluggable - but validate the science BEFORE the big refactor, not before. The ThresholdRule path must never regress existing notebooks.
Phase 1 - Validate the SEU science (highest priority)
Run the coupling_architecture.md §12.1 validation battery: (1) degenerate risk_perception=0 => adaptive == baseline; (2) compare adoption curve vs 0.3-threshold on Charleston at small no_seq (~10); (3) sensitivity sweeps over risk_aversion {0.5,1,2} and risk_perc_max {1,2,4}; (4) affordability => zero adoption; (5) lifespan > 75 y => cohort re-decides.
Cross-check bridge SEU outputs against DYNAMO-M's native calcEU_adapt/calcEU_do_nothing on a shared reference scenario (the docx 'Next' gate). Document numerical agreement tolerances.
Gate: do NOT start Phase 3 until this passes and the team agrees the math is correct.
Phase 2 - Consolidate event & time logic into the core
Move Bernoulli event drawing + max_events cap out of the example scripts into a single core method; implement RANDOM selection from the drawn pool.
Add a native run()/step() so time progression is owned by the engine, not the demo loop. Derive INITIAL_YEAR/TIME_HORIZON from FloodAdapt SLR metadata.
Harden read_impacts_dataset with an object_id-indexed accessor.
Phase 3 - Unified SimulationEngine + DecisionRule (Strategy)
Introduce SimulationEngine, AgentState, and the DecisionRule ABC.
Refactor ThresholdRule and SEURule onto the interface; keep ABMSimulator and DynamoDecisionBridge as thin backwards-compatible wrappers so no notebook API breaks.
Add eu_history and is_residential to the engine state; regression-test ThresholdRule against pre-refactor damage_history.
Implement persistent time_adapted tracking and lifespan-dryproof reset logic. Gap finding from Phase 1 verification 5: native DYNAMO-M resets adapt=0 when an agent's floodproofing age reaches lifespan_dryproof (default 75 years, from settings.yml). This logic lives in coastal_nodes.py:2221–2227 and is NOT exported by DecisionModule. The bridge currently hard-codes time_adapted=0 (dynamo_decision_bridge.py:326), so adapted households never age and never reset – they stay adapted forever. To match native DYNAMO-M multi-generational dynamics: (a) add time_adapted field to AgentState (initially 0); (b) add lifespan_dryproof parameter to DecisionConfig (default 75); (c) increment time_adapted yearly for each adapted agent; (d) in should_adapt, compute reset_mask = time_adapted >= lifespan_dryproof, reset adapt=False for those agents, and allow them to re-decide. This is essential for long-term ABM realism, because households that adapt then un-adapt (floodproofing fails, or becomes uneconomical later) can re-evaluate their strategy. Regression test: running a long-horizon ABM should show adaptation turnover; a cohort adapted at year 10 should mostly have unadapted by year 85+.
Phase 4a - Live DYNAMO-M SEU parity (near-term, in-MVP)
Add DynamoLiveRule: a thin adapter that imports DYNAMO-M's DecisionModule and calls calcEU_adapt / calcEU_do_nothing with the same arrays the bridge already assembles. Primary purpose: a parity oracle guaranteeing the ported SEURule has not drifted from upstream (this is the mechanism that executes the Phase 1 cross-check gate).
Feasibility (verified in source): calcEU_adapt (decision_module.py:114-368) and calcEU_do_nothing (369-471) are near-pure array functions - they depend only on the @njit static IterateThroughFlood and self.error_terms_stay, not on self.model / self.agents. No full Mesa model is required to call them.
Obstacles to handle: (1) the module-level import 'from gravity_models.read_gravity_model import read_gravity_model' (decision_module.py:3) only resolves with CWD=DYNAMO-M/DYNAMO-M - guard it as an OPTIONAL dependency so FloodAdapt-ABM still runs Threshold/SEU when DYNAMO-M is absent; (2) DecisionModule.__init__(agents, model) and sample_error_terms need a minimal stub model exposing settings, random_module, args; (3) for bit-parity set error_interval=0 (error_terms_stay=1), align the RNG stream, and keep amenity_value=0.
p_floods contract: both live methods np.sort(p_floods) ascending, cap perceived probability at 0.998, and np.trapz over [0,1] - so the coupling_architecture.md §1.3 return-period EventSet requirement is mandatory for the live rule too.
Phase 4b - Full Mesa-native integration (post-MVP)
Instantiate the DYNAMO-M SLRModel and populate CoastalNode household arrays from the FloodAdapt lookup table; drive ticks natively from model.step().
Heavier lift: requires bridging DYNAMO-M's DataDrive-based initialisation, geom_id conventions (_flood_plain), spin-up, and low-memory array handling. Keep OUT of the MVP; schedule only after Phase 4a proves parity.
Phase 4b-full roadmap (detailed next steps)
Phase 5 - Extending decision rules
Step 1 — Pin honeybees/mesa versions: Verify compatibility with DYNAMO-M pinned versions. Effort: 2–4 hrs. Risk: Low. Gate: Import succeeds.
Step 2 — Populate SLRModel init: config_path, settings_path, geojson study_area, args; instantiate Data, FloodRisk, CoastalAmenities. Effort: 4–6 hrs. Risk: Medium. Gate: SLRModel() succeeds.
Step 3 — Write lookup-table adapter (THE new artefact): Map object_id ↔ CoastalNode, property_value ↔ node.wealth, per-event damages → node arrays. Effort: 6–10 hrs. Risk: Medium. Gate: 4b-scaffold reproduces bit-for-bit.
Step 4 — Route adapt decisions: CoastalNode.step() → DynamoLiveRule.should_adapt → node state. Close the coupling loop. Effort: 4–8 hrs. Risk: Medium. Gate: Native arrays record decisions.
Step 5 — Integrate sub-systems: Gravity CWD, spin_up_flag, low-memory .npz, geom_id '_flood_plain', reporter. Effort: 4–8 hrs. Risk: Medium–High. Gate: All sub-steps run.
Step 6 — Execute 4b-full gate: 4b-full ≡ 4b-scaffold on native CoastalNode population. Bit-parity proof under real Mesa. Effort: 2–4 hrs. Risk: Low. Gate: Bit-parity PASS.
Total: 20–40 hrs. Infrastructure integration, no new science. The lookup-table adapter is the only new modelling component; all downstream decision logic is already frozen and validated.
Extend beyond MVP: insurance (calcEU_insure), migration + gravity model, government/dike CBA - each as a new rule/agent, not engine surgery.
Phase gate summary
Phase
Deliverable
Exit criterion
0
Green examples + reconciled config
Both demos run; 41 tests pass
1
Validated SEU
§12.1 battery passes; SEU == DYNAMO-M within tol.
2
Core event+time engine
No decision logic left in example scripts
3
SimulationEngine + rules
ThresholdRule reproduces legacy output
4a
Live DYNAMO-M SEU parity (in-MVP)
calcEU_* parity within tol.; live import optional/guarded
4b
Full Mesa-native integration (post-MVP)
SLRModel.step() drives CoastalNode populations from the lookup table
5
Extending decision rules
calcEU_insure, … .
## 8. Consolidated, prioritised TODO backlog
Merged from the 20260707 docx TODO table and in-code TODO markers.
Pri
Task
Source
Phase
P0
Fix cfg.environment.max_slr crash in demo summary
code §7
0
P0
Reconcile DecisionConfig docstring vs defaults
code §7
0
P1
Validate SEU vs DYNAMO-M on reference scenario
docx roadmap
1
P1
Run §12.1 validation battery
coupling_arch
1
P2
Replace inline _simulate_year_events with core generator
docx / run_coupled_example.py:147
2
P2
Refactor Bernoulli + cap into core; random pool selection
docx / both examples
2
P2
Refactor manual year loop into native step()
docx / run_coupled_example.py:328
2
P2
Derive INITIAL_YEAR/TIME_HORIZON from SLR metadata
run_coupled_example.py:52
2
P2
Robust object_id-indexed impacts accessor
setup_lookup_table.py:215
2
P3
SimulationEngine + DecisionRule (Threshold, SEU)
docx
3
P3
Widen DecisionRule / AgentState (add risk_perception, both damage matrices, adaptation_costs; inject DecisionConfig)
feasibility review
3
P4a
Live DYNAMO-M DecisionModule as parity oracle (thin adapter, optional guarded import)
feasibility review / decision_module.py:114-471
4a
P4b
Full Mesa-native agents/environment + model.step() driving
docx
4b
Go/No-Go decision & execution strategy (Phase 2 + 3)
Status (2026-07-08): Phase 0 (stabilise) and Phase 1 (validate SEU) are COMPLETE — the §12.1 battery passes and the ported SEU matches native DYNAMO-M within tolerance (worst relative EU error 4.2e-7, tol 1e-4; see seu_verification_tests/). Phases 2 and 3 are GO.
Recommendation: execute Phase 2 and Phase 3 TOGETHER, with two hard-stop gates. Rationale: Phase 2 builds the engine plumbing and Phase 3 plugs in the pluggable rules; splitting them leaves an awkward intermediate state and forces double refactoring. Doing both as one unit gives a single API evolution (one clean transition for notebook users) and faster convergence (~7–10 days total).
Gate 1 (end of Phase 2 — hard stop): capture a pre-refactor baseline, then confirm ThresholdRule damage histories match bit-for-bit (rtol=1e-6). Do NOT start the Phase 3 decision-rule refactor until this passes.
Gate 2 (end of Phase 3 — hard stop): re-run the full §12.1 V1–V6 validation battery on the new SimulationEngine + SEURule — all must pass (no science regression) — and confirm 2_simulate_adaptation.ipynb runs unchanged. If either gate fails, halt and debug within that phase before proceeding. Keep a pre_phase3_baseline snapshot so any regression can be diffed quickly.
Phase 2 task breakdown
P2.1 Extract unified event-drawing logic — create SimulationEngine._draw_year_events() (Bernoulli + max_events cap, RANDOM pool selection); both example scripts call this one method. Source: run_coupled_example.py:147, run_trace_manual_check.py:182.
P2.2 Add native run()/step() — time progression owned by the engine, not the demo loop; derive INITIAL_YEAR/TIME_HORIZON from FloodAdapt SLR projection metadata (not hardcoded 2020/30).
P2.3 Harden read_impacts_dataset — add an explicit object_id-indexed accessor + alignment assertions. Source: setup_lookup_table.py:215.
P2.4 (GATE 1) Regression-test ThresholdRule — run both example scripts on the full Charleston table; damage_history / baseline_damage_history / floodproofed arrays must be bitwise identical to the pre-refactor baseline (rtol=1e-6).
Phase 3 task breakdown
P3.1 Create AgentState dataclass (wealth, income, risk_perception, flood_timer, is_adapted, time_adapted).
P3.2 Implement DecisionRule ABC with the widened should_adapt(agent_state, damages_no_adapt, damages_adapt, event_freqs, max_pot_dmg, adaptation_costs) signature.
P3.3 Refactor ThresholdRule onto the interface (dmg/max_pot_dmg > 0.3); output must match the Phase-2 baseline exactly.
P3.4 Refactor SEURule onto the interface (wrap _calc_eu_adapt/_calc_eu_do_nothing); the V6 native cross-check must still pass (rel err < 1e-4).
P3.5 Refactor SimulationEngine core — single year loop orchestrating draw → prepare damages → update_flood_experience → rule.should_adapt() → state update → store history. ABMSimulator and DynamoDecisionBridge become thin backwards-compatible wrappers.
P3.6 Implement persistent time_adapted tracking + lifespan-dryproof reset (Phase-1 V5 gap): add lifespan_dryproof to DecisionConfig (default 75), increment time_adapted yearly for adapted agents, and reset adapt=False when time_adapted >= lifespan_dryproof so cohorts re-decide. Source: coastal_nodes.py:2221–2227.
P3.7 Add eu_history and is_residential diagnostics to engine state.
P3.8 Ensure backward-compat wrappers — no changes to 2_simulate_adaptation.ipynb or existing calling code; public API stable.
P3.9 (GATE 2) Re-run the full V1–V6 validation battery on the new engine — all must pass before Phase 3 is considered done.
Dependency & sequencing
Phase 2 order: P2.1 → {P2.2, P2.3} → P2.4 (Gate 1). Phase 3 order: {P3.1, P3.2} → P3.5 → {P3.3, P3.4, P3.6, P3.7} → P3.8 → P3.9 (Gate 2). P3.5 (SimulationEngine core) is the pivot both rules depend on; P3.9 depends on P3.6 (lifespan) and P3.8 (wrappers).
## 9. Definition of done & alignment with the objective
The proposed steps stay strictly inside the validated MVP objective: DYNAMO-M science as the decision engine inside FloodAdapt-ABM, damages sourced from the SFINCS/FIAT lookup table, physics bypassed, households-only, dry-proofing vs do-nothing. The refactor changes structure, never the agreed behaviour.
Science validated: SEU reproduces DYNAMO-M and passes the §12.1 battery.
Backwards compatible: ThresholdRule reproduces legacy ABMSimulator output; 2_simulate_adaptation.ipynb keeps working.
Single source of truth: one interpolation kernel, one event generator, one time loop, one pluggable decision interface.
Docs synchronised: file paths, method names, defaults, and event-cap semantics consistent across AGENTS.md, coupling_architecture.md, and code.
Extension-ready: insurance, migration, and government agents can be added as new rules without touching the engine.
Sev.
Issue
Location
Action
Med
Inline _simulate_year_events + Bernoulli/cap logic duplicated across both example scripts.
run_coupled_example.py:147, run_trace_manual_check.py:182
DONE: Move into core (SimulationEngine/bridge) as the single event generator.
Med
read_impacts_dataset assigns arrays assuming row order == object_id order (silent misalignment risk).
setup_lookup_table.py:215
Add an explicit object_id-indexed accessor; assert alignment.
