#!/bin/bash

# Verifica che Python sia installato
if ! command -v python3 &> /dev/null
then
    echo "Python 3 non è installato. Installa Python 3 prima di eseguire questa applicazione."
    exit 1
fi

# Verifica che le dipendenze siano installate
if [ ! -d "venv" ]; then
    echo "Creazione dell'ambiente virtuale..."
    python3 -m venv venv
    
    echo "Attivazione dell'ambiente virtuale..."
    source venv/bin/activate
    
    echo "Installazione delle dipendenze..."
    pip install -r requirements.txt
    pip install -r requirements-frontend.txt
else
    echo "Attivazione dell'ambiente virtuale..."
    source venv/bin/activate
fi

# Verifica se il database è inizializzato
if [ ! -f "data/snipedeal.db" ]; then
    echo "Inizializzazione del database..."
    python database_schema.py
fi

# Avvia l'applicazione Streamlit
echo "Avvio dell'applicazione SnipeDeal..."
streamlit run enhanced_app.py 