#!/bin/bash

# Colori per i messaggi
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Directory di base
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
LOGS_DIR="$SCRIPT_DIR/logs"
PID_FILE="$LOGS_DIR/snipe.pid"
LOG_FILE="$LOGS_DIR/snipe.log"
OUTPUT_FILE="$LOGS_DIR/output.log"

# Crea la directory logs se non esiste
mkdir -p "$LOGS_DIR"

# Funzione per avviare il programma
start() {
    if [ -f "$PID_FILE" ]; then
        echo -e "${RED}❌ Il programma è già in esecuzione${NC}"
        exit 1
    fi
    
    echo -e "${GREEN}🚀 Avvio del programma in background (intervallo: 1 minuto)...${NC}"
    cd "$SCRIPT_DIR"
    nohup python3 scraper_test.py > "$OUTPUT_FILE" 2>&1 &
    echo -e "${GREEN}✅ Programma avviato${NC}"
    echo -e "${GREEN}📝 Controlla i log con: tail -f $LOG_FILE${NC}"
}

# Funzione per fermare il programma
stop() {
    if [ ! -f "$PID_FILE" ]; then
        echo -e "${RED}❌ Il programma non è in esecuzione${NC}"
        exit 1
    fi
    
    PID=$(cat "$PID_FILE")
    echo -e "${GREEN}🛑 Arresto del programma (PID: $PID)...${NC}"
    kill $PID
    rm "$PID_FILE"
    echo -e "${GREEN}✅ Programma arrestato${NC}"
}

# Funzione per controllare lo stato
status() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p $PID > /dev/null; then
            echo -e "${GREEN}✅ Il programma è in esecuzione (PID: $PID)${NC}"
            echo -e "${GREEN}📝 Log file: $LOG_FILE${NC}"
        else
            echo -e "${RED}❌ Il programma non è in esecuzione (PID non valido)${NC}"
            rm "$PID_FILE"
        fi
    else
        echo -e "${RED}❌ Il programma non è in esecuzione${NC}"
    fi
}

# Funzione per vedere gli ultimi log
logs() {
    if [ -f "$LOG_FILE" ]; then
        tail -f "$LOG_FILE"
    else
        echo -e "${RED}❌ File di log non trovato${NC}"
    fi
}

# Gestione dei comandi
case "$1" in
    start)
        start
        ;;
    stop)
        stop
        ;;
    status)
        status
        ;;
    logs)
        logs
        ;;
    *)
        echo "Uso: $0 {start|stop|status|logs}"
        exit 1
        ;;
esac

exit 0 