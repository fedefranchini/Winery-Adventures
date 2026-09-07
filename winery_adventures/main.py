"""Entry point for the full execution of Winery Adventures."""

import joblib

from winery_adventures.computations import WineryHPCComputations
from winery_adventures.io import read_sensors, read_tank_info, write_output
from winery_adventures.pipeline import WineryPipeline
from winery_adventures.transformations import WineryTransformer


def run_full_pipeline(
    input_csv: str,
    tank_info_csv: str | None = None,
    output_csv: str = "output.csv",
    project_name: str | None = None,
) -> None:
    """Load the data, run the analyzers, and save the result.

    The two datasets are read in parallel when both sensor readings and
    tank information are present. Logging to W&B is only performed when
    ``project_name`` is set. If ``tank_info_csv`` is not provided, only the
    transformations that require the tank information are skipped.

    Args:
        input_csv: path to the TSV containing the sensor readings.
        tank_info_csv: optional path to the TSV with the tank information.
        output_csv: CSV destination for the processed result.
        project_name: optional W&B project name to send aggregated metrics
            to. If omitted, W&B logging is disabled.

    Raises:
        FileNotFoundError: if a required input file does not exist.
        DataValidationError: if a dataset does not satisfy the expected contract.
        OSError: if the result cannot be written.
    """
    tasks = [joblib.delayed(read_sensors)(input_csv)]

    if tank_info_csv is not None:
        tasks.append(joblib.delayed(read_tank_info)(tank_info_csv))

    # The results returned by Joblib avoid dependencies on shared memory
    # and keep loading compatible with different backends.
    loaded_datasets = joblib.Parallel(n_jobs=-1, prefer="threads")(tasks)

    sensors_df = loaded_datasets[0]
    tank_info_df = loaded_datasets[1] if tank_info_csv is not None else None

    analyzers = [WineryTransformer(tank_info=tank_info_df), WineryHPCComputations()]
    pipeline = WineryPipeline(analyzers=analyzers, project_name=project_name)
    result_df = pipeline.run(sensors_df, log_to_wandb=project_name is not None)

    write_output(result_df, output_csv)
