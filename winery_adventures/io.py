"""Funzioni di I/O per la pipeline Winery Adventures.

Si occupano di leggere i file TSV di input (sensori e, opzionalmente, le
informazioni sulle cisterne) e di scrivere il risultato finale elaborato.
Non applicano trasformazioni sui dati: quello è compito di
``WineryTransformer`` e ``WineryHPCComputations``.
"""

import logging
from pathlib import Path

import polars as pl

from winery_adventures.validation import (
    DataValidationError,
    validate_sensors,
    validate_tank_info,
)

logger = logging.getLogger(__name__)


def _read_tsv(path: str, dataset_name: str) -> pl.DataFrame:
    # Verifica il percorso prima di delegare la lettura a Polars.
    input_path = Path(path)
    if not input_path.is_file():
        logger.error("%s file was not found", dataset_name)
        raise FileNotFoundError(f"{dataset_name} file not found: {path}")

    # Converte gli errori del parser in un errore applicativo più comprensibile.
    try:
        return pl.read_csv(input_path, separator="\t")
    except pl.exceptions.PolarsError as exc:
        logger.error("Unable to read %s as a valid TSV file", dataset_name)
        raise DataValidationError(f"Unable to read {dataset_name} as a valid TSV file") from exc


def read_sensors(path: str) -> pl.DataFrame:
    """Legge il file TSV delle rilevazioni dei sensori.

    Il file è obbligatorio e separato da tabulazioni, con colonne
    ``tank_id``, ``time``, ``pH``, ``temp`` e, opzionalmente,
    ``quantity_liters``.

    Args:
        path: percorso del file TSV da leggere.

    Returns:
        Il DataFrame con i dati grezzi dei sensori.

    Raises:
        FileNotFoundError: se il percorso non identifica un file.
        DataValidationError: se il TSV non è leggibile o non rispetta il
            contratto dei sensori.
    """
    # Valida le letture prima che raggiungano trasformazioni e calcoli HPC.
    df = _read_tsv(path, "Sensor data")
    validate_sensors(df)
    logger.info("Sensor data loaded and validated (%d rows)", df.height)
    return df


def read_tank_info(path: str) -> pl.DataFrame:
    """Legge il file TSV delle informazioni sulle cisterne.

    Il file contiene ``tank_id``, ``grape_variety`` (varietà multiple
    separate da virgola) e ``capacity_liters``. La colonna
    ``grape_variety`` viene qui trasformata da stringa a lista, così le
    trasformazioni a valle (es. ``WineryTransformer.add_num_readings_per_grape_variety``)
    ricevono i dati già pronti all'uso.

    Args:
        path: percorso del file TSV da leggere.

    Returns:
        Il DataFrame con ``grape_variety`` già splittata in lista.

    Raises:
        FileNotFoundError: se il percorso non identifica un file.
        DataValidationError: se il TSV non è leggibile o non rispetta il
            contratto delle cisterne.
    """
    # La validazione avviene sulla stringa originale, prima dello split dei vitigni.
    df = _read_tsv(path, "Tank information")
    validate_tank_info(df)
    logger.info("Tank information loaded and validated (%d rows)", df.height)
    return df.with_columns(pl.col("grape_variety").str.split(","))


def write_output(df: pl.DataFrame, path: str) -> None:
    """Scrive il DataFrame elaborato su file CSV.

    Args:
        df: il DataFrame finale (trasformazioni + HPC applicate) da salvare.
        path: percorso del file di output.

    Raises:
        OSError: se il file di output non può essere scritto.
    """
    # Mantiene un messaggio uniforme in caso di percorso di output non scrivibile.
    try:
        df.write_csv(path)
    except OSError as exc:
        logger.error("Unable to write pipeline output")
        raise OSError(f"Unable to write pipeline output: {path}") from exc

    logger.info("Pipeline output written (%d rows)", df.height)
