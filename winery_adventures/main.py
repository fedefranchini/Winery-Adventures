import joblib

from winery_adventures.computations import WineryHPCComputations
from winery_adventures.io import read_sensors, read_tank_info, write_output
from winery_adventures.pipeline import WineryPipeline
from winery_adventures.transformations import WineryTransformer


def run_full_pipeline(input_csv, tank_info_csv=None, output_csv="output.csv", project_name=None):
    """Legge i dati (in parallelo), esegue la pipeline e scrive il risultato.

    tank_info_csv opzionale: se non
        fornito, la pipeline funziona comunque, saltando le trasformazioni
        che richiedono i dati delle cisterne (es. conteggio per varietà).
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
