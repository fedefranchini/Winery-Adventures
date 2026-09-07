# Development phases

This document describes how to carry out the Winery Adventures project,
from initial preparation to final verification. The phases indicate a
logical order, but the work is managed with Kanban: a new activity can
start only when its dependencies are complete and the card is in `Ready`.

## Rules valid in every phase

For every activity, you must:

1. check that the dependencies indicated on the card are complete;
2. move the card from `Ready` to `In Progress`;
3. respect the limit of a single main task `In Progress` per person;
4. create a `feature/WA-XX-description`,
   `fix/WA-XX-description`, or `docs/WA-XX-description` branch;
5. limit commits and changes to the card's scope and use `WA-XX` in commits;
6. run the tests and checks required by the card;
7. open a `WA-XX — description` Pull Request and add it to the Project;
8. move the card to `Review / Testing` and request the peer review;
9. address the observations raised during the review;
10. move the card to `Done` only after tests, approval, and merge.

## Phase 1 — Kickoff and requirements definition

### Objective

Prepare the work process and turn the provided README and tests into
clear, verifiable requirements. This phase reduces the risk of
implementing behaviors different from those required.

### Activities

- **WA-01 — Project management:** set up the Kanban Project, the fields,
  the states, the WBS, the workflow, the WIP limit, and the organizational
  documentation.
- **WA-02 — Requirements and tests:** create a matrix linking every
  requirement to its origin and to the tests that verify it. Also define
  data schemas, null handling, optional inputs, and expected errors.
- **WA-04 — Toolchain:** set up the Python package, reproducible
  dependencies, Pytest, formatter, and linter.

### What must be produced

- a public Project linked to the repository;
- traceable functional and non-functional requirements;
- a description of the input TSV and output CSV schemas;
- a development environment that can be installed reproducibly;
- documented commands for lint, formatting, and tests.

### Exit criteria

The phase is complete when both students can install the environment,
understand the expected results, and can collect the tests without
configuration errors.

## Phase 2 — Design and foundations

### Objective

Define the architecture before implementation and build the base
components the rest of the system depends on.

### Activities

- **WA-03 — Architecture and UML:** define responsibilities, relationships,
  and inheritance through class, sequence, and use case diagrams.
- **WA-05 — Continuous Integration:** set up automated lint and test
  checks on Pull Requests.
- **WA-06 — BaseWineryAnalyzer:** implement the abstract class and the
  common `analyze_data` contract.
- **WA-07 — I/O:** implement TSV reading, initial validation, the optional
  join with tank information, and output writing.

### What must be done

1. Establish which classes own each responsibility.
2. Define the flow from file loading to the final output.
3. Avoid circular dependencies and duplication between components.
4. Implement the shared interfaces and contracts first.
5. Verify I/O both with `tank_info` and without the optional file.
6. Make CI checks mandatory on regular Pull Requests.

### Exit criteria

UML and the base code must be consistent; the abstract class must pass the
dedicated tests; reading and writing must work on valid temporary files;
CI must correctly run the configured checks.

## Phase 3 — Implementing the core features

### Objective

Build the transformations, the HPC computation, and the end-to-end
orchestration required by the project's tests.

### Transformation activities

- **WA-08:** compute the average pH and the number of readings per tank.
- **WA-09:** expand the varieties associated with each tank and compute
  the number of readings per grape variety.
- **WA-10:** compute the deviation from the standard temperature of 26 °C
  and the version scaled to 1,000 liters when the quantity is available.

The transformations must preserve the columns needed by subsequent
phases, handle nulls according to the contract, and produce exactly the
column names required by the tests.

### Computation and integration activities

- **WA-11 — HPC:** implement the O(n²) pairwise formula, handle empty
  input, actually compile the function with Numba, and add
  `stress_score`.
- **WA-12 — Pipeline:** run the analyzers in the configured sequence and
  integrate Weights & Biases logging, which can be enabled and disabled.
- **WA-13 — Full flow:** integrate I/O, transformations, HPC, Joblib,
  wandb, and output writing through `run_full_pipeline`.

### What must be verified

- the numeric results of the known examples;
- behavior with a null quantity or a missing quantity column;
- aggregations across several tanks and several grape varieties;
- Numba compilation of the stress function;
- an actual Joblib call;
- the presence of `avg_pH_per_tank` and `stress_score` in the output;
- production of the nine rows expected by the acceptance test.

### Exit criteria

All unit tests for the base, transformations, computations, and pipeline
must pass. The end-to-end flow must produce a valid output starting from
the sample datasets.

## Phase 4 — Robustness, testing, and performance

### Objective

Make the system reliable on real input and demonstrate that it can handle
a dataset of at least 100,000 rows with measurable performance.

### Activities

- **WA-14 — Robustness:** validate the schemas, handle missing or invalid
  files, and add understandable application logging.
- **WA-15 — Data generator:** make seed, number of tanks, and number of
  readings configurable, ensuring reproducible output.
- **WA-16 — Tests and edge cases:** add tests for empty input, nulls,
  invalid schemas, and boundary values; measure coverage.
- **WA-17 — Integration:** complete the end-to-end tests, verifying
  output, Joblib, and wandb without unstable external dependencies.
- **WA-18 — Profiling:** measure time and memory with a repeatable
  methodology and identify the bottlenecks.
- **WA-19 — Optimization:** address only the problems demonstrated by
  profiling and compare results before and after.

### Performance procedure

1. Generate a reproducible dataset of at least 100,000 rows.
2. Record the environment, parameters, and code version.
3. Run several measurements, not a single execution.
4. Collect total time, time of the critical phases, and memory used.
5. Keep a baseline before the optimizations.
6. Apply one change at a time and rerun the tests and benchmark.
7. Document any attempted optimizations that do not produce benefits.

### Exit criteria

The full suite must pass, errors must be understandable, the large
dataset must be handled without errors, and the report must show
reproducible data. Every optimization must preserve functional
correctness.

## Phase 5 — Documentation, verification, and delivery

### Objective

Make the project understandable, reproducible, and ready for evaluation
and the final demo.

### Activities

- **WA-20 — Technical documentation:** set up Sphinx, complete the
  docstrings, and generate the API documentation without blocking
  warnings.
- **WA-21 — User guide:** document installation, configuration, usage,
  examples, input, output, and troubleshooting in the README.
- **WA-22 — Final verification:** check CI, quality, UML, the report, the
  Definition of Done, and prepare a reproducible demo.

### What must be done

1. Try the installation instructions starting from a clean environment.
2. Run the end-to-end example described in the README.
3. Check that UML, code, and documentation describe the same system.
4. Generate the Sphinx documentation and fix broken links or references.
5. Run lint, unit tests, acceptance tests, and the final benchmarks.
6. Prepare a short demo with input, execution, output, and performance
   results.
7. Verify the Definition of Done for every card before closing it.

### Exit criteria

The project is ready when another person can install and run it by
following only the documentation, all CI checks are green, the Pull
Requests have been reviewed, and the required artifacts are present.

## Responsibility and collaboration

The Owner indicated on the card is responsible for the implementation and
its fixes. The other member must perform the peer review, checking in
particular:

- adherence to acceptance criteria and dependencies;
- clarity and maintainability of the solution;
- presence and quality of the tests;
- absence of changes outside the scope;
- updating of the affected documentation.

Story points represent complexity and risk, not guaranteed hours. The
team must periodically compare estimates against actual time and discuss
any deviations without creating artificial activities or changing scope
just to achieve a perfect numeric split.
