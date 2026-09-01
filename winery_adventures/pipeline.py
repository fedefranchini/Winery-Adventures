"""Pipeline sequenziale e logging applicativo di Winery Adventures."""

import logging
from collections.abc import Sequence

import polars as pl
import wandb

from winery_adventures.base import BaseWineryAnalyzer

logger = logging.getLogger(__name__)


class WineryPipeline:
    """Esegue in sequenza una lista di analyzer e gestisce il logging su wandb."""

    def __init__(self, analyzers: Sequence[BaseWineryAnalyzer], project_name: str | None = None):
        """Configura la sequenza di elaborazione.

        Args:
            analyzers: componenti eseguiti nell'ordine fornito.
            project_name: nome opzionale del progetto W&B.
        """
        self.analyzers = analyzers
        self.project_name = project_name

    def run(self, df: pl.DataFrame, log_to_wandb: bool = False) -> pl.DataFrame:
        """Applica gli analyzer in sequenza e, se richiesto, registra il risultato.

        Args:
            df: letture iniziali della pipeline.
            log_to_wandb: abilita l'invio del risultato a W&B.

        Returns:
            Il DataFrame prodotto dall'ultimo analyzer.

        Raises:
            Exception: propaga l'errore sollevato da un analyzer o da W&B.
        """

        logger.info("Starting winery pipeline with %d analyzers", len(self.analyzers))

        # L'output di ogni analyzer diventa l'input del successivo.
        for analyzer in self.analyzers:
            analyzer_name = type(analyzer).__name__
            logger.info("Running analyzer %s", analyzer_name)
            # Registra quale componente è fallito senza includere i valori del dataset.
            try:
                df = analyzer.analyze_data(df)
            except Exception:
                logger.error("Analyzer %s failed", analyzer_name)
                raise

        # Il logging remoto resta disattivabile per test ed esecuzioni locali.
        if log_to_wandb:
            self.log_to_wandb(df)

        logger.info("Winery pipeline completed")
        return df

    def log_to_wandb(self, df: pl.DataFrame) -> None:
        """Invia il contenuto del DataFrame a W&B.

        Args:
            df: risultato della pipeline da registrare.

        Raises:
            Exception: propaga gli errori di inizializzazione o logging di W&B,
                chiudendo comunque la run già avviata.
        """

        logger.info("Starting wandb logging")
        wandb.init(project=self.project_name, reinit=True)
        # Chiude sempre la run, anche se wandb rifiuta i dati durante il logging.
        try:
            wandb.log(df.to_dict(as_series=False))
        finally:
            wandb.finish()
        logger.info("wandb logging completed")
