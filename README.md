# SnipeDeal

Un'applicazione Python per monitorare i prezzi degli iPhone su Subito.it.

## Funzionalità

- Ricerca automatica di annunci su Subito.it
- Filtro per prezzo massimo
- Calcolo delle statistiche di mercato
- Notifiche Telegram per gli annunci più interessanti
- Esclusione automatica degli annunci senza prezzo
- Calcolo del Sell Through Rate

## Requisiti

- Python 3.9+
- requests
- beautifulsoup4
- python-telegram-bot

## Installazione

1. Clona il repository:
```bash
git clone https://github.com/tuousername/SnipeDeal.git
cd SnipeDeal
```

2. Installa le dipendenze:
```bash
pip install -r requirements.txt
```

3. Configura le variabili d'ambiente:
- Crea un file `.env` con le tue configurazioni
- Aggiungi il token del bot Telegram e l'ID della chat

## Utilizzo

Esegui lo script:
```bash
python scraper_test.py
```

I risultati verranno salvati in `results.txt` e inviati via Telegram.

## Configurazione

Modifica il file `config.py` per personalizzare:
- Parole chiave di ricerca
- Prezzo massimo
- Numero di pagine da analizzare
- Formato dei log

## Licenza

MIT 