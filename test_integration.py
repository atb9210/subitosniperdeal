#!/usr/bin/env python3
"""
Script per testare l'integrazione tra scraper_adapter e subito_scraper
"""

import os
import sys
import logging
import json
from datetime import datetime

# Configura il logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("TestIntegration")

# Importa l'adapter e lo scraper
from scraper_adapter import scraper_adapter
from subito_scraper import SubitoScraper

def test_scraper_standalone():
    """Testa il nuovo scraper in modo indipendente"""
    logger.info("Test del nuovo scraper in modo indipendente...")
    
    # Crea un'istanza del nuovo scraper
    scraper = SubitoScraper(
        keywords=["ps5"],
        prezzo_max=500,
        apply_price_limit=False,
        max_pages=1,
        debug=True
    )
    
    # Test del metodo search
    logger.info("Test del metodo 'search'...")
    results = scraper.search("ps5")
    logger.info(f"search ha restituito {len(results)} risultati")
    
    # Test del metodo search_ads
    logger.info("Test del metodo 'search_ads'...")
    results_ads = scraper.search_ads("ps5")
    logger.info(f"search_ads ha restituito {len(results_ads)} risultati")
    
    # Test del metodo run
    logger.info("Test del metodo 'run'...")
    response = scraper.run()
    logger.info(f"run ha restituito un oggetto di tipo {type(response)}")
    if isinstance(response, dict):
        logger.info(f"run ha restituito {len(response.get('results', []))} risultati")
        logger.info(f"Statistiche: {json.dumps(response.get('stats', {}), indent=2)}")
    
    # Salva alcuni risultati per debug
    if results:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        debug_file = f"debug_standalone_{timestamp}.json"
        with open(debug_file, "w") as f:
            json.dump(results[:5], f, indent=2)
        logger.info(f"Salvati 5 risultati in {debug_file}")
    
    # Controlla che i risultati abbiano le chiavi corrette
    if results:
        logger.info(f"Esempio di risultato: {json.dumps(results[0], indent=2)}")
    
    return results, results_ads, response

def test_adapter_integration():
    """Testa l'integrazione tra adapter e scraper"""
    logger.info("Test dell'integrazione adapter-scraper...")
    
    # Verifica che l'adapter stia usando il nuovo scraper
    if hasattr(scraper_adapter.scraper, "__class__"):
        logger.info(f"L'adapter sta usando: {scraper_adapter.scraper.__class__.__name__}")
    else:
        logger.info("Adapter non ha ancora uno scraper inizializzato")
    
    # Verifica USING_NEW_SCRAPER
    from scraper_adapter import USING_NEW_SCRAPER
    logger.info(f"USING_NEW_SCRAPER = {USING_NEW_SCRAPER}")
    
    # Inizializziamo una ricerca con l'adapter
    # Nota: abbiamo bisogno di un ID di keyword valido dal database, 
    # quindi questo potrebbe fallire in questa fase di test
    try:
        # Simuliamo un record di keyword
        class DummyKeyword:
            def __init__(self):
                self.id = 1
                self.keyword = "ps5"
                self.limite_prezzo = 500
                self.applica_limite_prezzo = False
                self.limite_pagine = 1
                self.attivo = True
        
        # Proviamo a inizializzare lo scraper direttamente
        scraper_adapter._initialize_scraper(DummyKeyword())
        
        # Verifichiamo cosa è stato inizializzato
        if scraper_adapter.scraper:
            logger.info(f"Scraper inizializzato: {scraper_adapter.scraper.__class__.__name__}")
            # Proviamo a eseguire una ricerca diretta con lo scraper dell'adapter
            if hasattr(scraper_adapter.scraper, "search_ads"):
                results = scraper_adapter.scraper.search_ads("ps5")
                logger.info(f"Ricerca diretta con search_ads ha restituito {len(results)} risultati")
                
                if results:
                    logger.info(f"Esempio di risultato: {json.dumps(results[0], indent=2)}")
        else:
            logger.warning("Scraper non inizializzato")
    except Exception as e:
        logger.error(f"Errore durante l'inizializzazione del test adapter: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
    
    return None

if __name__ == "__main__":
    logger.info("Inizio dei test di integrazione...")
    
    # Test del nuovo scraper
    standalone_results, standalone_ads, standalone_response = test_scraper_standalone()
    
    # Test dell'integrazione con l'adapter
    adapter_results = test_adapter_integration()
    
    logger.info("Test di integrazione completati") 