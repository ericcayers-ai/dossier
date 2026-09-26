"""The injectable agent layer.

`manifest` declares the contract. `workspace` resolves a folder into the state
that contract operates on. `brief` turns both into a task packet any model can
execute. `adapters` emits that packet as a vendor-specific prompt pack. `loop`
keeps multi-step work honest across sessions.
"""

from .manifest import (
    ARTIFACTS,
    GATES,
    MODES,
    SCHEMA_VERSION,
    STAGES,
    agent_modes,
    artifacts,
    engine_modes,
    gates,
    mode,
    modes,
    pipeline_from,
    route,
    stages,
)
from .manifest import manifest as contract

__all__ = [
    "ARTIFACTS",
    "GATES",
    "MODES",
    "SCHEMA_VERSION",
    "STAGES",
    "agent_modes",
    "artifacts",
    "contract",
    "engine_modes",
    "gates",
    "mode",
    "modes",
    "pipeline_from",
    "route",
    "stages",
]
