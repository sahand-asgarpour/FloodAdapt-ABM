# FloodAdapt-ABM

FloodAdapt-ABM is a lightweight agent-based simulator that processes a precomputed [FloodAdapt](https://pypi.org/project/flood-adapt/) impact lookup table to generate a Monte-Carlo time series of building-level damages and household floodproofing decisions. It is designed to run either with a simple damage-threshold rule or coupled with the **DYNAMO-M** Subjective Expected Utility (SEU) decision framework.

---

## Repository Structure

All source code is stored under the `floodadapt_abm/` directory:

```
FloodAdapt-ABM/
├── floodadapt_abm/
│   ├── __init__.py                    # Public API exports (SimulationEngine recommended)
│   ├── _core/                         # Internal data-plumbing layer (not public)
│   │   ├── dynamo_decision_bridge.py # DYNAMO-M SEU coupling (internal composition)
│   │   └── lookup_utils.py           # NetCDF & SLR interpolation utilities (internal)
│   ├── simulation_engine.py           # ⭐ RECOMMENDED: Unified engine (Phase 2+3)
│   ├── decision_rule.py               # Pluggable rules: DecisionRule ABC, ThresholdRule, SEURule
│   ├── agent_state.py                 # Per-agent state container
│   ├── event_utils.py                 # Unified event drawing (Bernoulli + random-pool cap)
│   ├── coupling_config.py             # Configuration dataclasses
│   ├── abm_simulator.py               # Legacy simulator (threshold-based, backward compat)
│   └── setup_lookup_table.py          # FloodAdapt stage 1 combinations matrix generator
├── examples_engine/                   # ⭐ RECOMMENDED: SimulationEngine examples
│   ├── run_coupled_example_engine.py # SEURule vs ThresholdRule demo
│   ├── run_coupled_example.py         # (legacy bridge-based, reference only)
│   ├── run_trace_manual_check.py      # (legacy bridge-based, reference only)
│   └── README.md                      # Usage guide & architecture
├── old_bridge_examples/               # DEPRECATED: Original bridge-based examples
│   ├── run_coupled_example.py         # (moved from example/, kept for reference)
│   ├── run_trace_manual_check.py      # (moved from example/, kept for reference)
│   └── README.md                      # Migration guide
├── tests/                             # Test suite
│   ├── conftest.py                   # Shared test fixtures (mock datasets)
│   ├── test_event_utils.py           # Event drawing tests
│   ├── test_agent_state.py           # AgentState tests
│   ├── test_decision_rule.py         # DecisionRule parity tests (gates)
│   ├── test_simulation_engine.py     # SimulationEngine tests
│   └── test_dynamo_decision_bridge.py # Bridge regression tests (43 tests)
├── pyproject.toml                     # Standard package configuration & metadata
├── environment.yml                    # Conda environment definition (optional)
└── README.md                          # This file
```

**Key note**: The old `example/` folder is now `old_bridge_examples/` and should not be used for new projects. Use `examples_engine/` instead.

---

## Do I need all of `environment.yml` and `pyproject.toml`?

No, they serve different purposes:
1. **`pyproject.toml`**: **(Recommended / Primary)** This is the single source of truth for the package metadata and dependencies. It makes the package installable via `pip`.
2. **`environment.yml`**
---

## Installation

### Using pip and virtualenv (Standard Python)

You can create a standard Python virtual environment and install the package using `pip` (requires Python 3.10+):

1. Create a virtual environment in the project directory:
   ```bash
   # On Windows
   python -m venv venv
   
   # On macOS/Linux
   python3 -m venv venv
   ```

2. Activate the virtual environment:
   ```bash
   # On Windows (Command Prompt)
   venv\Scripts\activate.bat
   
   # On Windows (PowerShell)
   venv\Scripts\Activate.ps1
   
   # On macOS/Linux
   source venv/bin/activate
   ```

3. Install the package in editable mode:
   ```bash
   # Basic installation
   pip install -e .
   
   # Or install with developer dependencies (for running tests)
   pip install -e .[dev]
   
   # Or install with the full pipeline dependency (includes flood-adapt)
   pip install -e .[pipeline]
   ```


---

## Running the Example

A coupled DYNAMO-M simulation example is located in the `example/` folder. Run it using:

```bash
python example/run_coupled_example.py
```

---

## Running Tests

Unit tests are written using `pytest`. You can run them in the repository root:

```bash
pytest tests/ -v
```
