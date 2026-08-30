"""Definizione dell'analyzer dedicato ai calcoli ad alte prestazioni."""

import numpy as np
import polars as pl
from numba import njit

from winery_adventures.base import BaseWineryAnalyzer


@njit
def pairwise_stress_function(
    pH_vals: np.ndarray,
    temp_vals: np.ndarray,
    quantity_vals: np.ndarray,
) -> float:
    """Calcola lo stress medio confrontando tutte le coppie di letture."""
    # Il numero di letture delimita i cicli e serve per la normalizzazione finale.
    n = len(pH_vals)

    # Un insieme senza letture non produce alcun valore di stress.
    if n == 0:
        return 0.0

    stress_sum = 0.0

    # Confronta ogni lettura con tutte le altre, incluse le coppie inverse.
    for i in range(n):
        for j in range(n):
            # Misura le differenze tra la coppia, attribuendo peso doppio alla temperatura.
            pH_dev = abs(pH_vals[i] - pH_vals[j])
            temp_dev = abs(temp_vals[i] - temp_vals[j]) * 2.0

            # Volumi minori producono un fattore più alto perché sono considerati meno stabili.
            quantity_factor = (500.0 / quantity_vals[i]) + (500.0 / quantity_vals[j])

            # Combina le deviazioni e le pesa in base al volume delle due letture.
            stress_sum += (pH_dev + temp_dev) * quantity_factor

    # Normalizza la somma rispetto alle n^2 coppie confrontate.
    return stress_sum / (n * n)


class WineryHPCComputations(BaseWineryAnalyzer):
    """Raggruppa i calcoli numerici intensivi applicati alle letture."""

    def analyze_data(self, df: pl.DataFrame) -> pl.DataFrame:
        """Calcola e assegna lo stress di fermentazione di ogni cisterna."""
        stress_by_tank = {}

        # Suddivide il DataFrame per cisterna mantenendo l'ordine originale dei gruppi.
        for tank_df in df.partition_by("tank_id", maintain_order=True):
            # Tutte le righe del gruppo condividono il medesimo identificativo.
            tank_id = tank_df.get_column("tank_id")[0]

            # Converte le colonne numeriche in array Float64 compatibili con Numba.
            stress_by_tank[tank_id] = pairwise_stress_function(
                tank_df.get_column("pH").cast(pl.Float64).to_numpy(),
                tank_df.get_column("temp").cast(pl.Float64).to_numpy(),
                tank_df.get_column("quantity_liters").cast(pl.Float64).to_numpy(),
            )

        # Assegna a ogni riga lo stress calcolato per la relativa cisterna.
        stress_scores = []
        for tank_id in df.get_column("tank_id").to_list():
            stress_scores.append(stress_by_tank[tank_id])

        # Aggiunge i risultati al DataFrame senza rimuovere le colonne esistenti.
        return df.with_columns(pl.Series("stress_score", stress_scores, dtype=pl.Float64))
