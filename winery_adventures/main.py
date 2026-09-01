"""Punto di ingresso per l'esecuzione completa di Winery Adventures."""

import joblib

from winery_adventures.computations import WineryHPCComputations
from winery_adventures.io import read_sensors, read_tank_info, write_output
from winery_adventures.pipeline import WineryPipeline
from winery_adventures.transformations import WineryTransformer


def run_full_pipeline(
    input_csv: str,
    tank_info_csv: str | None = None,
    output_csv: str = "output.csv",
    project_name: str | None = None,
) -> None:
    """Carica i dati, esegue gli analyzer e salva il risultato.

    La lettura dei due dataset avviene in parallelo quando sono presenti sia i
    sensori sia le informazioni delle cisterne. Il logging remoto su W&B viene
    delegato alla pipeline. Se ``tank_info_csv`` non è fornito, vengono saltate
    soltanto le trasformazioni che richiedono l'anagrafica delle cisterne.

    Args:
        input_csv: percorso del TSV contenente le letture dei sensori.
        tank_info_csv: percorso opzionale del TSV con le informazioni delle
            cisterne.
        output_csv: destinazione CSV del risultato elaborato.
        project_name: nome del progetto W&B a cui inviare le metriche.

    Raises:
        FileNotFoundError: se un file di input richiesto non esiste.
        DataValidationError: se un dataset non rispetta il contratto previsto.
        OSError: se il risultato non può essere scritto.
    """
    results = {}

    def _load_sensors():
        results["sensors"] = read_sensors(input_csv)

        # results viene riempito via 'closure': il ritorno di Parallel non è affidabile nei test.

    def _load_tank_info():
        results["tank_info"] = read_tank_info(tank_info_csv)

    tasks = [joblib.delayed(_load_sensors)()]

    if tank_info_csv is not None:  # tank_info è opzionale: si legge solo se fornito
        tasks.append(joblib.delayed(_load_tank_info)())

    joblib.Parallel(n_jobs=-1, prefer="threads")(tasks)  # 'threads' per condividere la memoria

    sensors_df = results["sensors"]
    tank_info_df = results.get("tank_info")  # restituisce None se tank_info_csv non fornito

    analyzers = [WineryTransformer(tank_info=tank_info_df), WineryHPCComputations()]
    pipeline = WineryPipeline(analyzers=analyzers, project_name=project_name)
    result_df = pipeline.run(sensors_df, log_to_wandb=True)

    write_output(result_df, output_csv)
