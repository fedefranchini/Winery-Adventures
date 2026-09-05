# Winery-Adventures

A data science pipeline for ingesting, transforming and analyzing wine fermentation sensor 
data.

---da

## Struttura del repository

Cartelle principali del progetto:

```
Winery-Adventures/
├── winery_adventures/       # package applicativo
│   ├── base.py               # BaseWineryAnalyzer (classe astratta)
│   ├── transformations.py    # WineryTransformer (pH medio, conteggi, deviazione termica)
│   ├── computations.py       # WineryHPCComputations (stress pairwise, Numba)
│   ├── pipeline.py           # WineryPipeline (orchestrazione + logging wandb)
│   ├── io.py                 # lettura/scrittura TSV, validazione
│   ├── validation.py         # contratti dati e controlli di schema
│   └── main.py                # run_full_pipeline (punto di ingresso end-to-end)
├── benchmarks/               # benchmark riproducibile di tempo/memoria
├── tests/                    # test unitari (unit/) e end-to-end (acceptance/)
├── data/                     # dataset di esempio
├── data_generator.py         # generatore di dataset riproducibili e configurabili
└── docs/                     # documentazione di progetto
```

## Architettura e UML

Diagramma delle classi, di sequenza e dei casi d'uso del sistema sono
descritti in [`docs/architecture.md`](docs/architecture.md).

---

### Moduli principali (`winery_adventures/`)

---

#### `base.py`

Definisce `BaseWineryAnalyzer`, la classe astratta che stabilisce il
contratto comune (`analyze_data`) a cui si conformano tutti gli analyzer del
progetto.

---

#### `transformations.py`

Implementa `WineryTransformer`: calcola il pH medio e il numero di letture
per cisterna, il conteggio delle letture per varietà d'uva (tramite join con
`tank_info`), e la deviazione dalla temperatura standard.

---

#### `computations.py`

Implementa `WineryHPCComputations` e `pairwise_stress_function`, che calcola
un indice di stress da fermentazione confrontando ogni coppia di letture di
una cisterna. La funzione è compilata con Numba e parallelizzata (`prange`)
per le prestazioni.

---

#### `pipeline.py`

Implementa `WineryPipeline`, che esegue in sequenza una lista di analyzer e
gestisce il logging opzionale del risultato su Weights & Biases.

---

#### `io.py`

Funzioni per leggere i file TSV di input (sensori e cisterne, con validazione
dello schema) e per scrivere il file di output finale.

---

#### `validation.py`

Controlli sui contratti dati (colonne obbligatorie, tipi, valori nulli o
fuori range ammessi) applicati durante la lettura dei file.

---

#### `main.py`

Contiene `run_full_pipeline`, il punto di ingresso end-to-end: orchestra
lettura (in parallelo con Joblib), trasformazioni, calcolo HPC, logging e
scrittura dell'output.

---

### Test (`tests/`)

---

#### `unit/`

Un file di test per ciascun modulo sopra, inclusi i casi limite (input
vuoti, valori nulli, schemi non validi).

---

#### `acceptance/`

Test end-to-end che verificano l'intero flusso tramite `run_full_pipeline`,
sia con sia senza il file opzionale `tank_info`.

---

### Benchmark (`benchmarks/`)

---

#### `benchmark_pipeline.py`

Misura tempo di esecuzione e memoria delle fasi principali della pipeline
(I/O, trasformazioni, HPC, output) su un dataset generato in modo
riproducibile.

## Installazione e sviluppo

Il progetto richiede Python 3.10+ e si installa in un ambiente virtuale in
modalità editable (`pip install -e ".[dev]"`), con `black`/`ruff` per stile e
lint e `pytest` per i test. La procedura completa, i comandi per macOS/Linux e
Windows, e come generare dataset di grandi dimensioni sono descritti in
[`docs/development-setup.md`](docs/development-setup.md).

## Utilizzo

`run_full_pipeline` (in `winery_adventures/main.py`) è il punto di ingresso
end-to-end della pipeline: legge i file di input, applica le trasformazioni
e il calcolo HPC, e scrive il risultato su file.

```python
from winery_adventures.main import run_full_pipeline

run_full_pipeline(
    input_csv="data/sensors_sample.tsv",
    tank_info_csv="data/tank_info_sample.tsv",  # opzionale
    output_csv="data/results.csv",
    project_name="WineryAdventures",
)
```

- **`input_csv`** *(obbligatorio)*: percorso del file TSV con le rilevazioni dei sensori (pH, temperatura, quantità)
- **`tank_info_csv`** *(opzionale, default `None`)*: percorso del file TSV con le informazioni sulle cisterne (varietà d'uva, capacità). Se omesso, la pipeline funziona comunque, semplicemente senza calcolare le colonne che dipendono da questi dati (es. conteggio letture per varietà)
- **`output_csv`**: percorso dove viene scritto il file con i risultati
- **`project_name`**: nome del progetto usato per il logging su Weights & Biases

Per la descrizione completa delle colonne prodotte in output, altri esempi
d'uso, e la risoluzione dei problemi più comuni, vedi
[`docs/usage-guide.md`](docs/usage-guide.md).

## Project Management

Lo sviluppo è organizzato con metodologia **Kanban** tramite il
GitHub Project **Winery Adventures — Development**. Le attività della WBS sono
rappresentate esclusivamente da draft card `WA-01`–`WA-22`; non vengono usate
GitHub Issues come unità di lavoro.

- [Winery Adventures — Development](https://github.com/users/fedefranchini/projects/3)
- [Pull Request del repository](https://github.com/fedefranchini/Winery-Adventures/pulls)
- Workflow: `Ready` → `In Progress` → `Review / Testing` → `Done`
- WIP limit: massimo un task principale `In Progress` per ciascun componente
- Branch: `feature/WA-XX-descrizione`, `fix/WA-XX-descrizione` oppure
  `docs/WA-XX-descrizione`
- Pull Request: titolo `WA-XX — descrizione`, test superati e peer review
  dell'altro componente prima del merge

La WBS, le regole operative e la Definition of Done sono descritte in
[`docs/project-management.md`](docs/project-management.md).
Le attività da svolgere in ciascuna fase sono illustrate in
[`docs/development-phases.md`](docs/development-phases.md).