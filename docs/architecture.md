# Architecture and UML

Description of the UML diagrams representing the structure and behavior of
Winery Adventures: class diagram, sequence diagram, and use case diagram.

## Class diagram

![Class diagram](diagrams/class-diagram.png)

`BaseWineryAnalyzer` is the abstract base class used by the two provided
analyzers (`WineryTransformer` and `WineryHPCComputations`). `WineryAnalyzer`
is the structural Protocol that `WineryPipeline` requires (accepting and
storing a Sequence of analyzers satisfying this protocol without requiring
inheritance). `WineryPipeline` exposes `run`/`log_to_wandb` to orchestrate
execution and optional logging to Weights & Biases. `run_full_pipeline` enables
logging only when `project_name` is not `None`; low-level callers can explicitly
request logging without a project name, allowing W&B to select its default.
`pairwise_stress_function` and
`run_full_pipeline` are free functions: `pairwise_stress_function` is used by
`WineryHPCComputations` (a dependency relationship), while `run_full_pipeline`
orchestrates the full flow by creating and running the components.

## Sequence diagram

![Sequence diagram](diagrams/sequence-diagram.png)

The runtime flow of `run_full_pipeline` operates as follows: inputs are loaded
in parallel via Joblib, preflight tank-coverage validation
(`validation.validate_tank_coverage`) is executed when tank information is
provided, `WineryHPCComputations` runs on the unexpanded readings,
`WineryTransformer` follows (performing the join, per-variety expansion,
and temperature deviations, while re-checking coverage and preserving
`stress_score` as the last output column), summary metrics are optionally
logged to W&B if `project_name` is set, and the final CSV result is written to
output.

## Use case diagram

![Use case diagram](diagrams/use-case-diagram.png)

The **Data Analyst** actor can run the analysis pipeline (the main use
case), with extensions to include tank data when `tank_info_csv` is set
and to log metrics to Weights & Biases (an external secondary actor
outside the system boundary) when `project_name` is set. Independently,
they can also generate test datasets through the data generator.
