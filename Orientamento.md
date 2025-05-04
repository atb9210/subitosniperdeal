# Orientamento Progetto SnipeDeal

## Panoramica
SnipeDeal è un'applicazione Python progettata per monitorare i prezzi degli iPhone (ed esteso ad altri prodotti come Xbox) su Subito.it. L'applicazione esegue automaticamente ricerche, filtra gli annunci in base a criteri specifici e invia notifiche via Telegram quando vengono trovati annunci interessanti.

## Struttura del Progetto

```
SnipeDeal/
├── .git/
├── .gitignore
├── README.md
├── requirements.txt
├── database_schema.py       # Schema del database SQL
├── app.py                   # Applicazione Streamlit base
├── enhanced_app.py          # Applicazione Streamlit avanzata
├── scraper_adapter.py       # Adattatore per integrare lo scraper
├── subito_scraper.py        # Modulo principale per lo scraping
├── run.sh                   # Script per avviare l'applicazione
├── requirements-frontend.txt # Dipendenze frontend
├── data/                    # Directory per dati persistenti
│   ├── snipedeal.db         # Database SQLite
│   ├── snipedeal.log        # File di log
│   └── log_backups/         # Backup dei file di log
├── logs/                    # Directory per i file di log
```

## Componenti Principali

### 1. Scraper (subito_scraper.py)
Il cuore dell'applicazione è il file `subito_scraper.py` che contiene la classe `SubitoScraper`. Questa classe gestisce:
- Connessione a Subito.it con gestione degli header e dei proxy
- Estrazione dei dati dagli annunci (prezzo, titolo, dettagli, URL, ecc.)
- Filtro degli annunci in base a criteri come prezzo massimo
- Invio di notifiche via Telegram per gli annunci interessanti
- Salvataggio dei risultati in file di testo e JSON
- Tracciamento degli annunci già visti per evitare duplicati
- Calcolo di statistiche di prezzo (min, max, media, mediana)
- Gestione della cache per gli annunci già visti

### 2. Adattatore Scraper (scraper_adapter.py)
Un componente che fa da ponte tra lo scraper e il frontend:
- Integra lo scraper con il database SQL
- Gestisce l'esecuzione periodica delle ricerche
- Aggiorna automaticamente le statistiche
- Mantiene i job in background per ogni campagna attiva
- Fornisce funzionalità di fallback in caso di errori
- Normalizza i dati tra diversi formati per garantire compatibilità

### 3. Database (database_schema.py)
Schema del database SQLAlchemy con tre tabelle principali:
- **Keyword**: Gestisce le campagne di ricerca con i loro parametri
- **Risultato**: Memorizza gli annunci trovati e il loro stato
- **Statistiche**: Contiene le statistiche aggregate per ogni campagna

### 4. Frontend Streamlit (enhanced_app.py)
Un'interfaccia utente moderna che permette di:
- Gestire le campagne di ricerca (aggiungere, modificare, eliminare)
- Visualizzare statistiche con grafici e metriche
- Monitorare i risultati delle ricerche
- Configurare le notifiche Telegram
- Accedere ai log di sistema per diagnostica

## Funzionalità Principali

1. **Ricerca Automatica**: Cerca annunci su Subito.it usando parole chiave configurabili.
2. **Filtro per Prezzo**: Filtra gli annunci in base a un prezzo massimo configurabile.
3. **Statistiche di Mercato**: Calcola statistiche come prezzo medio e mediano.
4. **Notifiche Telegram Affidabili**: Invia notifiche con verifica della consegna e tentativi ripetuti in caso di fallimento.
5. **Esclusione Automatica**: Esclude annunci senza prezzo o venduti.
6. **Calcolo Sell Through Rate**: Traccia quanti annunci vengono venduti.
7. **Persistenza Dati Avanzata**: Sistema avanzato di deduplicazione per annunci già visti, basato su identificatori univoci.
8. **Dashboard Grafica**: Visualizza statistiche e metriche con grafici interattivi.
9. **Gestione Campagne**: Permette di avere multiple campagne di ricerca attive contemporaneamente.
10. **Sistema di Limiti Configurabili**: Limiti di prezzo e numero di pagine configurabili per ogni campagna.
11. **Sistema Cache Intelligente**: Memorizza annunci già visti per campagna con possibilità di reset selettivo.
12. **Interfaccia Admin**: Gestione completa delle campagne con opzioni per creare, modificare, eliminare e attivare/disattivare.
13. **Simulazione**: Modalità di simulazione avanzata per test e sviluppo senza dipendere da Subito.it.
14. **Geolocalizzazione**: Estrazione intelligente delle informazioni geografiche dagli annunci.
15. **Sistema di Logging**: Registra tutte le operazioni con livelli di dettaglio configurabili.
16. **Cache Intelligente per Campagna**: Traccia gli annunci visti separatamente per ogni campagna per massimizzare i risultati.
17. **GUI per Gestione Campagne**: Interfaccia web per aggiungere, modificare, eliminare e gestire le campagne.
18. **Configurazione Telegram**: Interfaccia per impostare le credenziali di notifica con test diretto di funzionamento.
19. **Simulazione Avanzata**: Generazione di dati realistici quando lo scraping reale non è possibile.
20. **Controllo Multipagina**: Supporto per impostare il numero di pagine da analizzare per ogni ricerca.
21. **Diagnostica Cronjob**: Monitora l'esecuzione dei job in background con log dettagliati per campagna.
22. **Visualizzazione Risultati**: Pagina dedicata alla visualizzazione di tutti i risultati con filtri e link cliccabili.
23. **Diagnostica Avanzata**: Sistema di debug con tracciamento completo delle API calls e mascheramento dati sensibili.
24. **Adattamento Intelligente**: Sistema di fallback che utilizza simulazioni in caso di errori con lo scraper originale.
25. **Normalizzazione Dati**: Sistema di mappatura che converte i dati tra formati diversi per garantire compatibilità.
26. **Validazione Risultati**: Verifica la pertinenza dei risultati con la keyword cercata ed evita risultati errati.
27. **Simulazione Intelligente**: Genera risultati simulati che corrispondono alle caratteristiche specifiche del prodotto cercato.
28. **Gestione Configurazione**: Salva e ripristina correttamente le configurazioni tra le diverse ricerche.
29. **Resilienza agli Errori**: Continua a funzionare anche quando lo scraper reale non può essere inizializzato.
30. **URL Autentici**: In modalità simulazione, estrae URL di annunci reali direttamente dal sito Subito.it.
31. **Supporto Multi-Prodotto**: Classificazione intelligente per diverse categorie di prodotti (videogiochi, telefonia, ecc.).
32. **Link Garantiti**: Tutti i link dei risultati portano sempre ad annunci specifici e reali, anche in modalità simulazione.
33. **Estrazione Live**: Mini-scraper integrato che ottiene dati reali del mercato attuale per keyword specifiche.
34. **Estrazione Geografica**: Estrazione precisa della città dall'annuncio, ottimizzata per una visualizzazione pulita.
35. **Statistiche Avanzate**: Calcolo automatico di statistiche di prezzo (min, max, media, mediana) per ogni ricerca.
36. **Modifica Campagne**: Interfaccia per modificare i parametri delle campagne dopo la creazione.
37. **Eliminazione Controllata**: Eliminazione di campagne con processo a due fasi per prevenire cancellazioni accidentali.
38. **Indicatori Visivi**: Visualizzazione migliorata dello stato dei parametri come il limite di prezzo attivo/inattivo.
39. **Processo di Eliminazione Intuitivo**: Sistema di conferma che mostra prima la casella di conferma, poi il numero di risultati interessati, e infine il pulsante di eliminazione.
40. **Feedback Contestuali**: Messaggi informativi che guidano l'utente durante operazioni critiche come l'eliminazione di campagne.
41. **Reset Cache Selettivo**: Possibilità di cancellare la cache degli annunci visti per una singola campagna, permettendo di riottenere tutti i risultati senza interferire con altre ricerche.
42. **Persistenza Avanzata**: Salvatagio degli annunci già visti in database con associazione alla campagna specifica, mantenendo comunque un sistema di fallback su file per retrocompatibilità.
43. **Gestione Limite Pagine**: Sistema migliorato che assicura il rispetto del parametro di limite pagine in tutte le modalità di ricerca (reale e simulata).
44. **Simulazione Proporzionale**: Generazione intelligente di risultati simulati in proporzione al numero di pagine configurato per una migliore rappresentazione dei risultati attesi.
45. **Trasparenza Parametri**: Logging dettagliato dei parametri effettivamente utilizzati durante le ricerche, con validazione esplicita della configurazione.
46. **Diagnostica dei Limiti**: Verifiche automatiche che assicurano il corretto funzionamento dei limiti configurati sia in fase di ricerca che durante la simulazione.
47. **Lista Annunci Visti**: Pagina dedicata alla visualizzazione e gestione della cache di annunci già visti per ogni campagna.
48. **Filtro Prezzi Robusto**: Sistema avanzato di filtro prezzi che converte esplicitamente i valori in formato numerico, scarta risultati non validi o fuori range e documenta dettagliatamente il processo nei log.
49. **Ordinamento Personalizzabile**: Possibilità di ordinare i risultati per data (più vecchi/recenti) e prezzo (crescente/decrescente) con ordinamento predefinito configurabile.

## Tecnologie Utilizzate

- **Python 3.9+**: Linguaggio di programmazione principale
- **Streamlit**: Framework per l'interfaccia utente web
- **SQLAlchemy**: ORM per la gestione del database
- **SQLite**: Database leggero per la persistenza dei dati
- **FastAPI**: Framework per API web (configurato nei requirements ma non implementato)
- **Requests/BeautifulSoup**: Per lo scraping di Subito.it
- **Python-Telegram-Bot**: Per inviare notifiche via Telegram
- **Schedule**: Per la pianificazione delle esecuzioni periodiche
- **Python-dotenv**: Per la gestione delle variabili d'ambiente
- **Matplotlib/Pandas**: Per la visualizzazione dei dati e statistiche

## Come Funziona

1. L'applicazione si avvia eseguendo `run.sh`
2. Streamlit lancia l'interfaccia web (accessibile a http://localhost:8501)
3. Si possono configurare e avviare le campagne di ricerca
4. L'adattatore utilizza lo scraper per cercare annunci in base ai parametri configurati
5. I risultati vengono normalizzati per garantire compatibilità tra diversi formati di dati
6. I risultati normalizzati vengono salvati nel database SQLite
7. Le statistiche vengono calcolate automaticamente
8. Le notifiche vengono inviate via Telegram per tutti i nuovi risultati trovati
9. I log vengono registrati per monitorare l'attività e gli errori
10. Le esecuzioni in background vengono monitorate attraverso la pagina "Log Cronjob"
11. I risultati completi sono visualizzabili tramite la pagina "Risultati" con filtri avanzati
12. Ogni fase del processo è monitorata con log dettagliati per facilitare la diagnosi di problemi

## Configurazione

Per configurare l'applicazione:
1. Esegui lo script `run.sh` per avviare l'interfaccia
2. Vai alla sezione "Impostazioni" per configurare Telegram:
   - Inserisci il token del bot e il chat ID
3. Nella sezione "Gestione Campagne" puoi aggiungere nuove campagne con:
   - Parola chiave di ricerca
   - Prezzo massimo
   - Applicazione del limite di prezzo (attivabile/disattivabile)
   - Numero di pagine da scansionare
   - Intervallo in minuti tra le scansioni
4. Puoi modificare o eliminare campagne esistenti dalla stessa sezione:
   - Usa il pannello "Modifica parametri" per aggiornare i valori
   - Usa il pulsante "Elimina campagna" per rimuovere una campagna e tutti i suoi dati

## Come Estendere

Per estendere l'applicazione con nuove funzionalità:
1. **Aggiungere nuovi filtri**: Modifica la classe `SubitoScraper` per aggiungere nuovi criteri di filtro
2. **Supportare altri siti**: Crea nuove classi scraper ispirate a `SubitoScraper` per altri siti di annunci
3. **Interfaccia avanzata**: Estendi l'interfaccia Streamlit con componenti più sofisticati
4. **Analytics avanzati**: Implementa algoritmi di ML per previsione dei prezzi o detection di offerte eccezionali
5. **API integrazione**: Aggiungi API per integrare l'applicazione con altri servizi o app mobile 