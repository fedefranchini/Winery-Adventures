"""Funzioni di I/O per la pipeline Winery Adventures.

Si occupano di leggere i file TSV di input (sensori e, opzionalmente, le
informazioni sulle cisterne) e di scrivere il risultato finale elaborato.
Non applicano trasformazioni sui dati: quello è compito di
``WineryTransformer`` e ``WineryHPCComputations``.
"""

import polars as pl


def read_sensors(path: str) -> pl.DataFrame:
    """Legge il file TSV delle rilevazioni dei sensori.

    Il file è obbligatorio e separato da tabulazioni, con colonne
    ``tank_id``, ``time``, ``pH``, ``temp`` e, opzionalmente,
    ``quantity_liters``.

    Args:
        path: percorso del file TSV da leggere.

    Returns:
        Il DataFrame con i dati grezzi dei sensori.
    """
    return pl.read_csv(path, separator="\t")


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
    """
    df = pl.read_csv(path, separator="\t")
    return df.with_columns(pl.col("grape_variety").str.split(","))


def write_output(df: pl.DataFrame, path: str) -> None:
    """Scrive il DataFrame elaborato su file CSV.

    Args:
        df: il DataFrame finale (trasformazioni + HPC applicate) da salvare.
        path: percorso del file di output.
    """
    df.write_csv(path)
