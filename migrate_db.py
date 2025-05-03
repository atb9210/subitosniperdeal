#!/usr/bin/env python3
# Script per aggiornare la struttura del database

import os
import sys
import sqlite3
import logging

# Impostazione del logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def migrate_database():
    """Aggiunge nuove colonne al database se necessario"""
    db_path = "data/snipedeal.db"
    
    # Verifica che il database esista
    if not os.path.exists(db_path):
        logger.error(f"Database non trovato: {db_path}")
        sys.exit(1)
    
    logger.info(f"Avvio migrazione del database: {db_path}")
    
    try:
        # Connessione al database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Verifica se la colonna id_annuncio esiste già nella tabella risultati
        cursor.execute("PRAGMA table_info(risultati)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if "id_annuncio" not in columns:
            logger.info("Aggiunta della colonna id_annuncio alla tabella risultati...")
            cursor.execute("ALTER TABLE risultati ADD COLUMN id_annuncio TEXT")
            logger.info("Colonna id_annuncio aggiunta con successo")
        else:
            logger.info("La colonna id_annuncio esiste già nella tabella risultati")
            
        # Creazione di un indice sulla colonna id_annuncio per velocizzare le ricerche
        logger.info("Creazione indice sulla colonna id_annuncio...")
        try:
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_risultati_id_annuncio ON risultati(id_annuncio)")
            logger.info("Indice creato con successo")
        except sqlite3.OperationalError as e:
            logger.warning(f"Errore nella creazione dell'indice: {e}")
        
        # Commit delle modifiche
        conn.commit()
        logger.info("Migrazione completata con successo")
        
    except Exception as e:
        logger.error(f"Errore durante la migrazione: {e}")
        sys.exit(1)
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    migrate_database() 