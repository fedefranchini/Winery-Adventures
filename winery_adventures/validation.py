"""Validazione dei contratti dati usati da Winery Adventures."""

import polars as pl


class DataValidationError(ValueError):
    """Segnala che un dataset non rispetta il contratto applicativo."""


SENSOR_REQUIRED_COLUMNS = {"tank_id", "time", "pH", "temp"}
TANK_INFO_REQUIRED_COLUMNS = {"tank_id", "grape_variety", "capacity_liters"}


def _require_columns(df: pl.DataFrame, required: set[str], dataset_name: str) -> None:
    # Confronta il contratto atteso con le colonne effettivamente disponibili.
    missing = sorted(required.difference(df.columns))
    if missing:
        raise DataValidationError(f"{dataset_name} is missing required columns: {', '.join(missing)}")


def _require_rows(df: pl.DataFrame, dataset_name: str) -> None:
    # Un dataset privo di righe non può essere elaborato dalla pipeline.
    if df.is_empty():
        raise DataValidationError(f"{dataset_name} must contain at least one row")


def _require_no_nulls(df: pl.DataFrame, columns: set[str], dataset_name: str) -> None:
    # Raccoglie tutte le colonne obbligatorie che contengono almeno un valore nullo.
    columns_with_nulls = sorted(column for column in columns if df.get_column(column).null_count() > 0)
    if columns_with_nulls:
        raise DataValidationError(
            f"{dataset_name} contains null values in required columns: " f"{', '.join(columns_with_nulls)}"
        )


def _require_numeric(df: pl.DataFrame, columns: set[str], dataset_name: str) -> None:
    # Verifica i tipi tramite lo schema Polars senza convertire silenziosamente i dati.
    invalid = sorted(column for column in columns if not df.schema[column].is_numeric())
    if invalid:
        raise DataValidationError(f"{dataset_name} requires numeric columns: {', '.join(invalid)}")


def _require_integer(df: pl.DataFrame, column: str, dataset_name: str) -> None:
    # Gli identificativi e le capacità devono mantenere un tipo intero.
    if not df.schema[column].is_integer():
        raise DataValidationError(f"{dataset_name} requires {column} to be an integer column")


def validate_sensors(df: pl.DataFrame) -> None:
    """Verifica schema e valori essenziali delle letture dei sensori.

    Controlla colonne obbligatorie, presenza di righe e valori, tipi, intervallo
    del pH, finitezza delle temperature e positività delle quantità opzionali.

    Args:
        df: dataset dei sensori da validare.

    Raises:
        DataValidationError: se il dataset non rispetta uno dei vincoli.
    """
    # Applica prima i controlli strutturali comuni a tutte le letture.
    _require_columns(df, SENSOR_REQUIRED_COLUMNS, "Sensor data")
    _require_rows(df, "Sensor data")
    _require_no_nulls(df, SENSOR_REQUIRED_COLUMNS, "Sensor data")
    _require_numeric(df, {"tank_id", "pH", "temp"}, "Sensor data")
    _require_integer(df, "tank_id", "Sensor data")

    # Il tempo resta testuale perché il formato viene conservato nell'output.
    if df.schema["time"] != pl.String:
        raise DataValidationError("Sensor data requires time to be a string column")

    if df.get_column("time").str.strip_chars().eq("").any():
        raise DataValidationError("Sensor data contains an empty time value")

    # Il pH deve essere finito e compreso nell'intervallo fisico 0-14.
    ph_values = df.get_column("pH").cast(pl.Float64)
    if not ph_values.is_finite().all() or (ph_values < 0).any() or (ph_values > 14).any():
        raise DataValidationError("Sensor data contains an invalid pH value")

    # Sono rifiutati NaN e valori infiniti che renderebbero inaffidabili i calcoli.
    temperature_values = df.get_column("temp").cast(pl.Float64)
    if not temperature_values.is_finite().all():
        raise DataValidationError("Sensor data contains a non-finite temperature value")

    # La quantità è opzionale e può contenere null, ma i valori presenti devono essere positivi.
    if "quantity_liters" in df.columns:
        _require_numeric(df, {"quantity_liters"}, "Sensor data")
        quantities = df.get_column("quantity_liters").drop_nulls().cast(pl.Float64)
        if not quantities.is_finite().all() or (quantities <= 0).any():
            raise DataValidationError("Sensor data contains an invalid quantity_liters value")


def validate_tank_info(df: pl.DataFrame) -> None:
    """Verifica schema e valori essenziali delle informazioni sulle cisterne.

    Controlla colonne obbligatorie, tipi, vitigni non vuoti, capacità positive e
    unicità degli identificativi.

    Args:
        df: anagrafica delle cisterne da validare.

    Raises:
        DataValidationError: se il dataset non rispetta uno dei vincoli.
    """
    # Controlla la struttura prima dello split della colonna grape_variety.
    _require_columns(df, TANK_INFO_REQUIRED_COLUMNS, "Tank information")
    _require_rows(df, "Tank information")
    _require_no_nulls(df, TANK_INFO_REQUIRED_COLUMNS, "Tank information")
    _require_numeric(df, {"tank_id", "capacity_liters"}, "Tank information")
    _require_integer(df, "tank_id", "Tank information")
    _require_integer(df, "capacity_liters", "Tank information")

    if df.schema["grape_variety"] != pl.String:
        raise DataValidationError("Tank information requires grape_variety to be a string column")

    if df.get_column("grape_variety").str.strip_chars().eq("").any():
        raise DataValidationError("Tank information contains an empty grape_variety value")

    # Una capacità nulla, infinita o non positiva non descrive una cisterna valida.
    capacities = df.get_column("capacity_liters").cast(pl.Float64)
    if not capacities.is_finite().all() or (capacities <= 0).any():
        raise DataValidationError("Tank information contains an invalid capacity_liters value")

    # Ogni cisterna deve comparire una sola volta nel dataset anagrafico.
    if df.get_column("tank_id").n_unique() != df.height:
        raise DataValidationError("Tank information contains duplicate tank_id values")
