# WA-02 — Matrice requisiti-test e contratti dati

Si derivano i requisiti funzionali dai test presenti in `tests/`. Per ogni
requisito è indicata l'origine (il test che lo richiede) e gli eventuali edge
case (null, colonne opzionali, input assenti, errori attesi).

## 1. Matrice requisiti-test

### 1.1 `tests/unit/test_base.py`

| ID | Requisito | Componente | Test di origine | Edge case |
|---|---|---|---|---|
| REQ-01 | `BaseWineryAnalyzer` è una classe astratta: non deve poter essere istanziata direttamente (`TypeError`). | BaseWineryAnalyzer | `test_base_class_is_abstract` | — |
| REQ-02 | Una sottoclasse che non implementa `analyze_data` non deve essere istanziabile (`TypeError`); una che lo implementa deve funzionare, e se il metodo restituisce l'input invariato deve restituire esattamente lo stesso oggetto ricevuto (identità, non copia). | BaseWineryAnalyzer | `test_base_class_abstract_method` | — |
| REQ-03 | `WineryTransformer` e `WineryHPCComputations` devono essere sottoclassi di `BaseWineryAnalyzer`. | Transformer, HPC | `test_subclasses` | — |

### 1.2 `tests/unit/test_transformations.py`

| ID | Requisito | Componente | Test di origine | Edge case |
|---|---|---|---|---|
| REQ-04 | `analyze_data` di `WineryTransformer` deve orchestrare tutte le trasformazioni, restituendo un DataFrame con `avg_pH_per_tank`, `tank_num_readings`, `grape_variety_num_readings` e `temperature_deviation_scaled` presenti contemporaneamente. | WineryTransformer | `test_transformer_analyze_data` | — |
| REQ-05 | `add_avg_ph_per_tank` aggiunge `avg_pH_per_tank`: per ogni riga, la media di `pH` calcolata su tutte le righe con lo stesso `tank_id` (valore ripetuto su ogni riga del gruppo). | WineryTransformer | `test_add_avg_ph_per_tank` | — |
| REQ-06 | `add_num_readings_per_tank` aggiunge `tank_num_readings`: per ogni riga, il numero totale di righe con lo stesso `tank_id`. | WineryTransformer | `test_add_num_readings_per_tank` | — |
| REQ-07 | `WineryTransformer` definisce una costante di classe `STANDARD_TEMPERATURE = 26.0`, riferimento per la deviazione termica. | WineryTransformer | `test_standard_temperature` | — |
| REQ-08 | `add_temperature_deviation` calcola sempre `temperature_deviation = \|temp - STANDARD_TEMPERATURE\|`. Se la colonna `quantity_liters` esiste, calcola anche `temperature_deviation_scaled = temperature_deviation * 1000 / quantity_liters`. | WineryTransformer | `test_add_temperature_deviation` | (a) `quantity_liters` null su una riga → `temperature_deviation_scaled` null solo su quella riga; (b) colonna `quantity_liters` assente → `temperature_deviation_scaled` non viene creata |
| REQ-09 | `add_num_readings_per_grape_variety` espande ogni lettura in una riga per varietà coltivata nella cisterna (join con `tank_info`), e aggiunge `grape_variety_num_readings`: per ogni varietà, la somma delle letture di tutte le cisterne che la coltivano. | WineryTransformer | `test_add_num_readings_per_grape_variety` | stessa varietà in più cisterne → somma le letture di tutte |
| REQ-10 | Se `WineryTransformer` è costruito senza `tank_info` (`None`), chiamare `add_num_readings_per_grape_variety` deve sollevare `AttributeError`. | WineryTransformer | `test_add_num_readings_per_grape_variety` | `tank_info` assente |

### 1.3 `tests/unit/test_computations.py`

| ID | Requisito | Componente | Test di origine | Edge case |
|---|---|---|---|---|
| REQ-11 | `pairwise_stress_function` deve essere compilata con Numba. | HPC | `test_is_function_numba` | — |
| REQ-12 | `WineryHPCComputations.analyze_data` raggruppa le letture per `tank_id`, calcola un unico valore di stress per cisterna con `pairwise_stress_function` e lo assegna a `stress_score` su ogni riga della cisterna. Formula: per ogni coppia (i,j) di letture, `(|pH_i - pH_j| + |temp_i - temp_j|·2) · (500/qty_i + 500/qty_j)`, sommato su tutte le coppie e diviso per n². Se n=0, restituisce 0.0. | WineryHPCComputations | `test_hpc_computations_class` | — |

### 1.4 `tests/unit/test_pipeline.py`

| ID | Requisito | Componente | Test di origine | Edge case |
|---|---|---|---|---|
| REQ-13 | `WineryPipeline` accetta una lista di analyzer e un `project_name`; `run(df, log_to_wandb=True)` esegue ogni analyzer in sequenza (output di uno → input del successivo) e, se `log_to_wandb=True`, inizializza una run wandb e logga il risultato finale. | WineryPipeline | `test_pipeline_chain` | — |
| REQ-14 | Con `log_to_wandb=False`, la pipeline produce comunque l'output corretto (stesse colonne) senza richiedere il logging wandb. | WineryPipeline | `test_analyzers_run` | `log_to_wandb=False` |
| REQ-15 | `WineryPipeline` accetta analyzer arbitrari purché espongano `analyze_data` (duck typing, non serve ereditare da `BaseWineryAnalyzer`); `project_name` è opzionale. Se ogni analyzer restituisce l'oggetto ricevuto invariato, `run` deve restituire esattamente lo stesso oggetto di input (identità). | WineryPipeline | `test_null_analyzers_run` | analyzer "no-op"; `project_name` non fornito |
| REQ-16 | `WineryPipeline` espone un metodo pubblico `log_to_wandb(df)`, utilizzabile indipendentemente da `run`, che logga il DataFrame passato su una run wandb. | WineryPipeline | `test_log_wandb` | — |

### 1.5 `tests/acceptance/test_winery_acceptance.py`

| ID | Requisito | Componente | Test di origine | Edge case |
|---|---|---|---|---|
| REQ-17 | `run_full_pipeline` legge il file sensori e, se fornito, il file `tank_info` (entrambi TSV/CSV separati da tab), esegue l'intera pipeline (trasformazioni + HPC), scrive il risultato su `output_csv`, e logga su wandb usando `project_name`. | run_full_pipeline | `test_winery_pipeline_end_to_end` | — |
| REQ-18 | Se `tank_info` è fornito, l'output finale è espanso per varietà (nel caso di esempio: 9 righe); deve contenere sia le colonne di trasformazione (`avg_pH_per_tank`) sia quelle HPC (`stress_score`). | run_full_pipeline | `test_winery_pipeline_end_to_end` | — |
| REQ-19 | `run_full_pipeline` deve usare effettivamente Joblib (`Parallel`/`delayed`) per almeno una parte del lavoro. | run_full_pipeline | `test_winery_pipeline_end_to_end` | — |

## 2. Contratti dati

### 2.1 `sensors_*.tsv`

| Colonna | Tipo | Obbligatoria (colonna) | Null ammesso (valore) |
|---|---|---|---|
| `tank_id` | int | sì | no |
| `time` | string `"YYYY-MM-DD HH:MM:SS"` | sì | no |
| `pH` | float | sì | no |
| `temp` | float | sì | no |
| `quantity_liters` | int | **no** (la colonna può mancare del tutto) | **sì**, anche se la colonna è presente |

### 2.2 `tank_info_*.tsv`

| Colonna | Tipo | Obbligatoria (colonna) | Null ammesso (valore) |
|---|---|---|---|
| `tank_id` | int | sì | no |
| `grape_variety` | string, valori multipli separati da virgola (es. `"CannonauVellutato,BovaleBarricato"`) | sì | no |
| `capacity_liters` | int | sì | no |
