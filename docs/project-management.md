# Project Management

## Metodo Kanban

Winery Adventures adotta Kanban per rendere visibili priorità, dipendenze e
stato del lavoro, mantenendo un flusso continuo compatibile con un gruppo di
due studenti. Il Project usa gli stati `Backlog`, `Ready`, `In Progress`,
`Review / Testing` e `Done`.

Le unità di lavoro sono esclusivamente draft card del GitHub Project. Ogni card
contiene risultato richiesto, acceptance criteria, dipendenze e test; le
dipendenze sono testuali e fanno riferimento ai codici `WA-XX`, senza creare
GitHub Issues.

## Stima e ripartizione

L'effort usa la scala 1, 2, 3, 5 e 8 story point. La stima considera ampiezza,
complessità, integrazioni, incertezza e lavoro di verifica, non il tempo in ore.
La ripartizione è basata sull'effort reale e non sul numero di card:

- MarrasFederico: **47 SP**
- FedeFranchini: **48 SP**

## Work Breakdown Structure

| Codice | Risultato | Owner | SP | Priority | Area | Dipendenze | Stato iniziale |
|---|---|---|---:|---|---|---|---|
| WA-01 | Configurare Project Kanban, campi, workflow e documentazione di project management | MarrasFederico | 3 | High | Documentation | — | Ready |
| WA-02 | Creare matrice requisiti-test e chiarire contratti dati, null ed errori | FedeFranchini | 3 | High | Requirements | — | Ready |
| WA-03 | Progettare architettura e UML: classi, sequenza e casi d'uso | FedeFranchini | 5 | High | Architecture | WA-02 | Backlog |
| WA-04 | Configurare package, dipendenze riproducibili, formatter, linter e Pytest | MarrasFederico | 5 | High | Architecture | — | Ready |
| WA-05 | Configurare CI per lint, test unitari, acceptance test e stato PR | FedeFranchini | 3 | High | Testing | WA-04 | Backlog |
| WA-06 | Implementare `BaseWineryAnalyzer` e i contratti astratti | MarrasFederico | 2 | High | Architecture | WA-03, WA-04 | Backlog |
| WA-07 | Implementare caricamento TSV, join opzionale e scrittura output | FedeFranchini | 5 | High | Backend | WA-02, WA-04 | Backlog |
| WA-08 | Implementare pH medio e conteggio letture per cisterna | MarrasFederico | 3 | High | Backend | WA-06 | Backlog |
| WA-09 | Implementare espansione e conteggio letture per vitigno | FedeFranchini | 5 | High | Data | WA-06, WA-07 | Backlog |
| WA-10 | Implementare deviazione termica semplice e scalata, inclusi null | MarrasFederico | 3 | High | Backend | WA-02, WA-06 | Backlog |
| WA-11 | Implementare formula pairwise e analyzer HPC compilato con Numba | MarrasFederico | 8 | High | Backend | WA-02, WA-06 | Backlog |
| WA-12 | Implementare pipeline sequenziale e logging Weights & Biases | FedeFranchini | 8 | High | Backend | WA-06, WA-08–WA-11 | Backlog |
| WA-13 | Implementare `run_full_pipeline`, orchestrazione I/O e parallelismo Joblib | FedeFranchini | 5 | High | Backend | WA-07, WA-12 | Backlog |
| WA-14 | Integrare validazione schema, error handling e logging applicativo | MarrasFederico | 5 | Medium | Backend | WA-07, WA-12 | Backlog |
| WA-15 | Rendere il generatore dati riproducibile, configurabile e verificato | FedeFranchini | 3 | Medium | Data | WA-04 | Backlog |
| WA-16 | Estendere unit test ed edge case: vuoti, null, schema e input invalidi | MarrasFederico | 5 | High | Testing | WA-08–WA-14 | Backlog |
| WA-17 | Completare acceptance e integration test del flusso end-to-end | FedeFranchini | 3 | High | Testing | WA-13, WA-14 | Backlog |
| WA-18 | Creare benchmark e report su tempo e memoria con dataset di almeno 100k righe | MarrasFederico | 5 | Medium | Testing | WA-11, WA-13, WA-15 | Backlog |
| WA-19 | Ottimizzare i colli di bottiglia dimostrati dal profiling | FedeFranchini | 5 | Medium | Backend | WA-18 | Backlog |
| WA-20 | Configurare documentazione Sphinx e completare docstring/API reference | MarrasFederico | 5 | Medium | Documentation | WA-08–WA-14 | Backlog |
| WA-21 | Completare README: installazione, uso, esempi, output e troubleshooting | FedeFranchini | 3 | Medium | Documentation | WA-13, WA-20 | Backlog |
| WA-22 | Verifica finale: qualità, CI, UML allineato, DoD e preparazione demo | MarrasFederico | 3 | High | Testing | WA-05, WA-16–WA-21 | Backlog |

## Workflow operativo

1. Selezionare una card `Ready` rispettando dipendenze e WIP limit.
2. Spostarla in `In Progress`.
3. Creare una branch `feature/WA-XX-descrizione`,
   `fix/WA-XX-descrizione` o `docs/WA-XX-descrizione`.
4. Usare `WA-XX` nei commit pertinenti e limitare le modifiche allo scope.
5. Eseguire i test applicabili.
6. Aprire una Pull Request con titolo `WA-XX — descrizione` e aggiungerla al
   Project. Non usare `Closes #...`.
7. Spostare la card in `Review / Testing` e richiedere la review dell'altro
   componente.
8. Dopo approvazione, test e merge, spostare la card in `Done`.

## WIP limit e peer review

Ogni componente può avere al massimo un task principale in `In Progress`.
Ogni Pull Request è revisionata dall'altro componente; l'autore risolve i
commenti e non approva autonomamente il proprio lavoro.

## Definition of Done

Una card è `Done` soltanto quando:

- acceptance criteria e dipendenze sono soddisfatti;
- implementazione e documentazione restano nello scope della card;
- test applicabili, lint e CI risultano superati;
- la Pull Request contiene il codice WA ed è collegata al Project;
- la peer review è stata completata e i commenti sono risolti;
- la Pull Request è stata integrata nel branch principale;
- la documentazione interessata è aggiornata e il risultato è riproducibile.
