# FloodAdapt-ABM

FloodAdapt-ABM is a lightweight agent-based simulator that processes a precomputed [FloodAdapt](https://pypi.org/project/flood-adapt/) impact lookup table to generate a Monte-Carlo time series of building-level damages and household floodproofing decisions. It is designed to run either with a simple damage-threshold rule or coupled with the **DYNAMO-M** Subjective Expected Utility (SEU) decision framework.

---

## Repository Structure

All source code is stored under the `floodadapt_abm/` directory:

```
FloodAdapt-ABM/
├── floodadapt_abm/
│   ├── __init__.py              # Package exports
│   ├── abm_simulator.py         # Main simulator logic (threshold-based)
│   ├── dynamo_decision_bridge.py # DYNAMO-M SEU coupling bridge
│   ├── coupling_config.py       # Configuration schemas (dataclasses)
│   ├── lookup_utils.py          # Shared NetCDF & SLR interpolation utilities
│   └── setup_lookup_table.py    # FloodAdapt stage 1 combinations matrix generator
├── example/
│   └── run_coupled_example.py       # Demonstration of coupled DYNAMO-M bridge run
├── tests/
│   └── test_dynamo_decision_bridge.py # Core unit tests
├── pyproject.toml                   # Standard package configuration & metadata
├── environment.yml                  # Conda environment definition
└── README.md                        # Installation & usage guide
```

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
