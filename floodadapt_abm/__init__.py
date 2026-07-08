"""
floodadapt_abm
==============
FloodAdapt-ABM: agent-based flood adaptation simulation coupled with
the DYNAMO-M Subjective Expected Utility decision framework.

Public API
----------
SimulationEngine (recommended)
    Unified simulation engine with pluggable decision rules
    (Strategy Pattern).  Owns time, data plumbing, event generation, and
    lifespan-dryproof reset logic.  Use this for new code.
ABMSimulator
    **Deprecated** legacy threshold-rule simulator (stage-2 pipeline),
    retained for backward compatibility and the Gate-1 regression test.
    New code should use ``SimulationEngine`` + ``ThresholdRule`` instead.
DecisionRule / ThresholdRule / SEURule
    Pluggable decision rules for ``SimulationEngine``.
AgentState
    Per-agent state container for the engine.
CouplingConfig / DecisionConfig / NetCDFMappingConfig
    Configuration dataclasses.

Note on setup_lookup_table
--------------------------
``setup_lookup_table`` (stage 1 pipeline) is intentionally NOT imported
here because it requires the full ``flood-adapt`` library, which is not
available in all environments (e.g. the ``dynamom`` conda env).

Import it explicitly when needed::

    from floodadapt_abm.setup_lookup_table import create_lookup_table

Internal plumbing (_core, not recommended for direct use)
---------------------------------------------------------
DynamoDecisionBridge
    Internal data-plumbing layer; composed by ``SimulationEngine``.
"""

from floodadapt_abm.abm_simulator import ABMSimulator
from floodadapt_abm.coupling_config import (
    CouplingConfig,
    DecisionConfig,
    NetCDFMappingConfig,
)
from floodadapt_abm.agent_state import AgentState
from floodadapt_abm.decision_rule import DecisionRule, ThresholdRule, SEURule
from floodadapt_abm.simulation_engine import SimulationEngine
from floodadapt_abm.event_utils import draw_year_events, generate_event_sequences

# For backward compat: DynamoDecisionBridge moved to _core, but re-export here
from floodadapt_abm._core import DynamoDecisionBridge

# Phase 4a: live DYNAMO-M parity rule. Import is guarded so the package still
# works when DYNAMO-M is not installed/importable (DYNAMO_M_AVAILABLE is False,
# and constructing DynamoLiveRule then raises DynamoMNotAvailable).
from floodadapt_abm.dynamo_live_rule import (
    DynamoLiveRule,
    DynamoMNotAvailable,
    DYNAMO_M_AVAILABLE,
)

__all__ = [
    "SimulationEngine",
    "ABMSimulator",
    "DecisionRule",
    "ThresholdRule",
    "SEURule",
    "DynamoLiveRule",
    "DynamoMNotAvailable",
    "DYNAMO_M_AVAILABLE",
    "AgentState",
    "CouplingConfig",
    "DecisionConfig",
    "NetCDFMappingConfig",
    "draw_year_events",
    "generate_event_sequences",
    "DynamoDecisionBridge",  # backward compat
]

