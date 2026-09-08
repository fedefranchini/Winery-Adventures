# Project Management

## Kanban method

Winery Adventures adopts Kanban to make priorities, dependencies, and work
status visible, keeping a continuous flow compatible with a two-student
group. The Project uses the states `Backlog`, `Ready`, `In Progress`,
`Review / Testing`, and `Done`.

The units of work are exclusively draft cards in the GitHub Project. Each
card contains the required outcome, acceptance criteria, dependencies, and
tests; dependencies are textual and reference `WA-XX` codes, without
creating GitHub Issues.

The operational description of the phases, activities, and their exit
criteria is available in [`development-phases.md`](development-phases.md).

## Estimation and breakdown

Effort uses the 1, 2, 3, 5, and 8 story point scale. The estimate considers
scope, complexity, integrations, uncertainty, and verification work, not
time in hours. The breakdown is based on actual effort, not on the number
of cards:

- MarrasFederico: **47 SP**
- FedeFranchini: **48 SP**

## Work Breakdown Structure

| Code | Outcome | Owner | SP | Priority | Area | Dependencies | Initial state |
|---|---|---|---:|---|---|---|---|
| WA-01 | Set up the Kanban Project, fields, workflow, and project management documentation | MarrasFederico | 3 | High | Documentation | — | Ready |
| WA-02 | Create the requirements-tests matrix and clarify data contracts, nulls, and errors | FedeFranchini | 3 | High | Requirements | — | Ready |
| WA-03 | Design the architecture and UML: classes, sequence, and use cases | FedeFranchini | 5 | High | Architecture | WA-02 | Backlog |
| WA-04 | Set up the package, reproducible dependencies, formatter, linter, and Pytest | MarrasFederico | 5 | High | Architecture | — | Ready |
| WA-05 | Set up CI for lint, unit tests, acceptance tests, and PR status | FedeFranchini | 3 | High | Testing | WA-04 | Backlog |
| WA-06 | Implement `BaseWineryAnalyzer` and the abstract contracts | MarrasFederico | 2 | High | Architecture | WA-03, WA-04 | Backlog |
| WA-07 | Implement TSV loading, initial validation, and output writing | FedeFranchini | 5 | High | Backend | WA-02, WA-04 | Backlog |
| WA-08 | Implement average pH and reading count per tank | MarrasFederico | 3 | High | Backend | WA-06 | Backlog |
| WA-09 | Implement tank information join, expansion, and reading count per grape variety | FedeFranchini | 5 | High | Data | WA-06, WA-07 | Backlog |
| WA-10 | Implement unscaled and scaled temperature deviation, including nulls | MarrasFederico | 3 | High | Backend | WA-02, WA-06 | Backlog |
| WA-11 | Implement the pairwise formula and the HPC analyzer compiled with Numba | MarrasFederico | 8 | High | Backend | WA-02, WA-06 | Backlog |
| WA-12 | Implement the sequential pipeline and Weights & Biases logging | FedeFranchini | 8 | High | Backend | WA-06, WA-08–WA-11 | Backlog |
| WA-13 | Implement `run_full_pipeline`, I/O orchestration, and Joblib parallelism | FedeFranchini | 5 | High | Backend | WA-07, WA-12 | Backlog |
| WA-14 | Integrate schema validation, error handling, and application logging | MarrasFederico | 5 | Medium | Backend | WA-07, WA-12 | Backlog |
| WA-15 | Make the data generator reproducible, configurable, and verified | FedeFranchini | 3 | Medium | Data | WA-04 | Backlog |
| WA-16 | Extend unit tests and edge cases: empty inputs, nulls, schema, and invalid input | MarrasFederico | 5 | High | Testing | WA-08–WA-14 | Backlog |
| WA-17 | Complete the acceptance and integration tests for the end-to-end flow | FedeFranchini | 3 | High | Testing | WA-13, WA-14 | Backlog |
| WA-18 | Create the time and memory benchmark and report with a dataset of at least 100k rows | MarrasFederico | 5 | Medium | Testing | WA-11, WA-13, WA-15 | Backlog |
| WA-19 | Optimize the bottlenecks demonstrated by profiling | FedeFranchini | 5 | Medium | Backend | WA-18 | Backlog |
| WA-20 | Set up Sphinx documentation and complete docstrings/API reference | MarrasFederico | 5 | Medium | Documentation | WA-08–WA-14 | Backlog |
| WA-21 | Complete the README: installation, usage, examples, output, and troubleshooting | FedeFranchini | 3 | Medium | Documentation | WA-13, WA-20 | Backlog |
| WA-22 | Final verification: quality, CI, aligned UML, DoD, and demo preparation | MarrasFederico | 3 | High | Testing | WA-05, WA-16–WA-21 | Backlog |

## Operational workflow

1. Select a `Ready` card respecting dependencies and the WIP limit.
2. Move it to `In Progress`.
3. Create a `feature/WA-XX-description`,
   `fix/WA-XX-description`, or `docs/WA-XX-description` branch.
4. Use `WA-XX` in the relevant commits and limit the changes to the scope.
5. Run the applicable tests.
6. Open a Pull Request titled `WA-XX — description` and add it to the
   Project. Do not use `Closes #...`.
7. Move the card to `Review / Testing` and request the other member's
   review.
8. After approval, tests, and merge, move the card to `Done`.

## WIP limit and peer review

Each member can have at most one main task `In Progress`. Every Pull
Request is reviewed by the other member; the author resolves the comments
and does not approve their own work.

## Definition of Done

A card is `Done` only when:

- the acceptance criteria and dependencies are satisfied;
- the implementation and documentation stay within the card's scope;
- the applicable tests, lint, and CI pass;
- the Pull Request contains the WA code and is linked to the Project;
- the peer review has been completed and the comments are resolved;
- the Pull Request has been merged into the main branch;
- the affected documentation is updated and the result is reproducible.
