# Configurazione dell'ambiente di sviluppo

Il presente documento descrive i requisiti e la procedura per predisporre un
ambiente locale riproducibile per lo sviluppo, l'esecuzione e la verifica di
Winery Adventures.

## Prerequisiti

- Python 3.10 o successivo;
- Git, se il codice sorgente viene acquisito tramite clonazione del repository.

La versione installata di Python può essere verificata con il comando:

```powershell
python --version
```

Una versione precedente alla 3.10 non è supportata.

## Creazione dell'ambiente virtuale

Dalla radice del repository:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
```

La directory `.venv` contiene file specifici dell'ambiente locale e non deve
essere inclusa nel controllo versione. Deve pertanto essere ricreata in ogni
nuova installazione.

Per uscire dall'ambiente:

```powershell
deactivate
```

## Installazione del progetto

Installare package, dipendenze runtime e strumenti di sviluppo in modalità
editable:

```powershell
python -m pip install -e ".[dev]"
```

La modalità editable rende immediatamente importabili le modifiche locali senza
reinstallare il package dopo ogni cambiamento.

Verificare l'installazione:

```powershell
python -c "import joblib, numba, numpy, polars, tqdm, wandb"
python -c "import winery_adventures"
python -m pip check
```

## Strumenti di qualità

Controllare la formattazione senza modificare i file:

```powershell
black --check .
```

Eseguire il linter:

```powershell
ruff check .
```

Applicare la formattazione e le correzioni automatiche ai file sorgente
interessati dalla modifica:

```powershell
black percorso\del\file.py
ruff check --fix percorso\del\file.py
```

I test di riferimento distribuiti con il progetto non devono essere riscritti
automaticamente. Qualsiasi loro modifica deve essere esplicita e motivata.

## Test

La suite completa viene eseguita con:

```powershell
pytest
```

Per escludere il test end-to-end marcato come lento:

```powershell
pytest -m "not slow"
```

Per produrre la copertura:

```powershell
pytest --cov=winery_adventures --cov-report=term-missing
```

## Dataset grandi

Il repository include i dataset ridotti `data/sensors_sample.tsv` e
`data/tank_info_sample.tsv`, destinati agli esempi e alle verifiche rapide. I
dataset completi possono essere generati localmente con:

```powershell
python data_generator.py
```

Il generatore produce `data/full_sensors.tsv` e `data/full_tank_info.tsv`. Questi
file non fanno parte dei dataset distribuiti nel repository, possono essere
rigenerati e possono raggiungere dimensioni significative.
