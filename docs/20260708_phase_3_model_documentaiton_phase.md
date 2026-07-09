# FloodAdapt-ABM × DYNAMO-M Coupling

> **Provenance (HYG.4, 2026-07-09):** converted from `20260708_phase_3_model_documentaiton_phase.docx` so the design record is diffable in-repo. Text extracted from the .docx XML; original heading levels and table layouts are flattened (numbered section lines promoted to headings heuristically). The .docx remains the typeset original.

Phase 4a — Live DYNAMO-M SEU Parity (Model Documentation)
DynamoLiveRule: the native-DYNAMO-M parity oracle for the ported SEU kernels
Date: 2026-07-08   ·   Status: Phase 4a complete   ·   90/90 tests passing (11 new)   ·   Parity gate: PASS
## 1. Executive Summary
Phase 4a adds DynamoLiveRule, a pluggable decision rule that drives the native DYNAMO-M DecisionModule (calcEU_do_nothing / calcEU_adapt) instead of the pure-NumPy kernels ported into the bridge. Its primary purpose is to serve as an automated parity oracle: running the ported SEURule and the live DynamoLiveRule on an identical agent state must yield the same expected utilities and identical adaptation decisions. This executes the Phase-1 'cross-check native' gate as a one-line, CI-runnable test.
Delivered in this phase:
DynamoLiveRule — a pluggable DecisionRule that calls upstream DYNAMO-M with no full Mesa model.
Optional guarded import — package still imports and runs ThresholdRule/SEURule when DYNAMO-M is absent.
Test suite — 11 new tests (availability, parity gate, engine integration); 90/90 total pass.
Verification — worst-case EU abs diff 1.9e-6, rel 4.8e-7 across 5 configs; decisions identical.
## 2. Position in the Strategy-Pattern Architecture
The unified SimulationEngine owns time, data and state; a pluggable DecisionRule owns behaviour. Phase 4a adds a third concrete rule alongside the legacy heuristic and the ported SEU science.
                       DecisionRule  (ABC, one method: should_adapt)
                              |
      +-----------------------+------------------------+
      |                       |                        |
 ThresholdRule            SEURule                 DynamoLiveRule           <- Phase 4a
 (legacy 0.3 rule)   (DYNAMO-M SEU, ported)   (calls NATIVE DecisionModule)
                     _core kernels:            calcEU_do_nothing / calcEU_adapt
                     _calc_eu_do_nothing         (upstream decision_module.py)
                     _calc_eu_adapt
      \_____________________  ____________________________/
                            \/
              SimulationEngine(ds, config, decision_rule=<any of the above>)
                  owns: NetCDF load, interpolation, event draw, state, run()/step()
SEURule and DynamoLiveRule compute the SAME science by two independent code paths (a hand-ported NumPy version vs. the original upstream code). Comparing them is what proves the port is faithful.
## 3. Class Reference
Class / symbol
Module
Role
DecisionRule (ABC)
decision_rule.py
Interface: should_adapt(...) -> bool mask
ThresholdRule
decision_rule.py
Legacy ex-post 0.3 heuristic
SEURule
decision_rule.py
Ported DYNAMO-M SEU (MVP default)
DynamoLiveRule
dynamo_live_rule.py
Live native DYNAMO-M parity oracle (Phase 4a)
DynamoMNotAvailable
dynamo_live_rule.py
Raised if native module can't import
DYNAMO_M_AVAILABLE
dynamo_live_rule.py
Bool flag, lightweight import-time probe
SimulationEngine
simulation_engine.py
Time/data/state owner; hosts any rule
Shared should_adapt signature (all rules):
def should_adapt(
    self,
    agent_state,        # wealth, income, risk_perception, flood_timer,
                        #   is_adapted, time_adapted
    damages_this_year,  # (n_agents,)          realised damage [ex-post: ThresholdRule]
    damages_no_adapt,   # (n_agents, n_events) catalogue @ SLR_t, no measures
    damages_adapt,      # (n_agents, n_events) catalogue @ SLR_t, floodproofed
    event_freqs,        # (n_events,)          exceedance prob = 1/RP
    max_pot_dmg,        # (n_agents,)
    adaptation_costs,   # (n_agents,)          annualised loan repayment
) -> np.ndarray:        # (n_agents,) bool     newly-adapt this year
## 4. How DynamoLiveRule Works
DynamoLiveRule instantiates the native DecisionModule against a minimal stub model, then on each call assembles the DYNAMO-M-convention arrays (events-first damage matrices) and invokes the upstream methods.
  DynamoLiveRule.should_adapt(state, ...)
  ------------------------------------------------------------------
  1. D_no = damages_no_adapt.T   (n_events, n_agents)   [DYNAMO-M convention]
     D_fp = damages_adapt.T
  2. error_terms_stay = ones(n_agents)     # error_interval == 0 (bit-parity)
     dm.error_terms_stay = error_terms_stay
  3. EU_dn = dm.calcEU_do_nothing(geom_id, n_agents, wealth, income,
                 amenity_value, amenity_weight, risk_perception,
                 expected_damages=D_no, adapted, p_floods, T, r, sigma)
  4. EU_ad = dm.calcEU_adapt(geom_id, n_agents, wealth, income,
                 expendature_cap, amenity_value, amenity_weight, risk_perception,
                 expected_damages_adapt=D_fp, adaptation_costs, time_adapted,
                 loan_duration, p_floods, T, r, sigma)
  5. newly_adapted = (EU_ad - EU_dn > 0) & ~is_adapted
Feasibility (verified in upstream source):
calcEU_adapt (decision_module.py:114-368) and calcEU_do_nothing (369-471) depend only on the @njit static IterateThroughFlood and self.error_terms_stay — NOT on self.model / self.agents. No Mesa model, gravity model, or agent population is needed.
The stub model is a SimpleNamespace exposing settings['decisions']['error_interval'] and random_module.random_state; agents=None (only load_gravity_models uses it, which we never call).
## 5. Optional / Guarded Import
The native module's top-level import of gravity_models only resolves when DYNAMO-M/DYNAMO-M is on sys.path. The dependency is therefore optional and resolved defensively, so FloodAdapt-ABM keeps working without DYNAMO-M.
  import floodadapt_abm
        |
        v
  DYNAMO_M_AVAILABLE  <-- _probe_availability()   (LIGHTWEIGHT)
        |                   checks decision_module.py + gravity_models/ EXIST
        |                   (no import, no sys.path change)
        v
  DynamoLiveRule(config[, dynamo_path])            (CONSTRUCTION)
        |
        v
  load_native_decision_module(path)
        |   path = dynamo_path  or  $DYNAMO_M_PATH  or  c:\repos\DYNAMO-M\DYNAMO-M
        |   sys.path.append(path)                  (append, never shadow)
        |   import decision_module -> DecisionModule
        +-- on failure -> raise DynamoMNotAvailable  (ThresholdRule/SEURule still fine)
Symbol
Meaning
DYNAMO_M_AVAILABLE
True if decision_module.py + gravity_models/ found (no import)
resolve_dynamo_path(p)
p -> $DYNAMO_M_PATH -> default conventional path
load_native_decision_module
Appends path, imports, returns DecisionModule class
DynamoMNotAvailable
Typed ImportError raised on construction if absent
## 6. Bit-Parity Configuration & the Gate
For an exact cross-check both rules run with error_interval=0 (so error_terms_stay==1, deterministic) and amenity_value=0. Under that configuration the only differences are float32 rounding inside the trapezoidal EU integral; the sign of EU_adapt - EU_do_nothing is preserved, so the boolean decisions are identical.
Verification result (5 configurations, Charleston-like sample):
Case
sigma
decisions identical
EU max |abs| diff
-inf masks match
baseline_sigma1
1.0
True
9.5e-07
True
power_utility_sigma2
2.0
True
1.7e-13
True
mixed_adapted_cohort
1.0
True
1.9e-06
True
affordability_locked
1.0
True
0.0e+00
True
large_event_catalogue
1.0
True
1.9e-06
True
Gate PASS: all decisions identical; worst-case EU max abs diff 1.9e-6, max rel diff 4.8e-7 — inside the float32 tolerance (abs ≤ 1e-3, rel ≤ 1e-4). Full report: progress_todos/20260708_phase4a_live_dynamo_parity/ (parity_report.md + parity_metrics.json).
## 7. Usage Examples (Practical)
### 7.1  Run the engine with the live rule
from floodadapt_abm import (
    SimulationEngine, CouplingConfig, DynamoLiveRule, DYNAMO_M_AVAILABLE,
)
import xarray as xr, numpy as np
ds  = xr.open_dataset("charleston_lookup_table.nc")
cfg = CouplingConfig()                       # error_interval=0, amenity=0 (parity)
if DYNAMO_M_AVAILABLE:
    live   = DynamoLiveRule(cfg.decision)    # or dynamo_path=r"...\DYNAMO-M\DYNAMO-M"
    engine = SimulationEngine(ds=ds, config=cfg, decision_rule=live)
    res    = engine.run(np.linspace(0, 1.5, 30), no_seq=10, seed=42, track_eu=True)
    print(res["adoption_fraction"].mean(axis=0))   # expected adoption per year
else:
    print("DYNAMO-M not available; use SEURule (the validated port).")
### 7.2  Assert parity (the CI gate, condensed)
from floodadapt_abm import SimulationEngine, CouplingConfig, SEURule, DynamoLiveRule
import numpy as np
cfg    = CouplingConfig()
engine = SimulationEngine(ds=ds, config=cfg)
state  = engine.state
D_no, D_fp = engine.prepare_damages(1.0)
amenity    = engine._data.amenity_value
kw = dict(agent_state=state, damages_this_year=np.zeros(state.n_agents, "float32"),
          damages_no_adapt=D_no, damages_adapt=D_fp, event_freqs=engine._event_freqs,
          max_pot_dmg=engine.max_pot_dmg, adaptation_costs=engine._annual_adapt_cost)
a_seu  = SEURule(cfg.decision, amenity_value=amenity).should_adapt(**kw)
a_live = DynamoLiveRule(cfg.decision, amenity_value=amenity).should_adapt(**kw)
assert np.array_equal(a_seu, a_live)          # identical decisions -> port is faithful
### 7.3  Point the rule at a custom DYNAMO-M checkout
# Option A: constructor argument
live = DynamoLiveRule(cfg.decision, dynamo_path=r"D:\code\DYNAMO-M\DYNAMO-M")
# Option B: environment variable (picked up by resolve_dynamo_path)
#   set DYNAMO_M_PATH=D:\code\DYNAMO-M\DYNAMO-M
live = DynamoLiveRule(cfg.decision)
## 8. Tests
tests/test_dynamo_live_rule.py (11 tests, auto-skips when DYNAMO-M absent):
Guarded import — availability flag is bool; probe agrees with flag; path resolution (argument > env > default); missing path raises DynamoMNotAvailable.
Parity gate — SEURule vs DynamoLiveRule decisions identical + EU allclose for sigma∈{1,2}, mixed adapted cohort, and affordability-locked cases.
Engine integration — live rule runs inside SimulationEngine.run(); full-trajectory adopted_history identical to the SEURule engine on the same seed.
pytest tests/test_dynamo_live_rule.py -v      # 11 passed (or skipped if no DYNAMO-M)
pytest tests/ -q                              # 90 passed
## 9. Scope Boundary (4a vs 4b)
Concern
Phase 4a (this doc, in-MVP)
Phase 4b (post-MVP)
Decision math
Native calcEU_* via DynamoLiveRule
Same, driven by Mesa
Time ownership
SimulationEngine.run()/step()
DYNAMO-M model.step()
Agent population
FloodAdapt lookup-table agents
Native CoastalNode arrays
Gravity / migration
Not used (never called)
load_gravity_models, allocation
Purpose
Parity oracle / drift guard
Full native integration
Keeping the DecisionRule contract stable is what makes the 4a → 4b migration non-breaking: 4b inverts time ownership to Mesa while reusing the same rule boundary.
## 10. Key Files & Artifacts
Path
Purpose
floodadapt_abm/dynamo_live_rule.py
DynamoLiveRule + guarded import helpers
tests/test_dynamo_live_rule.py
11 Phase-4a tests (parity gate)
progress_todos/20260708_phase4a_live_dynamo_parity/
parity_report.md + parity_metrics.json
AGENTS.md § 'Phase 4a'
Operational guide + reproduction commands
decision_module.py:114-471 (DYNAMO-M)
Native calcEU_adapt / calcEU_do_nothing
— End of Phase-4a model documentation —
