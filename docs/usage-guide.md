# Guida all'uso


Si descrive come eseguire la pipeline di Winery Adventures,
e interpretare l'output prodotto.

## Esecuzione della pipeline

`run_full_pipeline` (in `winery_adventures/main.py`) è il punto di ingresso
end-to-end: legge i dati (in parallelo, con Joblib), esegue trasformazioni e
calcolo HPC, logga il risultato su Weights & Biases e scrive l'output finale.

```python
from winery_adventures.main import run_full_pipeline

run_full_pipeline(
    input_csv="data/sensors_sample.tsv",
    tank_info_csv="data/tank_info_sample.tsv",  # opzionale: può essere omesso (None)
    output_csv="data/results.csv",
    project_name="WineryAdventures",
)
```

`tank_info_csv` è opzionale: se omesso, la pipeline funziona comunque,
saltando le trasformazioni che richiedono i dati delle cisterne (es. conteggio
letture per varietà d'uva).

### Logging su Weights & Biases

Se non hai un account wandb configurato, imposta `WANDB_MODE=offline` prima di
eseguire, per evitare richieste di login:

**macOS / Linux:**
```bash
WANDB_MODE=offline python tuo_script.py
```

**Windows (PowerShell):**
```powershell
$env:WANDB_MODE="offline"; python tuo_script.py
```

## Output

Il file scritto in `output_csv` contiene una riga per lettura sensore
(espansa per varietà d'uva, se `tank_info_csv` è fornito), con le colonne
originali più quelle calcolate dalla pipeline:

| Colonna | Sempre presente? | Descrizione |
|---|---|---|
| `avg_pH_per_tank` | sì | pH medio della cisterna |
| `tank_num_readings` | sì | numero di letture della cisterna |
| `temperature_deviation` | sì | scostamento assoluto dalla temperatura standard (26°C) |
| `temperature_deviation_scaled` | solo se `quantity_liters` è presente | deviazione normalizzata su 1000 litri |
| `grape_variety_num_readings` | solo se `tank_info_csv` è fornito | numero di letture per varietà d'uva |
| `stress_score` | sì | indice di stress da fermentazione (calcolo HPC, formula pairwise) |

## Contratti dati di input

Gli schemi attesi per `sensors_*.tsv` e `tank_info_*.tsv` (colonne, tipi,
valori nulli ammessi) sono documentati in
[`requirements-tests-matrix.md`](requirements-tests-matrix.md).