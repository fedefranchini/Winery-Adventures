"""Interfaccia comune degli analyzer di Winery Adventures."""

from abc import ABC, abstractmethod

import polars as pl


class BaseWineryAnalyzer(ABC):
    """Definisce l'interfaccia comune usata per elaborare i dati della cantina."""

    @abstractmethod
    def analyze_data(self, df: pl.DataFrame) -> pl.DataFrame:
        """Elabora un DataFrame e restituisce il risultato dell'analisi."""
        raise NotImplementedError
