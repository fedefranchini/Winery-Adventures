"""Definizione dell'analyzer dedicato alle trasformazioni dei dati."""

import polars as pl

from winery_adventures.base import BaseWineryAnalyzer


class WineryTransformer(BaseWineryAnalyzer):
    """Raggruppa le trasformazioni applicate alle letture delle cisterne."""

    def __init__(self, tank_info: pl.DataFrame | None):
        self.tank_info = tank_info

    def analyze_data(self, df: pl.DataFrame) -> pl.DataFrame:
        """Applica in sequenza le aggregazioni disponibili."""
        df = self.add_avg_ph_per_tank(df)
        return self.add_num_readings_per_tank(df)

    def add_avg_ph_per_tank(self, df: pl.DataFrame) -> pl.DataFrame:
        """Aggiunge a ogni lettura il pH medio della relativa cisterna."""
        return df.with_columns(pl.col("pH").mean().over("tank_id").alias("avg_pH_per_tank"))

    def add_num_readings_per_tank(self, df: pl.DataFrame) -> pl.DataFrame:
        """Aggiunge a ogni lettura il numero di rilevazioni della cisterna."""
        return df.with_columns(pl.len().over("tank_id").alias("tank_num_readings"))
