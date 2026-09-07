# WA-18 / WA-19 — Benchmark and optimization report

The measurements from September 6, 2026 verify the current pipeline and
isolate the effect of Numba's parallel compilation. The raw results are
kept in the [pipeline-wa22.json](benchmark-results/pipeline-wa22.json) and
[kernels-wa22.json](benchmark-results/kernels-wa22.json) files.

## Version and environment

The measured version is the working tree of `fix/WA-22-final-verification`,
based on `bce9f3d1bd151a995916cec0e6c8b34097ac101d`, with local WA-22
changes. The base commit alone does not identify the measured code: the
comparison JSON also keeps the SHA-256 fingerprints of the sources
involved. The fingerprints are of local bytes, so they include line
endings.

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
| Rows usable in the HPC computation | 270,123 after expansion |
| Repetitions | 5 per measurement |

Both runs produced the same inputs:

- sensors: `fdd4518535ce9dd98c4e034cb1f9ae5464771549ed7c7433bd10b8384d80d557`;
- tanks: `27b9dfe8c3ddf683a6b19499b3fbca38b158059b36e9dfdb96e5933cd37d0de4`.

## Reproduction

Run from the root, after installing the project. The destination
directory must exist. The following commands create new local reports:

```bash
python -m benchmarks.benchmark_pipeline --tanks 100 --readings 100000 --repetitions 5 --seed 42 --output benchmark-results.json
python -m benchmarks.compare_kernels --tanks 100 --readings 100000 --repetitions 5 --seed 42 --output kernel-comparison.json
```

Compare hashes, parameters, versions, and thread count before comparing
timings. The attached JSON files keep every repetition, not just the
median. Absolute timings vary with the machine, the load, and the run
conditions; the observed ratios are not guarantees for other
installations.

## Current pipeline

The runner measures TSV reading, transformations, HPC, and CSV writing.
Input generation and initial compilation are excluded from the
iterations; W&B is not activated by the benchmark. Score finiteness is
verified at every iteration.

Reading includes type inference over the entire TSV, needed to recognize
quantities and decimals even when they appear beyond the first rows. The
following timings include this cost; they do not reuse the measurements
from before the reader fix.

| Measure | Median | Minimum | Maximum |
|---|---:|---:|---:|
| Total | 0.425713 s | 0.406889 s | 0.457873 s |
| Input reading | 0.098503 s | 0.088663 s | 0.108369 s |
| Transformations | 0.045130 s | 0.041729 s | 0.053300 s |
| HPC | 0.245746 s | 0.233024 s | 0.277466 s |
| Output writing | 0.033972 s | 0.032711 s | 0.035799 s |

Phase medians are not necessarily additive. The total also includes
coordination and result checking.
Every iteration produced 300,000 rows with finite stress values.

| Phase | Peak of traced Python allocations |
|---|---:|
| Input reading | 0.111 MiB |
| Transformations | 0.778 MiB |
| HPC | 4.776 MiB |
| Output writing | 0.002 MiB |

`tracemalloc` does not measure the process's entire memory and does not
include all the native allocations of Polars, NumPy, and Numba. These
values cannot be used as an estimate of the required RAM.

## Controlled serial/parallel comparison

`benchmarks.compare_kernels` compiles the current formula body with
`parallel=False` and compares it with the application kernel's
`parallel=True`. In the serial variant, `prange` runs as a regular serial
loop. The null-quantity filter, the groups, and the arrays are identical:
only the compilation mode changes.

The warm-up uses the actual arrays before the measurements. The order of
the two variants is alternated across repetitions. The time includes the
calls for every tank and the collection of the scores, excluding data
preparation, compilation, numeric verification, and `tracemalloc`.

| Variant | Median |
|---|---:|
| Serial | 1.138219 s |
| Parallel | 0.127068 s |
| Serial/parallel ratio | 8.96× |

The maximum absolute difference observed is `4.2491e-12`. Every
repetition verifies equivalence with `rtol=1e-10` and `atol=1e-10`.

This comparison measures the effect of parallelism with the same
algorithm and usable data. It does not represent the full execution of an
old commit. The earlier historical comparison numbers, without the
original artifacts, are not used as conclusive evidence.

## Interpretation and possible optimizations

The HPC computation remains the dominant phase at the verified size.
Parallelism reduces the formula's time, while keeping the quadratic cost
relative to each tank's usable readings.

Symmetry could enable further optimizations without changing the
formula: the contribution of pair `(i, j)` matches that of `(j, i)`, and
self-pairs contribute zero. Summing only the pairs `i < j` and doubling
the result would therefore preserve the mathematical value, aside from
floating-point summation order effects. This variant is not implemented
or measured in the present work.

Distributing the tanks would also require dedicated measurements: copies,
coordination cost, and contention with the Numba threads could affect the
result. The report does not attribute gains to unmeasured optimizations.
