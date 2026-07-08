# Examples — SimulationEngine (Recommended)

This folder contains examples demonstrating the FloodAdapt-ABM coupling with the DYNAMO-M SEU decision framework.

## Canonical Examples (Use These)

### `run_coupled_example_engine.py` ⭐ (Recommended)

Unified `SimulationEngine` API demonstration:
- Side-by-side comparison of `SEURule` (DYNAMO-M SEU science) and `ThresholdRule` (legacy heuristic)
- Multi-year Charleston simulation
- **Status**: Current, Phase 2+3 refactor
- **Architecture**: `SimulationEngine` with pluggable `DecisionRule`

```bash
python run_coupled_example_engine.py
```

## Legacy Examples (For Reference Only)

See **`old_bridge_examples/`** folder (moved from `example/`):

- **`run_coupled_example.py`** — Original `DynamoDecisionBridge`-based example. **Not recommended for new code** — use `run_coupled_example_engine.py` instead. Manual year-by-year stepping using deprecated bridge API (internal-only as of Phase 2+3). Kept for backward compatibility & reference.

- **`run_trace_manual_check.py`** — Manual trace/debugging example using the bridge. **Reference only** — not part of current workflow.

**Migration path**: If you have code using the legacy bridge API, update imports:
```python
# OLD (still works, re-exported for compatibility)
from floodadapt_abm import DynamoDecisionBridge

# NEW (recommended)
from floodadapt_abm import SimulationEngine
```

---

## Folder Structure

```
examples_engine/                        ← YOU ARE HERE (canonical examples)
  ├── run_coupled_example_engine.py     ⭐ USE THIS
  ├── README.md                         (this file)
  └── old_bridge_examples/              ⚠️ DEPRECATED
       ├── run_coupled_example.py       (legacy bridge API)
       ├── run_trace_manual_check.py    (debug reference)
       └── README.md                    (migration guide)
```

---

```
SimulationEngine  (owns time, data, event drawing)
  ├── _data: DynamoDecisionBridge  (internal data plumbing)
  ├── decision_rule: DecisionRule  (pluggable: ThresholdRule or SEURule)
  └── state: AgentState  (unified per-agent arrays)
```

### Decision Rules

- **`SEURule`** — DYNAMO-M Subjective Expected Utility science (validated Phase 1). 
  Adapts when EU(adapt) > EU(do_nothing).
- **`ThresholdRule`** — Legacy ex-post heuristic. 
  Adapts when realised damage > 0.3 × max_pot_dmg.
- **Custom rules** — Inherit `DecisionRule`, implement `should_adapt(...)` to plug in new logic.

### Key Features

- **Unified event drawing**: All event generation flows through a single random-pool-capped Bernoulli draw (Phase 2 dedup).
- **Lifespan-dryproof reset** (Phase 3): Measures age and expire (reset) after 75 years, enabling multi-generational dynamics matching native DYNAMO-M.
- **Backward compatible**: Legacy `DynamoDecisionBridge` and `ABMSimulator` still work (internal use only).

## Usage

### Basic Run

```python
from floodadapt_abm import SimulationEngine, CouplingConfig, DecisionConfig
import xarray as xr
import numpy as np

# Load lookup table
ds = xr.open_dataset("path/to/lookup_table.nc")

# Configure
cfg = CouplingConfig(decision=DecisionConfig())

# Create engine (SEURule by default)
engine = SimulationEngine(ds=ds, config=cfg)

# Run
slr_trajectory = np.linspace(0, 2.0, 30)
results = engine.run(slr_trajectory, no_seq=10, seed=42)

# Access results
damage_history = results["damage_history"]       # (no_seq, n_agents, n_years)
adapted_history = results["adapted_history"]     # (no_seq, n_agents, n_years)
adoption_fraction = results["adoption_fraction"] # (no_seq, n_years)
```

### Custom Rule

```python
from floodadapt_abm import SimulationEngine, DecisionRule
import numpy as np

class CustomRule(DecisionRule):
    def should_adapt(self, agent_state, damages_this_year, damages_no_adapt,
                     damages_adapt, event_freqs, max_pot_dmg, adaptation_costs):
        # Your logic here
        return np.zeros(agent_state.n_agents, dtype=bool)

engine = SimulationEngine(ds=ds, config=cfg, decision_rule=CustomRule(cfg.decision))
results = engine.run(slr_trajectory, no_seq=10)
```

## Testing

All functionality is covered by the test suite:

```bash
pytest tests/ -v
```

- `test_event_utils.py` — Event generation (Bernoulli, random cap, reproducibility)
- `test_agent_state.py` — Per-agent state container
- `test_decision_rule.py` — Rule parity (ThresholdRule == legacy, SEURule == bridge)
- `test_simulation_engine.py` — Engine plumbing, lifespan turnover, degenerate cases

