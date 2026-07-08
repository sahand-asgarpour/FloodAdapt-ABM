"""
run_coupled_example_engine.py
==============================
Demonstration of the unified ``SimulationEngine`` (Phase 2+3 refactor).

This script loads the Charleston probabilistic lookup table, constructs a
``SimulationEngine`` with pluggable decision rules, and demonstrates:

* Unified event drawing (``event_utils.draw_year_events``)
* Multi-year runs via ``engine.run()``
* Pluggable decision rules: ``ThresholdRule`` (legacy 0.3) and ``SEURule`` (DYNAMO-M SEU)
* Lifespan-dryproof reset (Phase-3 gap closure)

Run directly::

    python run_coupled_example_engine.py

**Recommended use pattern**: This is the new canonical API. The old
``DynamoDecisionBridge`` is now internal (``floodadapt_abm._core``).

Reference
---------
Tierolf, L., Haer, T., Botzen, W. J. W., de Bruijn, J. A., Ton, M. J.,
Reimann, L., & Aerts, J. C. J. H. (2023). A coupled agent-based model for
France for simulating adaptation and migration decisions under future coastal
flood risk. Scientific Reports, 13(1), 4176.
https://doi.org/10.1038/s41598-023-31351-y
"""

from __future__ import annotations

import sys
import textwrap
from pathlib import Path

import numpy as np
import xarray as xr

from floodadapt_abm import (
    CouplingConfig,
    DecisionConfig,
    NetCDFMappingConfig,
    SimulationEngine,
    ThresholdRule,
    SEURule,
)

# ===========================================================================
# ── USER-ADJUSTABLE SETTINGS ────────────────────────────────────────────────
# ===========================================================================

#: Path to the precomputed FloodAdapt-ABM lookup table.
LOOKUP_TABLE_PATH: Path = Path(
    r"C:\repos\DYNAMO-M\lookup_table_charleston_beta_release_ABM_probabilistic_set.nc"
)

# Constants
RANDOM_SEED = 42
INITIAL_YEAR = 2020
TIME_HORIZON = 30
SLR_VALUES = np.linspace(0, 1.5, TIME_HORIZON)  # Linear SLR trajectory

#: Sub-sample of agents to print (keeps console readable).
N_AGENTS_PRINT: int = 10


# ===========================================================================
# ── HELPER FUNCTIONS ────────────────────────────────────────────────────────
# ===========================================================================


def _header(title: str, width: int = 72) -> None:
    """Print a formatted section header."""
    print("\n" + "=" * width)
    print(f"  {title}")
    print("=" * width)


def _subheader(title: str) -> None:
    print(f"  -- {title} --")


def _print_summary(engine: SimulationEngine, results: dict) -> None:
    """Print summary statistics."""
    print("\n  --- Simulation Summary ---")
    print(f"  Agents: {engine.n_agents}")
    print(
        f"  Final adoption fraction: {results['adapted_history'][:, :, -1].mean():.1%}"
    )
    total_damage = results["damage_history"].sum()
    print(f"  Total damage (all agents, all years): ${total_damage:,.0f}")


# ===========================================================================
# ── MAIN ────────────────────────────────────────────────────────────────────
# ===========================================================================


def main() -> None:
    """Execute the SimulationEngine demonstration."""

    _header("STEP 0 — SETUP")

    # Load the lookup table
    if not LOOKUP_TABLE_PATH.exists():
        print(
            f"ERROR: Lookup table not found at {LOOKUP_TABLE_PATH}\n"
            "Please download it or adjust LOOKUP_TABLE_PATH in this script."
        )
        sys.exit(1)

    ds = xr.open_dataset(LOOKUP_TABLE_PATH)
    print(f"Loaded {LOOKUP_TABLE_PATH.name}")
    print(f"  Dimensions: {dict(ds.dims)}")
    print(f"  Variables: {list(ds.data_vars)}")

    # Configuration
    cfg = CouplingConfig(
        netcdf=NetCDFMappingConfig(
            residential_substring="RES",
            strategy_no_measures="no_measures",
            strategy_floodproof="floodproof_all_0",
        ),
        decision=DecisionConfig(
            risk_aversion=1.0,
            discount_rate=0.032,
            decision_horizon=15,
            max_events_per_year=4,
            lifespan_dryproof=75,  # Phase-3: dryproofing lifespan
        ),
        random_seed=RANDOM_SEED,
    )

    print("\nConfiguration:")
    print(f"  Decision horizon: {cfg.decision.decision_horizon} years")
    print(f"  Risk aversion: {cfg.decision.risk_aversion}")
    print(f"  Lifespan (dryproof): {cfg.decision.lifespan_dryproof} years")

    # -----------------------------------------------------------------------
    # SCENARIO 1: SEURule (DYNAMO-M science, validated in Phase 1)
    # -----------------------------------------------------------------------
    _header("SCENARIO 1 — SEURule (DYNAMO-M SEU science)")

    print(textwrap.dedent("""
      The SEURule implements the DYNAMO-M Subjective Expected Utility framework
      (ported + validated in Phase 1). Agents adapt when EU(adapt) > EU(do_nothing).
    """))

    engine_seu = SimulationEngine(ds=ds, config=cfg)
    print(f"Created engine with {engine_seu.n_agents} residential agents")

    # Run Monte-Carlo simulation (3 sequences, simplified for demo)
    print(f"Running {3} Monte-Carlo sequences, {TIME_HORIZON} years each...")
    results_seu = engine_seu.run(SLR_VALUES, no_seq=3, seed=RANDOM_SEED, track_eu=True)

    _print_summary(engine_seu, results_seu)
    if results_seu["eu_adapt_history"] is not None:
        mean_eu_adapt = np.nanmean(results_seu["eu_adapt_history"])
        mean_eu_do_nothing = np.nanmean(results_seu["eu_do_nothing_history"])
        print(f"  Mean EU(adapt): {mean_eu_adapt:,.0f}")
        print(f"  Mean EU(do_nothing): {mean_eu_do_nothing:,.0f}")

    # -----------------------------------------------------------------------
    # SCENARIO 2: ThresholdRule (legacy heuristic for comparison)
    # -----------------------------------------------------------------------
    _header("SCENARIO 2 — ThresholdRule (legacy 0.3 heuristic)")

    print(textwrap.dedent("""
      The ThresholdRule reproduces the original ABMSimulator behaviour:
      agents adapt when realised damage > 0.3 * max_pot_dmg (ex-post).
    """))

    engine_thresh = SimulationEngine(
        ds=ds,
        config=cfg,
        decision_rule=ThresholdRule(cfg.decision, damage_threshold=0.30),
    )
    print(f"Created engine with {engine_thresh.n_agents} residential agents")

    print(f"Running {3} Monte-Carlo sequences, {TIME_HORIZON} years each...")
    results_thresh = engine_thresh.run(SLR_VALUES, no_seq=3, seed=RANDOM_SEED)

    _print_summary(engine_thresh, results_thresh)

    # -----------------------------------------------------------------------
    # COMPARISON
    # -----------------------------------------------------------------------
    _header("COMPARISON: SEURule vs ThresholdRule")

    print(textwrap.dedent(f"""
      Adoption fraction at year {TIME_HORIZON}:
        SEURule:      {results_seu['adapted_history'][:, :, -1].mean():.1%}
        ThresholdRule: {results_thresh['adapted_history'][:, :, -1].mean():.1%}
      
      Total damage over all sequences:
        SEURule:      ${results_seu['damage_history'].sum():,.0f}
        ThresholdRule: ${results_thresh['damage_history'].sum():,.0f}
      
      The difference reflects:
      1. SEURule is ex-ante (forward-looking utility maximisation)
      2. ThresholdRule is ex-post (reactive, high-damage trigger)
      3. Different adaptation thresholds => different damage dynamics
    """))

    print("\n✓ Demo complete. Both rules are now pluggable via SimulationEngine.")


if __name__ == "__main__":
    main()
