# WA-02 — Requirements-tests matrix and data contracts

The matrix links observable requirements to the automated tests that verify
their behavior. It includes both the reference tests and the regression
cases added during development.

## 1. Requirements-tests matrix

### 1.1 Analyzer abstraction

| ID | Requirement | Source test |
|---|---|---|
| REQ-01 | `BaseWineryAnalyzer` is abstract and cannot be instantiated directly. | `test_base_class_is_abstract` |
| REQ-02 | A subclass without `analyze_data` remains abstract; a concrete implementation can return the same object it received. | `test_base_class_abstract_method` |
| REQ-03 | `WineryTransformer` and `WineryHPCComputations` inherit from `BaseWineryAnalyzer`. | `test_subclasses` |

### 1.2 Transformations

| ID | Requirement | Source test |
|---|---|---|
| REQ-04 | `WineryTransformer.analyze_data` orchestrates aggregations, the optional join, and the temperature deviation. | `test_transformer_analyze_data` |
| REQ-05 | `avg_pH_per_tank` contains the tank's average pH, repeated on every one of its rows. | `test_add_avg_ph_per_tank` |
| REQ-06 | `tank_num_readings` contains the number of readings for the tank. | `test_add_num_readings_per_tank` |
| REQ-07 | The standard temperature used by the transformations is `26.0`. | `test_standard_temperature` |
| REQ-08 | `temperature_deviation` is the absolute value of `temp - 26.0`; if `quantity_liters` exists, the deviation scaled to 1,000 liters is also added. | `test_add_temperature_deviation` |
| REQ-09 | The join with `tank_info` expands the varieties and computes `grape_variety_num_readings` considering all tanks associated with the same variety. | `test_add_num_readings_per_grape_variety` |
| REQ-10 | Calling the per-variety transformation directly without `tank_info` raises `AttributeError`; the full orchestration instead skips that step. | `test_add_num_readings_per_grape_variety` |
| REQ-11 | A reading whose `tank_id` does not appear in `tank_info` raises `DataValidationError` before the join, reporting the missing identifiers. | `test_add_num_readings_rejects_unknown_tank` |

For REQ-08, a null value of `quantity_liters` produces a null scaled
deviation only on the corresponding row; if the entire column is missing,
`temperature_deviation_scaled` is not created.

REQ-11 prevents a reading from being silently discarded: the inner join can
therefore only remove tanks from the tank information that have no
readings.

### 1.3 HPC computation

| ID | Requirement | Source test |
|---|---|---|
| REQ-12 | `pairwise_stress_function` is compiled with Numba. | `test_is_function_numba` |
| REQ-13 | The compiled result matches the Python one and the known value of the reduced case. | `test_pairwise_stress_small` |
| REQ-14 | An empty set of computable readings produces a stress of `0.0`. | `test_pairwise_stress_empty_input` |
| REQ-15 | `WineryHPCComputations` computes one score per tank and propagates it to all its rows without mixing different tanks. | `test_hpc_computations_class`, `test_hpc_computations_keeps_tank_scores_separate` |
| REQ-16 | An empty DataFrame preserves the schema and receives a `stress_score` column of type `Float64`. | `test_hpc_computations_empty_dataframe` |
| REQ-17 | The computation only uses rows with a set `quantity_liters`, without removing rows from the output; if a tank has none, or if the column is entirely missing, it assigns `0.0` to all its rows. | `test_hpc_computations_ignores_readings_without_quantity`, `test_hpc_computations_returns_zero_without_computable_quantities` |

For a tank with *n* usable readings, the formula considers every ordered
pair, including self-pairs and reversed pairs:

```text
stress = (1 / n²) · Σᵢ Σⱼ
         (|pHᵢ - pHⱼ| + 2 · |tempᵢ - tempⱼ|)
         · (500 / quantityᵢ + 500 / quantityⱼ)
```

The value computed on the valid subset is also assigned to rows of the
same tank without a quantity. `0.0`, when *n* = 0, indicates that no pairs
can be computed.

### 1.4 Orchestration and logging

| ID | Requirement | Source test |
|---|---|---|
| REQ-18 | The analyzers run in sequence and the final result can be logged to W&B. | `test_pipeline_chain` |
| REQ-19 | With `log_to_wandb=False`, transformations and the HPC computation run without initializing logging. | `test_analyzers_run` |
| REQ-20 | The pipeline supports analyzers compatible with the `analyze_data` method; a no-op chain preserves the DataFrame's identity. | `test_null_analyzers_run` |
| REQ-21 | `log_to_wandb` can be called directly and logs the `stress_score`. | `test_log_wandb` |
| REQ-22 | The application logs describe the phases without including reading values. | `test_pipeline_logs_phases_without_sensor_values` |
| REQ-23 | An analyzer's error is logged and propagated to the caller without exposing dataset data. | `test_pipeline_logs_and_propagates_analyzer_errors` |
| REQ-24 | A W&B run is finished even when logging fails. | `test_wandb_run_is_finished_when_logging_fails` |

### 1.5 File input and output

| ID | Requirement | Source test |
|---|---|---|
| REQ-25 | A valid sensor TSV is read without altering its data. | `test_read_sensors_validates_input` |
| REQ-26 | A non-existent sensor path produces `FileNotFoundError`. | `test_read_sensors_rejects_missing_file` |
| REQ-27 | An invalid schema and an empty file produce `DataValidationError`. | `test_read_sensors_rejects_invalid_schema`, `test_read_sensors_rejects_empty_file` |
| REQ-28 | Comma-separated varieties are converted into a list while reading `tank_info`. | `test_read_tank_info_validates_and_splits_varieties` |
| REQ-29 | Every variety obtained from the split is stripped of surrounding spaces. | `test_read_tank_info_trims_each_variety` |
| REQ-30 | The output is written as a CSV and, when reread, preserves the data. | `test_write_output_writes_csv` |
| REQ-31 | Writing to a non-existent or inaccessible directory produces an explanatory `OSError`. | `test_write_output_reports_unwritable_path` |

### 1.6 Contract validation

| ID | Requirement | Source test |
|---|---|---|
| REQ-32 | A conforming sensor dataset is accepted. | `test_validate_sensors_accepts_contract` |
| REQ-33 | The sensor dataset must contain rows, all required columns, and no nulls in the required fields. | `test_validate_sensors_rejects_missing_columns`, `test_validate_sensors_rejects_empty_data`, `test_validate_sensors_rejects_null_required_values` |
| REQ-34 | `tank_id` must be an integer, `time` a non-empty string, `pH` a finite number between 0 and 14, and `temp` a finite number. | `test_validate_sensors_rejects_invalid_ph`, `test_validate_sensors_rejects_invalid_types_and_values` |
| REQ-35 | `quantity_liters` is optional and nullable; any present value must be numeric, finite, and positive. | `test_validate_sensors_allows_null_optional_quantity`, `test_validate_sensors_allows_missing_optional_quantity`, `test_validate_sensors_rejects_non_positive_quantity`, `test_validate_sensors_rejects_invalid_types_and_values` |
| REQ-36 | A conforming `tank_info` dataset is accepted. | `test_validate_tank_info_accepts_contract` |
| REQ-37 | `tank_info` must contain rows, all required columns, and no null values. | `test_validate_tank_info_rejects_missing_columns`, `test_validate_tank_info_rejects_empty_data`, `test_validate_tank_info_rejects_null_required_values` |
| REQ-38 | In `tank_info`, identifiers and capacities are integers, capacities are positive, varieties are non-empty strings, and `tank_id` values are unique. | `test_validate_tank_info_rejects_invalid_types_and_values`, `test_validate_tank_info_rejects_duplicate_tanks` |
| REQ-39 | The individual comma-separated items must also be non-empty: a value such as `Merlot,,Cabernet` is rejected. | `test_validate_tank_info_rejects_empty_variety_items` |

### 1.7 End-to-end execution

| ID | Requirement | Source test |
|---|---|---|
| REQ-40 | Without `tank_info`, the pipeline preserves the number of readings, omits the grape variety columns, and uses Joblib for a single loading task. | `test_run_full_pipeline_without_tank_info` |
| REQ-41 | With `tank_info`, the pipeline reads both TSV files, expands the rows per variety, produces transformations and stress, and logs the result to W&B. | `test_winery_pipeline_end_to_end` |
| REQ-42 | Without `tank_info`, the acceptance run produces transformations and stress, keeps the original rows, and still logs the result. | `test_winery_pipeline_without_tank_info` |
| REQ-43 | `run_full_pipeline` uses Joblib's `Parallel` and `delayed` to load the available inputs. | `test_winery_pipeline_end_to_end`, `test_winery_pipeline_without_tank_info`, `test_run_full_pipeline_without_tank_info` |
| REQ-44 | With `project_name` omitted, no W&B run is initialized; if `quantity_liters` is missing, the output preserves all rows with `stress_score` equal to `0.0`. | `test_run_full_pipeline_without_quantities_or_wandb` |

The input files are TSV, i.e. tab-separated data. The file name extension
does not change the expected separator.

### 1.8 Benchmark

| ID | Requirement | Source test |
|---|---|---|
| REQ-45 | The same seed generates inputs with the same fingerprints; every iteration exposes the produced rows and non-negative metrics for I/O, transformations, HPC, and output. | `test_benchmark_produces_repeatable_dataset_and_phase_metrics` |
| REQ-46 | The number of tanks, readings, and repetitions must be positive. | `test_benchmark_rejects_non_positive_parameters` |

### 1.9 Dataset generator

| ID | Requirement | Source test |
|---|---|---|
| REQ-47 | The variety pool is sorted, free of duplicates, and made up of labels that can be decomposed into grape variety plus adjective. | `test_generate_variety_pool_is_sorted_and_unique`, `test_generate_variety_pool_labels_combine_grape_and_adjective` |
| REQ-48 | If the requested combinations exceed the available ones, generation still terminates, returning at most every possible combination. | `test_generate_variety_pool_stops_at_available_combinations` |
| REQ-49 | The generated tank information assigns sequential `tank_id` values starting at 1, three distinct comma-separated varieties, and capacities between 1,000 and 1,800 liters; the pool is built internally when not provided. | `test_generate_tank_info_respects_contract`, `test_generate_tank_info_builds_its_own_pool_when_omitted` |
| REQ-50 | The generated readings respect the requested count, `tank_id` within the expected range, `pH` between 3 and 4, `temp` between 22 and 28, and `time` in the `YYYY-MM-DD HH:MM:SS` format starting from `--start-date`; `quantity_liters` is sometimes absent, as expected by the contract. | `test_generate_sensor_data_respects_contract`, `test_generate_sensor_data_produces_optional_missing_quantities` |
| REQ-51 | With the same seed, the generated datasets are identical; different seeds produce different readings. | `test_same_seed_reproduces_identical_datasets`, `test_different_seeds_produce_different_readings` |
| REQ-52 | The generated datasets pass the application validation for sensors and tanks. | `test_generated_datasets_satisfy_the_pipeline_contracts` |
| REQ-53 | The command line exposes `--seed`, `--num-tanks`, `--num-readings`, and `--start-date`; running it writes `data/full_sensors.tsv` and `data/full_tank_info.tsv`, announces their paths, and is reproducible byte for byte. | `test_parse_args_exposes_documented_options`, `test_main_writes_both_tsv_files_in_the_data_directory`, `test_main_is_reproducible_across_runs` |

The generator is the source of the datasets used by the benchmark: the
reproducibility verified by REQ-51 is what makes the measurements in
[benchmark-report.md](benchmark-report.md) comparable.

### 1.10 Final verification regressions

| ID | Requirement | Source test |
|---|---|---|
| REQ-54 | A completely null quantity is also allowed in the TSV; the reader exposes the column as `Float64` without accepting non-empty textual quantities. | `test_read_sensors_accepts_all_null_quantities`, `test_read_sensors_rejects_textual_quantities`, `test_validate_sensors_allows_all_null_quantity` |
| REQ-55 | With all null quantities, the real pipeline preserves the rows and produces zero stress and null scaled deviations, both with and without tank information. | `test_run_full_pipeline_with_all_null_quantities` |
| REQ-56 | The serial/parallel comparison verifies numeric equivalence, preserves timings and source fingerprints, and rejects empty workloads. | `test_kernel_comparison_checks_equivalence_and_records_evidence`, `test_kernel_comparison_rejects_empty_workload` |
| REQ-57 | TSV inference considers the entire file: late quantities or decimals in the sensors are allowed; text in quantities and decimal capacities remain rejected. | `test_read_sensors_infers_numeric_types_from_the_whole_file`, `test_read_sensors_rejects_text_after_numeric_rows`, `test_read_tank_info_rejects_late_decimal_capacity` |
| REQ-58 | Every W&B logging call explicitly uses `finish_previous` and completes the initialization, logging, and run-finishing cycle. | `test_wandb_logging_uses_explicit_reinit_and_finishes_each_run` |
| REQ-59 | If finite but extreme quantities or temperatures produce overflow in the stress, the analyzer stops processing with `DataValidationError` and identifies the tank. | `test_hpc_computations_rejects_non_finite_stress` |

## 2. Input data contracts

Both datasets must contain at least one row. Validation happens before the
transformations.

### 2.1 `sensors_*.tsv`

| Column | Type and constraints | Required | Null allowed |
|---|---|---|---|
| `tank_id` | integer | yes | no |
| `time` | non-empty string | yes | no |
| `pH` | finite numeric, `0 ≤ pH ≤ 14` | yes | no |
| `temp` | finite numeric | yes | no |
| `quantity_liters` | finite and positive numeric when set | no | yes |

The generator uses the `YYYY-MM-DD HH:MM:SS` time format, but validation
only requires a non-empty string and does not interpret the value as a
date.

### 2.2 `tank_info_*.tsv`

| Column | Type and constraints | Required | Null allowed |
|---|---|---|---|
| `tank_id` | integer and unique | yes | no |
| `grape_variety` | non-empty string; multiple values separated by a comma | yes | no |
| `capacity_liters` | positive integer | yes | no |

## 3. Result contract

`write_output` produces a comma-separated CSV. The parent directory must
exist. The result preserves the sensor columns and adds:

| Column | Presence | Meaning |
|---|---|---|
| `avg_pH_per_tank` | always | tank's average pH |
| `tank_num_readings` | always | number of the tank's readings before expansion |
| `temperature_deviation` | always | absolute distance from 26 °C |
| `temperature_deviation_scaled` | if `quantity_liters` exists | deviation scaled to 1,000 liters; null on the single null quantity |
| `stress_score` | always | finite `Float64` score, computed on the available quantities and propagated to the entire tank |
| `capacity_liters` | with `tank_info` | tank's nominal capacity |
| `grape_variety` | with `tank_info` | single variety after expansion |
| `grape_variety_num_readings` | with `tank_info` | readings overall associated with the variety |

The join with `tank_info` is an inner join and replicates each reading for
every associated variety. A reading whose `tank_id` does not appear in the
tank information is not silently discarded: the transformation raises
`DataValidationError` before the join, so the inner join can only exclude
tanks from the tank information that have no readings. If a tank has no
set quantities, `stress_score = 0.0` indicates the absence of computable
pairs.
