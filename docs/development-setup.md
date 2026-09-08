# Development environment setup

This document describes how to set up a local environment to develop, run,
and verify Winery Adventures.

## Prerequisites

- Python 3.10 or later;
- Git to acquire and version the source code.

The requirement declared by the package is Python 3.10 or later; the
continuous integration pipeline explicitly checks Python 3.10. Check the
available version with:

```bash
python --version
```

## Acquiring the repository

Clone the repository and move into its root:

```bash
git clone https://github.com/fedefranchini/Winery-Adventures.git
cd Winery-Adventures
```

All the following commands assume this working directory.

## Creating the virtual environment

**macOS / Linux:**

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
```

**Windows (PowerShell):**

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
```

The `.venv` directory contains files specific to the local installation
and must not be versioned. To leave the virtual environment:

```bash
deactivate
```

## Installing the project

Install the package, the runtime dependencies, and the development tools
in editable mode:

```bash
python -m pip install -e ".[dev]"
```

In this mode, changes to the source become immediately importable without
reinstalling the package. Then check the environment and dependencies:

```bash
python -c "import joblib, numba, numpy, polars, sphinx, myst_parser, tqdm, wandb"
python -c "import winery_adventures"
python -m pip check
```

The Polars minimum is `1.44.1`, the version verified with the explicit
`empty_as_null` option of `explode`; compatibility with `1.0` is not
declared. The W&B minimum is `0.19.10`, which supports
`reinit="finish_previous"` in place of the deprecated boolean. The bounds
are defined in `pyproject.toml`: after changing them, the editable
installation must be repeated, not just the environment reactivated.

## Configuring Weights & Biases

To log runs online, authenticate the environment with:

```bash
wandb login
```

For local checks without authentication, offline mode can be used instead.

**macOS / Linux:**

```bash
export WANDB_MODE=offline
```

**Windows (PowerShell):**

```powershell
$env:WANDB_MODE="offline"
```

Instructions for running the pipeline are provided in the
[usage guide](usage-guide.md).

## Quality checks

Run the linter and check formatting without modifying the files:

```bash
ruff check .
black --check .
```

During development, automatic fixes must be limited to the files affected
by the task:

**macOS / Linux:**

```bash
ruff check --fix path/to/file.py
black path/to/file.py
```

**Windows (PowerShell):**

```powershell
ruff check --fix path\to\file.py
black path\to\file.py
```

The reference tests distributed with the project must not be rewritten
automatically. Any change to them must be explicit and justified.

## Tests and coverage

Run the entire suite with:

```bash
pytest
```

To exclude the end-to-end tests marked as slow:

```bash
pytest -m "not slow"
```

To produce the coverage report for the application package and the
generator, using the same sources and the 90% threshold configured for the
CI:

```bash
pytest --cov --cov-report=term-missing
```

The `.coverage` file produced by the command is a local artifact and is
not part of the source.

## Sphinx documentation

The documentation includes the Markdown guides and the API reference
derived from the docstrings. Generate it in strict mode, treating warnings
as errors:

```bash
sphinx-build -W --keep-going -b html docs docs/_build/html
```

At the end, the starting page is at `docs/_build/html/index.html`.

## Generated datasets

The repository includes the reduced datasets `data/sensors_sample.tsv` and
`data/tank_info_sample.tsv`, intended for examples and quick checks. To
generate larger datasets locally:

```bash
python data_generator.py --seed 42 --num-tanks 100 --num-readings 100000
```

The available options are `--seed`, `--num-tanks`, `--num-readings`, and
`--start-date`. With the same parameters and seed, the same data is
produced in the `data/full_sensors.tsv` and `data/full_tank_info.tsv`
files. These artifacts are regenerable, can be large, and are not part of
the distributed datasets.

## Benchmark

A quick check of the benchmark can be run with:

```bash
python -m benchmarks.benchmark_pipeline --tanks 10 --readings 1000 --repetitions 2 --seed 42 --output benchmark-results.json
```

For the measurement expected on 100,000 readings:

```bash
python -m benchmarks.benchmark_pipeline --tanks 100 --readings 100000 --repetitions 3 --seed 42 --output benchmark-results.json
```

The script accepts `--order` to select the analyzer execution order:
`hpc-first` (the production default, running HPC before grape variety
expansion) and `transformer-first` (the legacy order kept for the
controlled before/after comparison).

The JSON file contains the environment, parameters, SHA-256 fingerprints
of the inputs and benchmark sources, measurements of the individual
iterations, and a per-phase summary covering preflight tank-coverage
validation alongside input reading, transformations, HPC, and output
writing. The first run may take longer because the dataset is
regenerated from scratch.

Methodology, collected measurements, and a controlled comparison between
serial and parallel compilation of the current formula (run via
`benchmarks.compare_kernels`) are reported in the
[benchmark report](benchmark-report.md).

## Local verification sequence

Before proposing a Pull Request, run from the root:

```bash
python -m pip check
ruff check .
black --check .
pytest --cov --cov-report=term-missing
sphinx-build -W --keep-going -b html docs docs/_build/html
```

## Troubleshooting

### PowerShell activation blocked

If the local policy prevents running `Activate.ps1`, enable it for the
current process only and repeat the activation:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

### Dependencies or imports unavailable

Check that `.venv` is activated, repeat
`python -m pip install -e ".[dev]"`, and run `python -m pip check`.

### W&B authentication requested

Run `wandb login` for online mode, or set
`WANDB_MODE=offline` before starting the pipeline or the manual tests.

### Sphinx build not clean

Remove any previous `docs/_build` directory, rerun the command in strict
mode, and fix every reported reference or docstring.

### Slower initial benchmark

Numba's JIT compilation introduces a cost on the first call. The runner
performs a warm-up on both signatures used in practice, so compilation
stays outside the measured windows; overall startup still takes longer
because of dataset generation.
