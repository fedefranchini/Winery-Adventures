# WA-18 / WA-19 — Benchmark and optimization report

This report presents the benchmark results for the Winery Adventures
pipeline, evaluating the effect of the analyzer execution reordering
(WA-19: HPC computation before variety expansion) and isolating the
performance impact of Numba's parallel compilation (WA-18). The
`hpc-first`, `transformer-first`, and kernel measurements in this report
were produced on September 7, 2026.

The raw measurement data is recorded in the following JSON files:

- Production order (`hpc-first`): [pipeline-wa22-hpc-first.json](benchmark-results/pipeline-wa22-hpc-first.json)
- Legacy order (`transformer-first`): [pipeline-wa22-transformer-first.json](benchmark-results/pipeline-wa22-transformer-first.json)
- Kernel comparison (`hpc-first`): [kernels-wa22-hpc-first.json](benchmark-results/kernels-wa22-hpc-first.json)
- Historical pre-reorder baseline: [pipeline-wa22.json](benchmark-results/pipeline-wa22.json) and [kernels-wa22.json](benchmark-results/kernels-wa22.json)

## Version and environment

The measured version is the working tree of
`fix/WA-22-final-verification`, on top of commit
`d8c4b82b5c1ba6dd3b8f926db2743215db4748a1` (`d8c4b82`), with local WA-22
changes. The base commit alone does not identify the measured code: the
benchmark and kernel comparison JSON files record the SHA-256
fingerprints of the sources involved so that the measured code remains
identifiable despite uncommitted changes in the working tree. The
fingerprints are of local bytes, so they include line endings.

| Item | Value |
|---|---|
| System | Windows-10-10.0.26200-SP0 |
| Processor | AMD64 Family 25 Model 33 Stepping 2, AuthenticAMD |
| Numba threads | 32 |
| Python | 3.11.0 |
| NumPy / Polars | 2.4.6 / 1.44.1 |
| Numba / Joblib | 0.67.0 / 1.5.3 |
| Input | 100 tanks, 100,000 readings, seed 42 |
| Output | 300,000 rows after per-variety expansion |
| Computable unexpanded rows (`hpc-first`) | 90,041 complete readings evaluated |
| Computable expanded rows (`transformer-first`) | 270,123 expanded rows evaluated |
| Repetitions | 5 per measurement |

All benchmark runs produced identical deterministic inputs:

- sensors: `fdd4518535ce9dd98c4e034cb1f9ae5464771549ed7c7433bd10b8384d80d557`;
- tanks: `27b9dfe8c3ddf683a6b19499b3fbca38b158059b36e9dfdb96e5933cd37d0de4`.

## Reproduction

Run from the root, after installing the project. The destination
directory must exist. The following commands create new local reports:

```bash
python -m benchmarks.benchmark_pipeline --tanks 100 --readings 100000 --repetitions 5 --seed 42 --order hpc-first --output docs/benchmark-results/pipeline-wa22-hpc-first.json
python -m benchmarks.benchmark_pipeline --tanks 100 --readings 100000 --repetitions 5 --seed 42 --order transformer-first --output docs/benchmark-results/pipeline-wa22-transformer-first.json
python -m benchmarks.compare_kernels --tanks 100 --readings 100000 --repetitions 5 --seed 42 --output docs/benchmark-results/kernels-wa22-hpc-first.json
```

Compare hashes, parameters, versions, and thread count before comparing
timings. The attached JSON files keep every repetition, not just the
median. Absolute timings vary with the machine, the load, and the run
conditions; the observed ratios are not guarantees for other
installations.

## Production pipeline (`hpc-first`)

The runner measures TSV reading, preflight tank-coverage validation,
transformations, HPC, and CSV writing. Input generation and initial
compilation are excluded from the iterations; W&B is not activated by the
benchmark. Score finiteness is verified at every iteration.

Reading includes type inference over the entire TSV, needed to recognize
quantities and decimals even when they appear beyond the first rows. The
flow includes the preflight validation check (`validate_tank_coverage`)
performed immediately after loading. The following timings include these
costs; they do not reuse the measurements from before the runner fix.

| Measure | Median | Minimum | Maximum |
|---|---:|---:|---:|
| Total | 0.221799 s | 0.214286 s | 0.258613 s |
| Input reading | 0.087726 s | 0.086735 s | 0.107534 s |
| Preflight validation | 0.001515 s | 0.001354 s | 0.002023 s |
| Transformations | 0.039976 s | 0.038753 s | 0.054334 s |
| HPC | 0.067462 s | 0.061745 s | 0.072189 s |
| Output writing | 0.025063 s | 0.023248 s | 0.026205 s |

Phase medians are not necessarily additive. The total also includes
coordination and result checking. Every iteration produced 300,000 rows
with finite stress values.

| Phase | Peak of traced Python allocations |
|---|---:|
| Input reading | 0.111 MiB |
| Preflight validation | 0.773 MiB |
| Transformations | 0.773 MiB |
| HPC | 1.538 MiB |
| Output writing | 0.002 MiB |

`tracemalloc` does not measure the process's entire memory and does not
include all the native allocations of Polars, NumPy, and Numba. These
values cannot be used as an estimate of the required RAM.

## Reordering effect (WA-19 before/after comparison)

The WA-19 optimization reorders the analyzers so that the quadratic
pairwise stress computation runs on unexpanded sensor readings before
grape variety expansion, rather than after.

Both execution orders were measured in the same session on the same
machine and the same seed 42 dataset (5 repetitions):

| Measure | Legacy (`transformer-first`) | Production (`hpc-first`) | Speedup / Ratio |
|---|---:|---:|---:|
| Total runtime (median) | 0.336496 s | 0.221799 s | 1.52× (34.1% less time) |
| Total runtime (min) | 0.324103 s | 0.214286 s | 1.51× |
| Total runtime (max) | 0.343845 s | 0.258613 s | 1.33× |
| Input reading (median) | 0.087457 s | 0.087726 s | 1.00× |
| Preflight validation (median) | 0.001566 s | 0.001515 s | 1.03× |
| Transformations (median) | 0.039730 s | 0.039976 s | 0.99× |
| HPC computation (median) | 0.174963 s | 0.067462 s | 2.59× (61.4% less time) |
| Output writing (median) | 0.027151 s | 0.025063 s | 1.08× |
| HPC peak Python memory | 4.776 MiB | 1.538 MiB | 3.11× reduction |

### Rationale and numerical verification

In the legacy order (`transformer-first`), each sensor reading is
expanded into multiple rows based on the grape varieties assigned to its
tank (an average factor of about 3 in the standard benchmark dataset,
expanding 90,041 computable readings to 270,123 rows). Because the
pairwise stress kernel has quadratic complexity relative to the number
of readings per tank, expanding each reading by a factor of about 3
multiplies the number of pairwise evaluations per tank by about 9, while
the n squared normalization denominator grows by the same factor, so the
tank stress score is mathematically unchanged.

Reordering to `hpc-first` computes the pairwise stress scores directly on
the 90,041 unexpanded valid readings, and the transformer subsequently
broadcasts the resulting score to each variety row. This reduces the
median HPC execution time from 0.174963 s to 0.067462 s (a **2.59×
speedup**) and reduces peak traced memory from 4.776 MiB to 1.538 MiB
(**3.11× reduction**). The measured wall-clock HPC gain is 2.59× rather
than 9× because the kernel is executed in parallel across 32 Numba
threads and other per-phase costs remain.

For the finite outputs exercised by the regression tests, reordering
preserves stress values within floating-point tolerance, not bit for bit.
Extreme inputs can overflow the longer legacy accumulation even when
the unexpanded computation remains finite. The regression tests are:

- `tests/unit/test_main.py::test_run_full_pipeline_reordered_vs_reference_and_legacy_order`
- `tests/unit/test_pipeline.py::test_legacy_explicitly_ordered_pipeline_usable`

## Controlled serial/parallel comparison

`benchmarks.compare_kernels` compiles the current formula body with
`parallel=False` and compares it with the application kernel's
`parallel=True` on the unexpanded sensor readings (90,041 complete
readings across 100 tanks). In the serial variant, `prange` runs as a
regular serial loop. The null-quantity filter, the groups, and the
arrays are identical: only the compilation mode changes.

The warm-up uses the actual arrays before the measurements. The order of
the two variants is alternated across repetitions. The time includes the
calls for every tank and the collection of the scores, excluding data
preparation, compilation, numeric verification, and `tracemalloc`.

| Variant | Median |
|---|---:|
| Serial | 0.122712 s |
| Parallel | 0.013351 s |
| Serial/parallel ratio | 9.19× |

The maximum absolute difference observed is `6.1995e-13`. Every
repetition verifies equivalence with `rtol=1e-10` and `atol=1e-10`.

This comparison measures the effect of parallelism with the same
algorithm and usable data. It does not represent the full execution of
an old commit.

## Historical pre-reorder baseline (Reference evidence)

Earlier measurements from September 6, 2026, obtained prior to the
analyzer reordering, are retained in
[pipeline-wa22.json](benchmark-results/pipeline-wa22.json) and
[kernels-wa22.json](benchmark-results/kernels-wa22.json) as historical
baseline evidence.

Those historical runs measured the working tree of the branch based on
commit `bce9f3d1bd151a995916cec0e6c8b34097ac101d`, with local
uncommitted WA-22 changes. The recorded source fingerprints in those JSON
files predate the English translation of comments, docstrings, and
descriptive text; they do not match the current source files. While the
stress formula and generated datasets are unchanged, the analyzer
orchestration order and the benchmark runners are not.

| Metric | Pre-reorder baseline value |
|---|---:|
| Usable rows evaluated in HPC | 270,123 (after expansion) |
| Pipeline total runtime (median) | 0.425713 s |
| Pipeline HPC phase runtime (median) | 0.245746 s |
| Pipeline HPC peak Python memory | 4.776 MiB |
| Kernel serial runtime (median) | 1.138219 s |
| Kernel parallel runtime (median) | 0.127068 s |
| Kernel serial/parallel ratio | 8.96× |

## Interpretation and possible optimizations

With the WA-19 analyzer reordering, the HPC computation is no longer the
overwhelming bottleneck of the pipeline at the verified size (dropping
from the legacy 0.175 s median down to 0.067 s in the same measurement
session, now faster than the 0.088 s input reading phase). Parallelism
in Numba provides a 9.19× kernel speedup on this 32-thread machine.

Symmetry could enable further optimizations for ordinary quantities: the
contribution of pair `(i, j)` matches that of `(j, i)`, and self-pairs
evaluate to zero. However, validation accepts any finite strictly
positive quantity, including extreme subnormal values such as `1e-320`
for which `500.0` divided by the quantity evaluates to infinity. The
self-pair term is then `0.0` multiplied by infinity, yielding `NaN`
rather than zero. In the current full double loop that `NaN` propagates
and the analyzer correctly rejects the dataset with
`DataValidationError`, whereas summing only the pairs `i < j` and
doubling would skip the diagonal entirely and return zero for a
single-reading input. Because skipping the diagonal would change
observable behavior on extreme subnormal quantities, this variant is
deliberately not implemented rather than merely unmeasured.

Distributing the tanks would also require dedicated measurements:
copies, coordination cost, and contention with the Numba threads could
affect the result. The report does not attribute gains to unmeasured
optimizations.
