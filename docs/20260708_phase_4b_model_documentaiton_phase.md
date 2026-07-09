# FloodAdapt-ABM × DYNAMO-M Coupling

> **Provenance (HYG.4, 2026-07-09):** converted from `20260708_phase_4b_model_documentaiton_phase.docx` so the design record is diffable in-repo. Text extracted from the .docx XML; original heading levels and table layouts are flattened (numbered section lines promoted to headings heuristically). The .docx remains the typeset original.

Phase 4b — Mesa-native Driving (Model Documentation)
Inverting time ownership: model.step() ticks drive the shared decision kernels
Date: 2026-07-08   ·   Status: Phase 4b (scaffold) complete   ·   104/104 tests passing (14 new)   ·   Bit-parity gate: PASS
## 1. Executive Summary
Phase 4b changes *who owns time*. In Phases 3 and 4a the year loop lives inside SimulationEngine.run(); in Phase 4b a small model advances one tick at a time via FloodAdaptSLRModel.step(), mirroring the native DYNAMO-M SLRModel.run_model() (while True: self.step()). The decision science is untouched: the same DecisionRule.should_adapt seam is called, only from a different driver.
Delivered in this phase:
FloodAdaptSLRModel — a framework-free model that mirrors the DYNAMO-M object graph and drives ticks; run_mesa_native() is a drop-in analogue of engine.run().
Non-breaking gate — the tick driver reproduces engine.run() bit-for-bit (SEURule & ThresholdRule, multiple seeds/sequences).
Test suite — 14 new tests (bit-parity, time ownership, object graph, guarded live rule); 104/104 total pass.
Scope — binding the real honeybees SLRModel needs the full DYNAMO-M data ecosystem; documented as the '4b-full' follow-up.
## 2. Why We Mirror DYNAMO-M (Rationale + Feasibility)
The goal of Phase 4b is to prove that FloodAdapt-ABM can hand time ownership to a DYNAMO-M-style Mesa scheduler WITHOUT changing the decision science. We do this with a faithful, dependency-free MIRROR of the native control flow rather than the real honeybees SLRModel. There are four concrete reasons.
Reason 1 - The real native model is not instantiable here.
honeybees and mesa are not installed (import fails on both).
SLRModel.__init__ requires config_path, settings_path, a geojson study_area and a parsed args namespace, then eagerly builds Area(self), Data(self), Agents(self), Reporter(self), FloodRisk and CoastalAmenities (model.py:66-76).
Agents.__init__ constructs Nodes, Beaches, BeachManager, PopulationChange, GDP_change, GovernmentAgent, InsurerAgent and calls decision_module.load_gravity_models() (agents/__init__.py:13-25) - pulling in GLOFRIS flood risk, gravity models, geojson study areas, spin-up, pickling and low-memory .npz scratch folders.
Reason 2 - The decision kernel does NOT need any of that.
Phase 4a already proved (in source) that calcEU_do_nothing / calcEU_adapt depend only on the static @njit IterateThroughFlood and self.error_terms_stay - not on self.model or self.agents. So the *behaviour* we care about is separable from the whole Mesa/honeybees data ecosystem. Mirroring lets us exercise exactly that separable seam.
Reason 3 - We want to isolate ONE variable: time ownership.
If we swapped in the full native stack we would change the driver, the data loading, the agent population source and the RNG all at once - and any numerical difference would be unattributable. The mirror changes ONLY who owns the clock, so a bit-for-bit match against engine.run is a clean proof that time-ownership inversion is non-breaking.
Reason 4 - It matches the endorsed roadmap.
The 20260707 docx explicitly scopes full Mesa-native binding as a 'heavy lift - keep OUT of the MVP; schedule only after Phase 4a proves parity.' The mirror is the in-MVP deliverable that de-risks that later lift.
## 3. Object Graph — Mirroring DYNAMO-M
Each FloodAdapt-ABM class mirrors a native DYNAMO-M counterpart:
Native DYNAMO-M
FloodAdapt-ABM mirror (mesa_native.py)
Role
SLRModel
FloodAdaptSLRModel
Owns time (the clock)
SLRModel.run_model()
FloodAdaptSLRModel.run_model()
while-loop over ticks
SLRModel.step()
FloodAdaptSLRModel.step()
One native tick (one year)
Agents
Agents
Steps each agent group
Agents.regions (Nodes)
CoastalNodePopulation
Vectorised households
CoastalNode arrays
AgentState
wealth/income/risk/adapted...
decision_module
DecisionRule (SEURule/DynamoLiveRule)
Shared decision kernel
  FloodAdaptSLRModel            (owns time: timestep, n_timesteps, rng)
    |-- engine: SimulationEngine    (shared kernel: events, damage, rule, state)
    |-- agents: Agents
    |        +-- regions: CoastalNodePopulation   (households == a view over
    |                       |                        engine.state: AgentState)
    |                       +-- step(): engine.step(year) -> record history
    |-- damage_history / adapted_history / eu_* buffers
    +-- step():        agents.step();  timestep += 1        # one tick
        run_model():   while timestep < n_timesteps: step() # time owned HERE
### 3.1  The corresponding DYNAMO-M processes (what we mirror)
Each mirror method is a 1:1 analogue of a real DYNAMO-M control-flow method. The native excerpts below are the exact processes being mirrored.
Native tick loop - SLRModel.run_model() (model.py:113-127):
def run_model(self):
    self.random_module.reset_all_seeds()
    ...
    while True:                 # <-- TIME IS OWNED HERE
        print(self.current_time)
        self.step()             # one native tick
        self.timestep += 1
        if self.current_time >= self.end_time:
            break
Mirror: FloodAdaptSLRModel.run_model() runs 'while timestep < n_timesteps: self.step()', resetting the RNG per sequence exactly as reset_all_seeds() does upstream.
Native per-tick fan-out - Agents.step() (agents/__init__.py:31-40):
def step(self):
    if self.model.settings['general']['include_ambient_pop_change']:
        self.population_change.step()
    if (not self.model.spin_up_flag or self.model.args.GUI):
        self.GDP_change.step()
    self.beaches.step()
    self.regions.step()          # <-- households (CoastalNodes) decide here
    self.beach_manager.step()
Mirror: Agents.step() delegates to regions.step() only. The MVP coupling models the household adaptation decision, so beaches, government, insurer, population and GDP sub-steps are intentionally out of scope (they belong to Phase 5 as new rules/agents).
Native household step - Nodes.step() (agents/nodes.py:331-360, abridged):
def step(self):
    self.reset_node_attributes()
    ...                                   # population/EAD/amenity snapshots
    all_nodes_with_population = [n for n in self.all_households if n.n > 0]
    for i, node in enumerate(all_nodes_with_population):
        self.model.agents.government.step(node)
        # ... node computes expected damages @ SLR_t and calls
        #     decision_module.calcEU_do_nothing / calcEU_adapt -> adapt/move
Mirror: CoastalNodePopulation.step() calls engine.step(year), which draws events at SLR_t, interpolates damages, and delegates the adapt decision to DecisionRule.should_adapt - the same maths calcEU performs upstream. The vectorised AgentState replaces the per-household node objects.
Native object construction - SLRModel.__init__ / Agents.__init__ (model.py:66-76, agents/__init__.py:13-25):
# SLRModel.__init__
self.area   = Area(self, study_area)
self.data   = Data(self)
self.agents = Agents(self)
self.reporter = Reporter(self)
self.flood_risk = FloodRisk(model=self)
self.coastal_amenities = CoastalAmenities(model=self)
# Agents.__init__
self.regions = Nodes(model, self)
self.beaches = Beaches(model, self)
self.beach_manager = BeachManager(...)
self.population_change = PopulationChange(...)
self.GDP_change = GDP_change(...)
self.decision_module = DecisionModule(model, self)
self.decision_module.load_gravity_models()
self.government = GovernmentAgent(...)
self.insurer = InsurerAgent(...)
Mirror: FloodAdaptSLRModel builds only { engine, Agents(regions= CoastalNodePopulation) }. The bracketed native sub-systems (Data, FloodRisk, gravity, beaches, government, insurer) are exactly the '4b-full' ecosystem deferred to the follow-up in Section 8.
## 4. Time-ownership Inversion (the essence of 4b)
Concern
Phase 3 / 4a
Phase 4b
Loop owner
SimulationEngine.run()
FloodAdaptSLRModel.step() ticks
Per-year kernel
engine.step()
engine.step() (unchanged)
Decision seam
DecisionRule.should_adapt
DecisionRule.should_adapt (unchanged)
Monte-Carlo
outer loop in run()
one model per sequence
Analogue of
—
native SLRModel.run_model()
Because both paths call the identical per-year kernel with the identical RNG stream (default_rng(seed + s) per sequence), the outputs are identical by construction. The change is architectural, not numerical — and that is precisely the property we want to prove.
## 5. The Non-breaking Gate (verification)
run_mesa_native(engine, ...) must equal engine.run(...) bit-for-bit for the same seed / SLR / no_seq. Result (synthetic Charleston-like sample):
Case
rule
no_seq
seed
damage identical
adapted identical
SEURule_seq1_seed0
SEURule
1
0
yes
yes
SEURule_seq3_seed42
SEURule
3
42
yes
yes
SEURule_seq5_seed123
SEURule
5
123
yes
yes
ThresholdRule_seq3_seed7
ThresholdRule
3
7
yes
yes
ThresholdRule_seq5_seed99
ThresholdRule
5
99
yes
yes
Gate PASS: Mesa-native driving reproduces engine.run bit-for-bit in every case. Full report: progress_todos/20260708_phase4b_mesa_native_driving/ (phase4b_report.md + phase4b_metrics.json).
## 6. Usage Examples (Practical)
### 6.1  Drop-in run with Mesa-native time
from floodadapt_abm import SimulationEngine, CouplingConfig, run_mesa_native
import xarray as xr, numpy as np
ds     = xr.open_dataset("charleston_lookup_table.nc")
engine = SimulationEngine(ds=ds, config=CouplingConfig())     # SEURule default
# Time is owned by model.step() ticks, not by engine.run():
res = run_mesa_native(engine, np.linspace(0, 1.5, 30), no_seq=10, seed=42)
res["damage_history"]     # (no_seq, n_agents, n_years)
res["adoption_fraction"]  # (no_seq, n_years)
### 6.2  Drive time by hand, one tick at a time
from floodadapt_abm import SimulationEngine, CouplingConfig, FloodAdaptSLRModel
import numpy as np
engine = SimulationEngine(ds=ds, config=CouplingConfig())
model  = FloodAdaptSLRModel(engine, np.linspace(0, 1.5, 20), seed=42)
model.agents.regions.n         # households (mirrors CoastalNode.n)
model.step()                   # one native tick == one year
print(model.timestep)          # -> 1
model.run_model()              # finish the remaining years (while-loop)
print(model.timestep)          # -> 20 (== n_timesteps)
### 6.3  Prove equivalence (the CI gate, condensed)
import numpy as np
from floodadapt_abm import SimulationEngine, CouplingConfig, run_mesa_native
cfg = CouplingConfig()
native = run_mesa_native(SimulationEngine(ds=ds, config=cfg), slr, no_seq=5, seed=42)
loop   = SimulationEngine(ds=ds, config=cfg).run(slr, no_seq=5, seed=42)
assert np.array_equal(native["adapted_history"], loop["adapted_history"])  # non-breaking
## 7. Tests
tests/test_mesa_native.py (14 tests):
Bit-parity — run_mesa_native == engine.run for damage/adapted/adoption and EU histories (SEURule & ThresholdRule; seeds 0/42/123; no_seq 1/3/5).
Time ownership — model.step() advances exactly one year; run_model() reaches the horizon; result shapes are correct.
Object graph — model.agents.regions is a CoastalNodePopulation whose state IS the engine's live AgentState; stepping mutates it.
Guarded live rule — DynamoLiveRule also reproduces engine.run under Mesa-native time (skipped when DYNAMO-M is absent).
pytest tests/test_mesa_native.py -v      # 14 passed
pytest tests/ -q                         # 104 passed
## 8. Scope Boundary and How Easy 4b-full Will Be
Concern
4b-scaffold (this doc)
4b-full (follow-up)
Time driver
FloodAdaptSLRModel.step()
honeybees SLRModel.step()
Framework
None (pure NumPy mirror)
honeybees / mesa
Agent population
AgentState from lookup table
native CoastalNode arrays
Data ecosystem
Not required
GLOFRIS, gravity, geojson, spin-up
Decision seam
DecisionRule.should_adapt
same (unchanged)
Status
Delivered, gated
Blocked on DYNAMO-M data env
### 8.1  Will the move to 4b-full be easy?
Short answer: the CONTRACT migration is easy and low-risk; the ENVIRONMENT migration is the real work. The scaffold was designed so that the hard part (decision maths + rule interface) is already done and frozen, and only infrastructure wiring remains.
What makes it easy (already de-risked here):
The DecisionRule.should_adapt(...) boundary is unchanged between 4a, 4b-scaffold and 4b-full. DynamoLiveRule already calls the REAL native calcEU functions (Phase 4a), so the science seam is production-proven.
Time-ownership inversion is already proven non-breaking (bit-parity gate). Swapping FloodAdaptSLRModel.step() for the native SLRModel.step() driver does not touch the decision path.
The object graph already mirrors the native names 1:1 (FloodAdaptSLRModel/Agents/CoastalNodePopulation <-> SLRModel/Agents/Nodes), so the port is a rename-and-rewire, not a redesign.
What still takes real effort (the environment lift):
Install and pin honeybees + mesa and reconcile the honeybees current_time/end_time property behaviour noted in model.py:49-57.
Provide config_path, settings_path, a geojson study_area and an args namespace; stand up Data(self), FloodRisk (GLOFRIS inundation) and CoastalAmenities.
Populate native CoastalNode arrays FROM the FloodAdapt lookup table (the reverse-coupling seam): map object_id -> node, property_value -> max_pot_dmg, and per-event damages -> the node's expected-damage arrays. This is the single genuinely new adapter.
Handle spin-up, geom_id '..._flood_plain' conventions, low-memory .npz array paging and gravity-model CWD requirements.
Effort estimate:
Migration task
Effort
Risk
Keep DecisionRule/DynamoLiveRule seam
None (done)
None
Swap driver to native model.step()
Low
Low (gate-proven)
Install/pin honeybees + mesa
Low-Med
Med (version drift)
Lookup-table -> CoastalNode adapter
Medium
Medium
Data/FloodRisk/gravity/spin-up wiring
High
Med-High
Conclusion: because Phase 4a froze the science seam and Phase 4b froze the time-ownership contract, 4b-full is an infrastructure integration exercise (hours-to-days of wiring per sub-system) rather than a re-architecture. The only new modelling artefact is the lookup-table -> CoastalNode adapter; everything downstream of should_adapt is already validated.
Where this is documented: this section is the authoritative record; it is summarised in AGENTS.md (Phase 4b section) and referenced from mesa_native.py, examples_engine/06_mesa_native_driving.py and the examples_engine/README.md.
## 9. Phase 4b-full Next Steps (Post-MVP Roadmap)
With 4b-scaffold gated and frozen, Phase 4b-full is the binding of the real honeybees SLRModel. This is a wiring exercise, not a re-architecture, because the decision science is already validated and the time-ownership contract is proven non-breaking.
### 9.1  Roadmap (effort estimates)
Step
Task
Effort
Risk
Gate
1
Pin honeybees/mesa versions; verify config compatibility.
2-4 hrs
Low
Import test
2
Populate SLRModel: config_path, settings_path, geojson study_area, args namespace; instantiate Data, FloodRisk, CoastalAmenities.
4-6 hrs
Medium
SLRModel() succeeds
3
Write lookup-table adapter: map object_id ↔ CoastalNode, property_value ↔ node.wealth, per-event damages → node arrays. **The ONE new modelling artefact.**
6-10 hrs
Medium
Round-trip reproduce 4b-scaffold
4
Route adapt decisions: CoastalNode.step() → DynamoLiveRule.should_adapt → node state. Close the coupling loop.
4-8 hrs
Medium
Decisions recorded in native array
5
Integrate sub-systems: gravity CWD, spin_up_flag, low-memory .npz paging, geom_id '_flood_plain' filtering, reporter.
4-8 hrs
Medium-High
All sub-step logic runs
6
Execute 4b-full gate: 4b-full ≡ 4b-scaffold (bit-parity on native model).
2-4 hrs
Low
Bit-parity gate PASS
**Total estimate**: 20-40 hrs (infrastructure integration; no new science).
### 9.2  The lookup-table adapter (the centrepiece)
This is the single new modelling artefact. It bridges the FloodAdapt damage lookup (netCDF: object_id, year, event → damage) to the native CoastalNode array structure (node.locations, node.damages_coastal_cells, node.property_value).
# Pseudo-logic (the adapter)
for node in self.agents.regions.all_households:
    if node.geom_id.endswith('flood_plain'):
        object_id = lookup_geom_id_to_object_id(node.geom_id)
        damages = damages_lookup[object_id, :, t]  # per-event @ SLR_t
        node.damages_coastal_cells = damages      # populate native array
        node.property_value = lookup_property_value[object_id]
# Each native step(), calcEU consumes node.damages_coastal_cells
#  and calls: decision_module.calcEU_adapt / calcEU_do_nothing
# (same as Phase 4a DynamoLiveRule, now inside Mesa's loop)
This adapter is also the reverse-coupling seam: flood damages flow FROM FloodAdapt TO DYNAMO-M, and adaptation decisions flow BACK. When 4b-full runs natively, this is the heartbeat of the coupling.
### 9.3  Verification & gate
4b-full must reproduce 4b-scaffold **bit-for-bit** on a deterministic CoastalNode population (same locations, property_values, amenities as the synthetic lookup table used in 4b-scaffold). This is the proof that binding the native model did not introduce numerical errors or logic drift. After 4b-full gate PASS, the coupling is natively Mesa-driven and ready for production use.
## 10. Q&A — Will step() be Replaced by Mesa Ticks?
Q: In Phase 4b, will step() be replaced with Mesa ticks / time progression?
Yes — but only the driver, not the decision contract. Concretely:
Today (Phase 3/4a): SimulationEngine.run() owns time — the outer for s in range(no_seq) / inner for t in range(n_years) loop calls self.step(...), which draws events, updates state, and delegates behaviour to a DecisionRule.
Phase 4b: Time ownership inverts to DYNAMO-M's Mesa scheduler. The native SLRModel.step() becomes the tick driver; each tick DYNAMO-M advances its CoastalNode agents and pulls flood damages from the FloodAdapt lookup table. So the manual year loop in SimulationEngine.step()/run() is what gets replaced by model.step().
What stays stable: the DecisionRule.should_adapt(...) boundary and the coupling contract (arrays in → bool decision out). DynamoLiveRule is the seam — in 4a it's called inside our loop; in 4b the same calcEU math is called inside Mesa's loop. That's exactly why keeping the rule interface stable makes the 4a→4b migration non-breaking.
One nuance: it's not literally that 'step() is deleted.' Rather, who calls the per-year sequence changes — FloodAdapt's engine loop (4a) → DYNAMO-M model.step() (4b). Our engine either becomes a thin shim around the native model or is bypassed for the native path, while SEURule / DynamoLiveRule remain the shared decision kernels.
## 11. Key Files & Artifacts
Path
Purpose
floodadapt_abm/mesa_native.py
FloodAdaptSLRModel / Agents / CoastalNodePopulation / run_mesa_native
tests/test_mesa_native.py
14 Phase-4b tests (bit-parity gate)
examples_engine/06_mesa_native_driving.py
Runnable Phase-4b demo
progress_todos/20260708_phase4b_mesa_native_driving/
report + metrics + harness
AGENTS.md § 'Phase 4b'
Operational guide + reproduction
— End of Phase-4b model documentation —
