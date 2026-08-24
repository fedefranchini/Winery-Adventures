# Fasi di sviluppo

Questo documento descrive come svolgere il progetto Winery Adventures, dalla
preparazione iniziale alla verifica finale. Le fasi indicano un ordine logico,
ma il lavoro è gestito con Kanban: una nuova attività può iniziare soltanto
quando le sue dipendenze sono concluse e la card si trova in `Ready`.

## Regole valide in tutte le fasi

Per ogni attività si deve:

1. verificare che le dipendenze indicate nella card siano concluse;
2. spostare la card da `Ready` a `In Progress`;
3. rispettare il limite di un solo task principale `In Progress` per persona;
4. creare una branch `feature/WA-XX-descrizione`,
   `fix/WA-XX-descrizione` o `docs/WA-XX-descrizione`;
5. limitare commit e modifiche allo scope della card e usare `WA-XX` nei commit;
6. eseguire i test e i controlli richiesti dalla card;
7. aprire una Pull Request `WA-XX — descrizione` e aggiungerla al Project;
8. spostare la card in `Review / Testing` e richiedere la peer review;
9. correggere le osservazioni emerse durante la review;
10. spostare la card in `Done` soltanto dopo test, approvazione e merge.

## Fase 1 — Avvio e definizione dei requisiti

### Obiettivo

Preparare il processo di lavoro e trasformare README e test forniti in
requisiti chiari e verificabili. Questa fase riduce il rischio di implementare
comportamenti diversi da quelli richiesti.

### Attività

- **WA-01 — Project management:** configurare il Project Kanban, i campi, gli
  stati, la WBS, il workflow, il WIP limit e la documentazione organizzativa.
- **WA-02 — Requisiti e test:** creare una matrice che colleghi ogni requisito
  alla sua origine e ai test che lo verificano. Definire inoltre schemi dati,
  gestione dei null, input opzionali ed errori attesi.
- **WA-04 — Toolchain:** predisporre package Python, dipendenze riproducibili,
  Pytest, formatter e linter.

### Cosa si deve produrre

- Project pubblico e collegato al repository;
- requisiti funzionali e non funzionali tracciabili;
- descrizione degli schemi TSV di input e output;
- ambiente di sviluppo installabile in modo riproducibile;
- comandi documentati per lint, formattazione e test.

### Criteri di uscita

La fase è conclusa quando entrambi gli studenti possono installare l'ambiente,
comprendono i risultati attesi e possono raccogliere i test senza errori di
configurazione.

## Fase 2 — Progettazione e fondazioni

### Obiettivo

Definire l'architettura prima dell'implementazione e costruire i componenti di
base dai quali dipende il resto del sistema.

### Attività

- **WA-03 — Architettura e UML:** definire responsabilità, relazioni ed
  ereditarietà attraverso diagrammi di classi, sequenza e casi d'uso.
- **WA-05 — Continuous Integration:** configurare controlli automatici di lint
  e test sulle Pull Request.
- **WA-06 — BaseWineryAnalyzer:** implementare la classe astratta e il contratto
  comune `analyze_data`.
- **WA-07 — I/O:** implementare lettura TSV, validazione iniziale, join opzionale
  delle informazioni sulle cisterne e scrittura dell'output.

### Cosa si deve fare

1. Stabilire quali classi possiedono ciascuna responsabilità.
2. Definire il flusso dal caricamento dei file fino all'output finale.
3. Evitare dipendenze circolari e duplicazioni tra componenti.
4. Implementare prima le interfacce e i contratti condivisi.
5. Verificare I/O sia con `tank_info` sia senza il file opzionale.
6. Rendere obbligatori i controlli CI nelle normali Pull Request.

### Criteri di uscita

UML e codice di base devono essere coerenti; la classe astratta deve superare i
test dedicati; lettura e scrittura devono funzionare su file temporanei validi;
la CI deve eseguire correttamente i controlli configurati.

## Fase 3 — Implementazione delle funzionalità principali

### Obiettivo

Realizzare le trasformazioni, il calcolo HPC e l'orchestrazione end-to-end
richiesti dai test del progetto.

### Attività sulle trasformazioni

- **WA-08:** calcolare pH medio e numero di letture per cisterna.
- **WA-09:** espandere le varietà associate a ogni cisterna e calcolare il
  numero di letture per vitigno.
- **WA-10:** calcolare la deviazione dalla temperatura standard di 26 °C e la
  versione scalata su 1000 litri quando la quantità è disponibile.

Le trasformazioni devono preservare le colonne necessarie alle fasi successive,
gestire i null secondo il contratto e produrre esattamente i nomi di colonna
richiesti dai test.

### Attività di calcolo e integrazione

- **WA-11 — HPC:** implementare la formula pairwise O(n²), gestire l'input vuoto,
  compilare realmente la funzione con Numba e aggiungere `stress_score`.
- **WA-12 — Pipeline:** eseguire gli analyzer nella sequenza configurata e
  integrare il logging Weights & Biases, attivabile e disattivabile.
- **WA-13 — Flusso completo:** integrare I/O, trasformazioni, HPC, Joblib, wandb
  e scrittura dell'output tramite `run_full_pipeline`.

### Cosa si deve verificare

- risultati numerici degli esempi noti;
- comportamento con quantità nulla o colonna quantità assente;
- aggregazioni tra più cisterne e più vitigni;
- compilazione Numba della funzione di stress;
- chiamata effettiva di Joblib;
- presenza di `avg_pH_per_tank` e `stress_score` nell'output;
- produzione delle nove righe attese dal test di accettazione.

### Criteri di uscita

Tutti i test unitari relativi a base, trasformazioni, computazioni e pipeline
devono passare. Il flusso end-to-end deve generare un output valido a partire
dai dataset di esempio.

## Fase 4 — Robustezza, testing e performance

### Obiettivo

Rendere il sistema affidabile su input reali e dimostrare che può gestire
dataset di almeno 100.000 righe con prestazioni misurabili.

### Attività

- **WA-14 — Robustezza:** validare gli schemi, gestire file assenti o invalidi e
  aggiungere logging applicativo comprensibile.
- **WA-15 — Generatore dati:** rendere configurabili seed, numero di cisterne e
  numero di letture, assicurando output riproducibili.
- **WA-16 — Test ed edge case:** aggiungere test per input vuoti, null, schemi
  errati e valori limite; misurare la copertura.
- **WA-17 — Integrazione:** completare i test end-to-end verificando output,
  Joblib e wandb senza dipendenze esterne instabili.
- **WA-18 — Profiling:** misurare tempo e memoria con una metodologia
  ripetibile e identificare i colli di bottiglia.
- **WA-19 — Ottimizzazione:** intervenire soltanto sui problemi dimostrati dal
  profiling e confrontare risultati prima e dopo.

### Procedura per le performance

1. Generare un dataset riproducibile di almeno 100.000 righe.
2. Registrare ambiente, parametri e versione del codice.
3. Eseguire più misurazioni, non una singola esecuzione.
4. Raccogliere tempo totale, tempo delle fasi critiche e memoria utilizzata.
5. Conservare una baseline prima delle ottimizzazioni.
6. Applicare una modifica alla volta e rieseguire test e benchmark.
7. Documentare anche ottimizzazioni tentate che non producono benefici.

### Criteri di uscita

La suite completa deve passare, gli errori devono essere comprensibili, il
dataset grande deve essere gestito senza errori e il report deve mostrare dati
riproducibili. Ogni ottimizzazione deve preservare la correttezza funzionale.

## Fase 5 — Documentazione, verifica e consegna

### Obiettivo

Rendere il progetto comprensibile, riproducibile e pronto per la valutazione e
la dimostrazione finale.

### Attività

- **WA-20 — Documentazione tecnica:** configurare Sphinx, completare docstring e
  generare la documentazione API senza warning bloccanti.
- **WA-21 — Guida utente:** documentare installazione, configurazione, uso,
  esempi, input, output e troubleshooting nel README.
- **WA-22 — Verifica finale:** controllare CI, qualità, UML, report, Definition
  of Done e preparare una demo riproducibile.

### Cosa si deve fare

1. Provare le istruzioni di installazione partendo da un ambiente pulito.
2. Eseguire l'esempio end-to-end descritto nel README.
3. Controllare che UML, codice e documentazione descrivano lo stesso sistema.
4. Generare la documentazione Sphinx e correggere link o riferimenti errati.
5. Eseguire lint, test unitari, test di accettazione e benchmark finali.
6. Preparare una demo breve con input, esecuzione, output e risultati di
   performance.
7. Verificare la Definition of Done di tutte le card prima di chiuderle.

### Criteri di uscita

Il progetto è pronto quando un'altra persona può installarlo ed eseguirlo
seguendo soltanto la documentazione, tutti i controlli CI sono verdi, le Pull
Request sono state revisionate e gli artefatti richiesti sono presenti.

## Responsabilità e collaborazione

L'Owner indicato nella card è responsabile della realizzazione e delle
correzioni. L'altro componente deve effettuare la peer review, controllando in
particolare:

- aderenza ad acceptance criteria e dipendenze;
- chiarezza e manutenibilità della soluzione;
- presenza e qualità dei test;
- assenza di modifiche estranee allo scope;
- aggiornamento della documentazione interessata.

Gli story point rappresentano complessità e rischio, non ore garantite. Il team
deve confrontare periodicamente stime e tempo effettivo e discutere eventuali
scostamenti senza creare attività artificiali o modificare lo scope soltanto
per ottenere una divisione numerica perfetta.
