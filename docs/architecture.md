# Architecture and UML

Description of the UML diagrams representing the structure and behavior of
Winery Adventures: class diagram, sequence diagram, and use case diagram.

## Class diagram

![Class diagram](diagrams/class-diagram.png)

`BaseWineryAnalyzer` is the abstract class that defines the common contract
(`analyze_data`), implemented by `WineryTransformer` and
`WineryHPCComputations`. `WineryPipeline` composes a list of analyzers and
exposes `run`/`log_to_wandb` to orchestrate execution and logging.
`pairwise_stress_function` and `run_full_pipeline` are free functions, not
classes: `pairwise_stress_function` is used by `WineryHPCComputations` (a
dependency relationship), `run_full_pipeline` orchestrates the entire flow by
creating and running the other components.

## Sequence diagram

![Sequence diagram](diagrams/sequence-diagram.png)

The diagram shows the flow of `run_full_pipeline`: reading the
sensor and tank files (in parallel, via Joblib), creating the
analyzers and the pipeline, running the transformations and the HPC
computation (nested calls inside `WineryPipeline.run`), logging to wandb —
only if `project_name` is set — and writing the final result.

## Use case diagram

![Use case diagram](diagrams/use-case-diagram.png)

The **Data Analyst** actor can run the analysis pipeline (the main use
case) and optionally include the tank data as an optional extension.
Independently, they can also generate test datasets through the data
generator.
