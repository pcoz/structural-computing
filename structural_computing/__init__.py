"""structural-computing -- declarative structural computation, packaged.

The friendly user-facing entry point is :class:`StructuralComputer`:

    >>> from structural_computing import StructuralComputer
    >>> sc = StructuralComputer()
    >>> sc.count_matchings([(0, 1), (1, 2), (2, 3), (3, 0)])
    2

For composing custom pipelines, the framework primitives are also exposed:

    >>> from structural_computing import Stage, Route, run_pipeline, RichTrace

See the docs at https://github.com/pcoz/free-fermion-quantum-simulation/blob/main/docs/getting-started.md
for the 10-minute tutorial.
"""

__version__ = "0.1.0a1"

from .easy import (
    StructuralComputer,
    CompareReport,
    NotInFamily,
)
from .pipeline_router import (
    Stage,
    Route,
    StageRecord,
    Trace,
    run_pipeline,
    run_pipeline_streaming,
)
from .classify import (
    Classification,
    classify,
    classify_constraint_set,
    classify_graph,
    classify_signature,
)
from .route import route
from .trace import RichTrace, RegimeChange
from .replay import ReplayCache, cached_runner, default_key
from .verifier import (
    brute_force_count_matchings,
    satisfies_gf2_affine,
    enumerate_satisfying_assignments,
    gibbs_expectation_brute,
    verify_pipeline,
)

__all__ = [
    # Wrapper class (the main entry point)
    "StructuralComputer",
    "CompareReport",
    "NotInFamily",
    # Pipeline framework
    "Stage",
    "Route",
    "StageRecord",
    "Trace",
    "run_pipeline",
    "run_pipeline_streaming",
    # Classifier
    "Classification",
    "classify",
    "classify_constraint_set",
    "classify_graph",
    "classify_signature",
    # Router
    "route",
    # Trace aggregator
    "RichTrace",
    "RegimeChange",
    # Replay cache
    "ReplayCache",
    "cached_runner",
    "default_key",
    # Verifier
    "brute_force_count_matchings",
    "satisfies_gf2_affine",
    "enumerate_satisfying_assignments",
    "gibbs_expectation_brute",
    "verify_pipeline",
    # Version
    "__version__",
]
