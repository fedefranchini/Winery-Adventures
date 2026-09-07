"""Sequential pipeline and application logging for Winery Adventures."""

import logging
from collections.abc import Sequence
from typing import Protocol

import polars as pl
import wandb

logger = logging.getLogger(__name__)


class WineryAnalyzer(Protocol):
    """Structural contract of the components the pipeline can run."""

    def analyze_data(self, df: pl.DataFrame) -> pl.DataFrame:
        """Describe the operation required of every pipeline component.

        Args:
            df: data received from the previous component.

        Returns:
            The processed DataFrame to pass to the next component.
        """
        ...


class WineryPipeline:
    """Runs a list of analyzers in sequence and handles wandb logging."""

    def __init__(self, analyzers: Sequence[WineryAnalyzer], project_name: str | None = None):
        """Configure the processing sequence.

        Args:
            analyzers: components run in the order provided.
            project_name: optional W&B project name.
        """
        self.analyzers = analyzers
        self.project_name = project_name

    def run(self, df: pl.DataFrame, log_to_wandb: bool = False) -> pl.DataFrame:
        """Apply the analyzers in sequence and, if requested, log the result.

        Args:
            df: the pipeline's initial readings.
            log_to_wandb: enable sending the result to W&B.

        Returns:
            The DataFrame produced by the last analyzer.

        Raises:
            Exception: propagates the error raised by an analyzer or by W&B.
        """

        logger.info("Starting winery pipeline with %d analyzers", len(self.analyzers))

        # Each analyzer's output becomes the next analyzer's input.
        for analyzer in self.analyzers:
            analyzer_name = type(analyzer).__name__
            logger.info("Running analyzer %s", analyzer_name)
            # Log which component failed without including dataset values.
            try:
                df = analyzer.analyze_data(df)
            except Exception:
                logger.error("Analyzer %s failed", analyzer_name)
                raise

        # Remote logging can be disabled for tests and local runs.
        if log_to_wandb:
            self.log_to_wandb(df)

        logger.info("Winery pipeline completed")
        return df

    def log_to_wandb(self, df: pl.DataFrame) -> None:
        """Send a summary of the processed DataFrame to W&B.

        Args:
            df: the pipeline result to summarize and log.

        Raises:
            Exception: propagates W&B initialization or logging errors,
                still finishing the already started run.
        """

        metrics: dict[str, int | float] = {"output_rows": df.height}

        if "tank_id" in df.columns:
            metrics["tank_count"] = df.get_column("tank_id").n_unique()

        if "stress_score" in df.columns:
            stress_scores = df.get_column("stress_score").drop_nulls().cast(pl.Float64)
            metrics["stress_score_count"] = stress_scores.len()
            if not stress_scores.is_empty():
                # The existing metric name represents the mean; min and max complete the summary.
                metrics["stress_score"] = float(stress_scores.mean())
                metrics["stress_score_min"] = float(stress_scores.min())
                metrics["stress_score_max"] = float(stress_scores.max())

        logger.info("Starting wandb logging")
        # Start a new run, finishing any previous run, without deprecated options.
        run = wandb.init(project=self.project_name, reinit="finish_previous")
        # Avoid payloads proportional to the dataset size and always finish the created run.
        try:
            run.log(metrics)
        finally:
            run.finish()
        logger.info("wandb logging completed")
