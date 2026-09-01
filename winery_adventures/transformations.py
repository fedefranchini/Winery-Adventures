"""Definizione dell'analyzer dedicato alle trasformazioni dei dati."""

import polars as pl

from winery_adventures.base import BaseWineryAnalyzer


class WineryTransformer(BaseWineryAnalyzer):
    """Raggruppa le trasformazioni applicate alle letture delle cisterne."""

    STANDARD_TEMPERATURE = 26.0

    def __init__(self, tank_info: pl.DataFrame | None = None):
        """Configura le trasformazioni con i dati anagrafici opzionali.

        Args:
            tank_info: informazioni delle cisterne, già validate e con
                ``grape_variety`` rappresentata come lista.
        """
        self.tank_info = tank_info

    def analyze_data(self, df: pl.DataFrame) -> pl.DataFrame:
        """Applica in sequenza tutte le trasformazioni disponibili.

        Args:
            df: letture dei sensori da arricchire.

        Returns:
            Le letture con aggregazioni per cisterna, eventuali aggregazioni
            per vitigno e deviazioni termiche.

        Raises:
            polars.exceptions.ColumnNotFoundError: se manca una colonna richiesta.
        """
        df = self.add_avg_ph_per_tank(df)
        df = self.add_num_readings_per_tank(df)
        if self.tank_info is not None:
            df = self.add_num_readings_per_grape_variety(df)
        return self.add_temperature_deviation(df)

    def add_avg_ph_per_tank(self, df: pl.DataFrame) -> pl.DataFrame:
        """Aggiunge a ogni lettura il pH medio della relativa cisterna.

        Args:
            df: letture contenenti ``tank_id`` e ``pH``.

        Returns:
            Le letture con la colonna ``avg_pH_per_tank``.

        Raises:
            polars.exceptions.ColumnNotFoundError: se manca una colonna richiesta.
        """
        # Calcola la media per cisterna e la propaga su tutte le relative letture.
        return df.with_columns(pl.col("pH").mean().over("tank_id").alias("avg_pH_per_tank"))

    def add_num_readings_per_tank(self, df: pl.DataFrame) -> pl.DataFrame:
        """Aggiunge a ogni lettura il numero di rilevazioni della cisterna.

        Args:
            df: letture contenenti ``tank_id``.

        Returns:
            Le letture con la colonna ``tank_num_readings``.

        Raises:
            polars.exceptions.ColumnNotFoundError: se manca ``tank_id``.
        """
        # Conta le righe di ogni cisterna e assegna il conteggio a ogni relativa riga.
        return df.with_columns(pl.len().over("tank_id").alias("tank_num_readings"))

    def add_num_readings_per_grape_variety(self, df: pl.DataFrame) -> pl.DataFrame:
        """Aggiunge il numero di rilevazioni della relativa varietà d'uva.

        Args:
            df: letture contenenti ``tank_id``.

        Returns:
            Le letture associate ai vitigni e corredate dalla colonna
            ``grape_variety_num_readings``. Una cisterna con più vitigni produce
            una riga per ciascun vitigno.

        Raises:
            AttributeError: se ``tank_info`` non è stato fornito.
            polars.exceptions.ColumnNotFoundError: se manca una colonna richiesta.
        """
        # Associa a ogni lettura le informazioni della relativa cisterna.
        df = self.tank_info.join(df, on="tank_id")

        # Espande ogni lista di varietà in una riga distinta per vitigno.
        df = df.explode("grape_variety")

        # Conta le rilevazioni associate a ciascuna varietà d'uva.
        return df.with_columns(pl.len().over("grape_variety").alias("grape_variety_num_readings"))

    def add_temperature_deviation(self, df: pl.DataFrame) -> pl.DataFrame:
        """Aggiunge la deviazione termica assoluta, semplice e scalata.

        Args:
            df: letture contenenti ``temp`` ed eventualmente
                ``quantity_liters``.

        Returns:
            Le letture con ``temperature_deviation`` e, quando la quantità è
            disponibile, ``temperature_deviation_scaled``.

        Raises:
            polars.exceptions.ColumnNotFoundError: se manca ``temp``.
        """
        # Calcola lo scostamento assoluto dalla temperatura standard.
        result = df.with_columns((pl.col("temp") - self.STANDARD_TEMPERATURE).abs().alias("temperature_deviation"))

        # Se manca la colonna della quantità, conserva soltanto la deviazione semplice.
        if "quantity_liters" not in result.columns:
            return result

        # Normalizza la deviazione rispetto a 1.000 litri di prodotto.
        return result.with_columns(
            (pl.col("temperature_deviation") * 1000 / pl.col("quantity_liters")).alias("temperature_deviation_scaled")
        )
