"""Interfaccia comune degli analyzer di Winery Adventures."""

from abc import ABC, abstractmethod

import polars as pl


class BaseWineryAnalyzer(ABC):
    """Definisce l'interfaccia comune usata per elaborare i dati della cantina."""

    @abstractmethod
    def analyze_data(self, df: pl.DataFrame) -> pl.DataFrame:
        """Elabora le letture secondo la responsabilità dell'analyzer.

        Args:
            df: letture da elaborare.

        Returns:
            Un nuovo DataFrame contenente il risultato dell'analisi.

        Raises:
            NotImplementedError: se una sottoclasse non implementa il metodo.
        """
        raise NotImplementedError
