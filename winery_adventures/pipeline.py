"""Definizione della pipeline per l'esecuzione degli analyzer sequenzialmente ed eventuale logging su wandb"""

import polars as pl
import wandb


class WineryPipeline:
    """Esegue in sequenza una lista di analyzer e gestisce il logging su wandb."""

    def __init__(self, analyzers, project_name: str | None = None):
        self.analyzers = analyzers
        self.project_name = project_name

    def run(self, df: pl.DataFrame, log_to_wandb: bool = False) -> pl.DataFrame:
        """Applica in sequenza ogni gli analyzer al DataFrame e, se necessario, logga su wandb."""

        for analyzer in self.analyzers:
            df = analyzer.analyze_data(df)

        if log_to_wandb:
            self.log_to_wandb(df)  # Logga le metriche calcolate dall'analyzer su wandb

        return df

    def log_to_wandb(self, df: pl.DataFrame):
        """Logga il contenuto del DataFrame su wandb."""

        wandb.init(project=self.project_name, reinit=True)
        wandb.log(df.to_dict(as_series=False))  # Logga il DataFrame completo come tabella
        wandb.finish()
