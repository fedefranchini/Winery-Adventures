"""Definizione dell'analyzer dedicato alle trasformazioni dei dati."""

import polars as pl

from winery_adventures.base import BaseWineryAnalyzer


class WineryTransformer(BaseWineryAnalyzer):
    """Raggruppa le trasformazioni applicate alle letture delle cisterne."""

    STANDARD_TEMPERATURE = 26.0

    def __init__(self, tank_info: pl.DataFrame | None):
        self.tank_info = tank_info

    def analyze_data(self, df: pl.DataFrame) -> pl.DataFrame:
        """Applica in sequenza le trasformazioni disponibili."""
        df = self.add_avg_ph_per_tank(df)
        df = self.add_num_readings_per_tank(df)
        df = self.add_num_readings_per_grape_variety(df)
        return self.add_temperature_deviation(df)

    def add_avg_ph_per_tank(self, df: pl.DataFrame) -> pl.DataFrame:
        """Aggiunge a ogni lettura il pH medio della relativa cisterna."""
        # Calcola la media per cisterna e la propaga su tutte le relative letture.
        return df.with_columns(pl.col("pH").mean().over("tank_id").alias("avg_pH_per_tank"))

    def add_num_readings_per_tank(self, df: pl.DataFrame) -> pl.DataFrame:
        """Aggiunge a ogni lettura il numero di rilevazioni della cisterna."""
        # Conta le righe di ogni cisterna e assegna il conteggio a ogni relativa riga.
        return df.with_columns(pl.len().over("tank_id").alias("tank_num_readings"))

    def add_num_readings_per_grape_variety(self, df: pl.DataFrame) -> pl.DataFrame:
        """Aggiunge a ogni lettura il numero di rilevazioni della relativa varietà d'uva."""
        # Associa a ogni lettura le informazioni della relativa cisterna.
        df = self.tank_info.join(df, on="tank_id")

        # Espande ogni lista di varietà in una riga distinta per vitigno.
        df = df.explode("grape_variety")

        # Conta le rilevazioni associate a ciascuna varietà d'uva.
        return df.with_columns(pl.len().over("grape_variety").alias("grape_variety_num_readings"))

    def add_temperature_deviation(self, df: pl.DataFrame) -> pl.DataFrame:
        """Aggiunge la deviazione termica assoluta, semplice e scalata."""
        # Calcola lo scostamento assoluto dalla temperatura standard.
        result = df.with_columns((pl.col("temp") - self.STANDARD_TEMPERATURE).abs().alias("temperature_deviation"))

        # Se manca la colonna della quantità, conserva soltanto la deviazione semplice.
        if "quantity_liters" not in result.columns:
            return result

        # Normalizza la deviazione rispetto a 1.000 litri di prodotto.
        return result.with_columns(
            (pl.col("temperature_deviation") * 1000 / pl.col("quantity_liters")).alias("temperature_deviation_scaled")
        )
