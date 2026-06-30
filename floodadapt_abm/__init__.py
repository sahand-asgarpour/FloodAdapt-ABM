"""
floodadapt_abm
==============
FloodAdapt-ABM: agent-based flood adaptation simulation coupled with
the DYNAMO-M Subjective Expected Utility decision framework.

Key public classes
------------------
ABMSimulator
    Monte-Carlo threshold-rule simulator (stage 2 pipeline).
DynamoDecisionBridge
    SEU-based decision bridge coupling the NetCDF lookup table with
    DYNAMO-M utility functions.
CouplingConfig / DecisionConfig / NetCDFMappingConfig
    Configuration dataclasses for the bridge.

Note on setup_lookup_table
--------------------------
``setup_lookup_table`` (stage 1 pipeline) is intentionally NOT imported
here because it requires the full ``flood-adapt`` library, which is not
available in all environments (e.g. the ``dynamom`` conda env).

Import it explicitly when needed::

    from floodadapt_abm.setup_lookup_table import create_lookup_table
"""

from floodadapt_abm.abm_simulator import ABMSimulator
from floodadapt_abm.dynamo_decision_bridge import DynamoDecisionBridge
from floodadapt_abm.coupling_config import (
    CouplingConfig,
    DecisionConfig,
    NetCDFMappingConfig,
)

__all__ = [
    "ABMSimulator",
    "DynamoDecisionBridge",
    "CouplingConfig",
    "DecisionConfig",
    "NetCDFMappingConfig",
]
