# Configurazione dell'ambiente di sviluppo

Il presente documento descrive i requisiti e la procedura per predisporre un
ambiente locale riproducibile per lo sviluppo, l'esecuzione e la verifica di
Winery Adventures.

## Prerequisiti

- Python 3.10 o successivo;
- Git, se il codice sorgente viene acquisito tramite clonazione del repository.

La versione installata di Python può essere verificata con il comando:

```bash
python --version
```

Una versione precedente alla 3.10 non è supportata.

## Creazione dell'ambiente virtuale

Dalla radice del repository:

**macOS / Linux:**
```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
```

**Windows (PowerShell):**
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
```

La directory `.venv` contiene file specifici dell'ambiente locale e non deve
essere inclusa nel controllo versione. Deve pertanto essere ricreata in ogni
nuova installazione.

Per uscire dall'ambiente (comando identico su tutti i sistemi):

```bash
deactivate
```

## Installazione del progetto

Installare package, dipendenze runtime e strumenti di sviluppo in modalità
editable:

```bash
python -m pip install -e ".[dev]"
```

La modalità editable rende immediatamente importabili le modifiche locali senza
reinstallare il package dopo ogni cambiamento.

Verificare l'installazione:

```bash
python -c "import joblib, numba, numpy, polars, tqdm, wandb"
python -c "import winery_adventures"
python -m pip check
```

## Strumenti di qualità

Controllare la formattazione senza modificare i file:

```bash
black --check .
```

Eseguire il linter:

```bash
ruff check .
```

Applicare la formattazione e le correzioni automatiche ai file sorgente
interessati dalla modifica:

**macOS / Linux:**
```bash
black percorso/del/file.py
ruff check --fix percorso/del/file.py
```

**Windows (PowerShell):**
```powershell
black percorso\del\file.py
ruff check --fix percorso\del\file.py
```

I test di riferimento distribuiti con il progetto non devono essere riscritti
automaticamente. Qualsiasi loro modifica deve essere esplicita e motivata.

## Test

La suite completa viene eseguita con:

```bash
pytest
```

Per escludere il test end-to-end marcato come lento:

```bash
pytest -m "not slow"
```

Per produrre la copertura:

```bash
pytest --cov=winery_adventures --cov-report=term-missing
```

## Dataset grandi

Il repository include i dataset ridotti `data/sensors_sample.tsv` e
`data/tank_info_sample.tsv`, destinati agli esempi e alle verifiche rapide. I
dataset completi possono essere generati localmente con:

```bash
python data_generator.py --seed 42 --num-tanks 100 --num-readings 100000
```

Il generatore è configurabile (`--seed`, `--num-tanks`, `--num-readings`,
`--start-date`) e produce output riproducibile a parità di seed. Genera
`data/full_sensors.tsv` e `data/full_tank_info.tsv`: questi file non fanno
parte dei dataset distribuiti nel repository, possono essere rigenerati e
possono raggiungere dimensioni significative.