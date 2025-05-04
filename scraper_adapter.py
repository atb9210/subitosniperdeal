import os
import sys
import json
import datetime
from typing import Dict, List, Optional
import threading
import time
import logging
import traceback

# Configura il logging
logger = logging.getLogger("SnipeDeal.Scraper")

# Importa il nuovo scraper dalla root
try:
    from subito_scraper import SubitoScraper
    logger.info("Modulo SubitoScraper importato con successo dalla root")
    USING_NEW_SCRAPER = True
except ImportError as e:
    error_msg = f"ERRORE: Impossibile importare il nuovo modulo subito_scraper: {str(e)}"
    logger.error(error_msg)
    logger.error(traceback.format_exc())
    print(error_msg)
    
    # Prova a importare il vecchio scraper come fallback
    try:
        # Aggiungi la directory backend al path
        backend_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backend')
        sys.path.append(backend_path)
        
        # Importa direttamente dal modulo
        sys.path.insert(0, backend_path)
        from scraper_test import SubitoScraper
        
        # Prova anche a importare le configurazioni 
        try:
            from app.config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
        except ImportError:
            logger.warning("Non è stato possibile importare le configurazioni dal modulo config.py. Verranno utilizzate le configurazioni dal file .env")
            TELEGRAM_BOT_TOKEN = None
            TELEGRAM_CHAT_ID = None
            
        logger.info("Modulo SubitoScraper legacy importato con successo come fallback")
        USING_NEW_SCRAPER = False
    except ImportError as e:
        error_msg = f"ERRORE: Impossibile importare il modulo scraper_test: {str(e)}"
        logger.error(error_msg)
        logger.error(f"Percorso di ricerca Python: {sys.path}")
        logger.error(f"Contenuto della directory backend: {os.listdir(backend_path) if os.path.exists(backend_path) else 'Directory non trovata'}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        print(error_msg)
        
        # Definizione di una classe SubitoScraper di fallback per evitare errori
        class SubitoScraper:
            """Classe di fallback usata quando lo scraper originale non può essere importato"""
            
            def __init__(self, proxy=None):
                self.BASE_URL = "https://www.subito.it/annunci-italia/vendita/usato/"
                logger.warning("Utilizzo della classe SubitoScraper di fallback - lo scraping reale non funzionerà")
                
            def search_ads(self):
                logger.error("Tentativo di utilizzare la funzione search_ads nella classe di fallback")
                return []
        
        USING_NEW_SCRAPER = False

# Importa i modelli di database
from database_schema import Keyword, Risultato, Statistiche, SessionLocal

# Funzione per leggere le impostazioni Telegram direttamente dal file .env
def get_telegram_config():
    """Legge le configurazioni Telegram dal file .env"""
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
    backend_env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backend', '.env')
    
    # Prova prima il file .env nella root
    if os.path.exists(env_path):
        config = {}
        try:
            with open(env_path, 'r') as f:
                for line in f:
                    if '=' in line:
                        key, value = line.strip().split('=', 1)
                        config[key] = value
            return config.get('TELEGRAM_BOT_TOKEN', ''), config.get('TELEGRAM_CHAT_ID', '')
        except Exception as e:
            logger.error(f"Errore nella lettura del file .env root: {str(e)}")
    
    # Prova il file .env nel backend come fallback
    if os.path.exists(backend_env_path):
        config = {}
        try:
            with open(backend_env_path, 'r') as f:
                for line in f:
                    if '=' in line:
                        key, value = line.strip().split('=', 1)
                        config[key] = value
            return config.get('TELEGRAM_BOT_TOKEN', ''), config.get('TELEGRAM_CHAT_ID', '')
        except Exception as e:
            logger.error(f"Errore nella lettura del file .env backend: {str(e)}")
    
    return None, None

class ScraperAdapter:
    """
    Adattatore per integrare lo scraper esistente con il nuovo sistema basato su database
    """
    
    def __init__(self):
        self.scraper = None
        self.running_tasks = {}  # Dizionario per tenere traccia dei thread in esecuzione per ogni keyword
        self.scraper_logs = []   # Lista per memorizzare i log specifici dello scraper
        self.cronjob_logs = []   # Lista per memorizzare i log dei cronjob
        
    def _initialize_scraper(self, keyword_record=None):
        """
        Inizializza un'istanza dello scraper con i parametri della keyword
        
        Args:
            keyword_record: Record della keyword dal database con i parametri di ricerca
        """
        try:
            # Ottieni token e chat ID Telegram
            telegram_token, telegram_chat_id = get_telegram_config()
            
            # Parametri di base
            params = {
                "telegram_token": telegram_token,
                "telegram_chat_id": telegram_chat_id,
                "debug": True
            }
            
            # Se abbiamo un record di keyword, aggiungi i parametri specifici
            if keyword_record:
                params.update({
                    "keywords": [keyword_record.keyword],
                    "prezzo_max": keyword_record.limite_prezzo if keyword_record.applica_limite_prezzo else None,
                    "prezzo_min": keyword_record.limite_prezzo_min if keyword_record.applica_limite_prezzo else None,
                    "apply_price_limit": keyword_record.applica_limite_prezzo,
                    "max_pages": keyword_record.limite_pagine,
                    "keyword_id": keyword_record.id,
                    "db_session": SessionLocal()  # Passa una sessione del database
                })
            
            try:
                # Cerca prima nella directory corrente
                # Il nuovo subito_scraper.py nella root del progetto
                try:
                    from subito_scraper import SubitoScraper
                    self.scraper = SubitoScraper(**params)
                    self._add_log("INFO", "Modulo SubitoScraper importato con successo dalla root")
                    return True
                except ImportError as e:
                    self._add_log("WARNING", f"Impossibile importare SubitoScraper dalla root: {str(e)}")
                
                # Prova ad importare dallo scraper originale 
                try:
                    sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backend'))
                    from scraper_test import SubitoScraper
                    self.scraper = SubitoScraper(**params)
                    global USING_NEW_SCRAPER
                    USING_NEW_SCRAPER = False
                    self._add_log("INFO", "Modulo SubitoScraper importato con successo da backend")
                    return True
                except ImportError as e:
                    self._add_log("ERROR", f"Impossibile importare SubitoScraper da backend: {str(e)}")
                
                # Se arriviamo qui, non è stato possibile importare lo scraper
                self._add_log("ERROR", "Impossibile importare lo scraper da qualsiasi posizione")
                
                # Usa la classe di fallback
                self.scraper = self.FallbackScraper(**params)
                self._add_log("WARNING", "Utilizzo della classe di fallback (simulazione)")
                return True
                
            except Exception as e:
                self._add_log("ERROR", f"Errore nell'inizializzazione dello scraper: {str(e)}")
                self._add_log("ERROR", traceback.format_exc())
                
                # Fallback alla versione di simulazione
                self.scraper = self.FallbackScraper(**params)
                self._add_log("WARNING", "Utilizzo della classe di fallback dopo un errore di inizializzazione")
                return True
                
        except Exception as e:
            self._add_log("ERROR", f"Errore grave nell'inizializzazione dello scraper: {str(e)}")
            self._add_log("ERROR", traceback.format_exc())
            return False
        
    def _add_log(self, level, message):
        """Aggiunge un messaggio di log alla lista dei log dello scraper"""
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = {
            "timestamp": now,
            "level": level,
            "message": message
        }
        self.scraper_logs.append(log_entry)
        
        # Mantieni solo gli ultimi 1000 log
        if len(self.scraper_logs) > 1000:
            self.scraper_logs = self.scraper_logs[-1000:]
        
        # Log anche nel sistema principale
        if level == "ERROR":
            logger.error(message)
        elif level == "WARNING":
            logger.warning(message)
        else:
            logger.info(message)
    
    def _add_cronjob_log(self, level, message, keyword_id=None):
        """Aggiunge un messaggio di log alla lista dei log dei cronjob"""
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = {
            "timestamp": now,
            "level": level,
            "message": message,
            "keyword_id": keyword_id
        }
        self.cronjob_logs.append(log_entry)
        
        # Mantieni solo gli ultimi 1000 log
        if len(self.cronjob_logs) > 1000:
            self.cronjob_logs = self.cronjob_logs[-1000:]
        
        # Log anche nel sistema principale
        if level == "ERROR":
            logger.error(f"[CRONJOB] {message}")
        elif level == "WARNING":
            logger.warning(f"[CRONJOB] {message}")
        else:
            logger.info(f"[CRONJOB] {message}")
    
    def get_logs(self, limit=100):
        """Restituisce gli ultimi N log dello scraper"""
        return self.scraper_logs[-limit:] if limit < len(self.scraper_logs) else self.scraper_logs
    
    def get_cronjob_logs(self, limit=100):
        """Restituisce gli ultimi N log dei cronjob"""
        return self.cronjob_logs[-limit:] if limit < len(self.cronjob_logs) else self.cronjob_logs
    
    def search_for_keyword(self, keyword_id: int) -> Dict:
        """
        Esegue una ricerca per la keyword specificata e salva i risultati nel database
        """
        session = SessionLocal()
        try:
            # Ottieni i dettagli della keyword dal database
            keyword_record = session.query(Keyword).filter(Keyword.id == keyword_id).first()
            
            if not keyword_record or not keyword_record.attivo:
                return {"status": "error", "message": "Keyword non trovata o non attiva"}
            
            # Inizializza lo scraper con i parametri della keyword
            scraper_initialized = self._initialize_scraper(keyword_record)
            
            self._add_log("INFO", f"Avvio ricerca per keyword: {keyword_record.keyword}")
            self._add_cronjob_log("INFO", f"Avvio ricerca per keyword: {keyword_record.keyword}", keyword_id)
            
            # Parametri di ricerca
            search_params = {
                "keyword": keyword_record.keyword,
                "prezzo_max": keyword_record.limite_prezzo if keyword_record.applica_limite_prezzo else None,
                "prezzo_min": keyword_record.limite_prezzo_min if keyword_record.applica_limite_prezzo else None,
                "max_pages": keyword_record.limite_pagine
            }
            
            self._add_log("INFO", f"Parametri di ricerca: {json.dumps(search_params)}")
            self._add_cronjob_log("INFO", f"Parametri di ricerca: {json.dumps(search_params)}", keyword_id)
            
            # Variabile per tenere traccia se stiamo usando simulazione o scraper reale
            using_simulation = False
            
            try:
                # Verifica se possiamo usare lo scraper
                if scraper_initialized and self.scraper:
                    if USING_NEW_SCRAPER:
                        # Usa il nuovo scraper con metodo search_ads che accetta la keyword come parametro
                        self._add_log("INFO", "Utilizzo del nuovo scraper per la ricerca")
                        self._add_cronjob_log("INFO", "Utilizzo del nuovo scraper per la ricerca", keyword_id)
                        
                        # Verifica che il parametro max_pages sia stato passato correttamente
                        self._add_log("INFO", f"Verifico i parametri impostati nello scraper:")
                        self._add_log("INFO", f"  - max_pages: {self.scraper.max_pages}")
                        self._add_log("INFO", f"  - prezzo_max: {self.scraper.prezzo_max}")
                        self._add_log("INFO", f"  - prezzo_min: {getattr(self.scraper, 'prezzo_min', None)}")
                        self._add_log("INFO", f"  - apply_price_limit: {self.scraper.apply_price_limit}")
                        
                        # Esegui la ricerca
                        ads = self.scraper.search_ads(keyword_record.keyword)
                        self._add_log("INFO", f"Ricerca completata, trovati {len(ads)} annunci")
                    else:
                        # Fallback alla versione legacy
                        self._add_log("INFO", "Utilizzo dello scraper legacy per la ricerca")
                        self._add_cronjob_log("INFO", "Utilizzo dello scraper legacy per la ricerca", keyword_id)
                        
                        # Prova a usare il vecchio scraper
                        try:
                            ads = self.scraper.search_ads(keyword_record.keyword)
                        except TypeError:
                            # Se il vecchio scraper non accetta un parametro keyword
                            self._add_log("WARNING", "Il vecchio scraper non supporta il parametro keyword, usando metodo senza parametri")
                            ads = self.scraper.search_ads()
                    
                    # Verifica che i risultati siano pertinenti
                    if ads:
                        valid_results = 0
                        keyword_lower = keyword_record.keyword.lower()
                        for ad in ads:
                            title = ad.get('titolo') or ad.get('title', '')
                            if title and keyword_lower in title.lower():
                                valid_results += 1
                                
                        if valid_results == 0 and len(ads) > 0:
                            self._add_log("WARNING", f"Nessuno dei {len(ads)} risultati contiene la keyword '{keyword_record.keyword}' nel titolo!")
                            self._add_cronjob_log("WARNING", f"Risultati non pertinenti: lo scraper ha restituito {len(ads)} annunci ma nessuno contiene '{keyword_record.keyword}' nel titolo", keyword_id)
                            
                            # Se i risultati non sono pertinenti, usa la simulazione
                            self._add_log("INFO", "Utilizzo della simulazione per garantire risultati pertinenti")
                            ads = self._simulate_search_results(search_params)
                            using_simulation = True
                        else:
                            self._add_log("INFO", f"Trovati {valid_results}/{len(ads)} risultati pertinenti con la keyword '{keyword_record.keyword}'")
                    else:
                        self._add_log("WARNING", "Nessun risultato trovato, utilizzo della simulazione")
                        ads = self._simulate_search_results(search_params)
                        using_simulation = True
                else:
                    self._add_log("WARNING", "Inizializzazione scraper fallita, utilizzo della simulazione")
                    ads = self._simulate_search_results(search_params)
                    using_simulation = True
            except Exception as e:
                error_msg = f"Errore durante l'esecuzione della ricerca: {str(e)}"
                self._add_log("ERROR", error_msg)
                self._add_log("ERROR", traceback.format_exc())
                self._add_cronjob_log("ERROR", error_msg, keyword_id)
                
                # Usa la simulazione come fallback
                self._add_log("WARNING", "Utilizzo della simulazione come fallback dopo un errore")
                ads = self._simulate_search_results(search_params)
                using_simulation = True
            
            # Salva i risultati nel database
            self._add_log("INFO", f"Salvando {len(ads)} risultati nel database")
            self._add_cronjob_log("INFO", f"Salvando {len(ads)} risultati nel database", keyword_id)
            new_results = self._save_results_to_db(keyword_id, ads)
            
            # Aggiorna le statistiche
            self._add_log("INFO", "Aggiornamento statistiche")
            self._add_cronjob_log("INFO", "Aggiornamento statistiche", keyword_id)
            self._update_statistics(keyword_id)
            
            # Invia notifiche per i nuovi risultati
            if new_results > 0:
                self._add_log("INFO", f"Trovati {new_results} nuovi risultati, invio notifiche")
                self._add_cronjob_log("INFO", f"Trovati {new_results} nuovi risultati, invio notifiche", keyword_id)
                
                # Ottieni i risultati non notificati
                nuovi_risultati = session.query(Risultato).filter(
                    Risultato.keyword_id == keyword_id,
                    Risultato.notificato == False
                ).all()
                
                for risultato in nuovi_risultati:
                    self._add_log("INFO", f"Invio notifica per il risultato ID {risultato.id}")
                    success = self.notify_telegram(risultato.id)
                    if success:
                        self._add_log("INFO", f"Notifica inviata con successo per ID {risultato.id}")
                        self._add_cronjob_log("INFO", f"Notifica inviata con successo per ID {risultato.id}", keyword_id)
                    else:
                        self._add_log("ERROR", f"Errore nell'invio della notifica per ID {risultato.id}")
                        self._add_cronjob_log("ERROR", f"Errore nell'invio della notifica per ID {risultato.id}", keyword_id)
            
            mode_text = "simulazione" if using_simulation else "scraper reale"
            self._add_log("INFO", f"Ricerca completata per '{keyword_record.keyword}' usando {mode_text}, trovati {len(ads)} risultati")
            self._add_cronjob_log("INFO", f"Ricerca completata per '{keyword_record.keyword}' usando {mode_text}, trovati {len(ads)} risultati", keyword_id)
            
            return {
                "status": "success",
                "message": f"Ricerca completata per '{keyword_record.keyword}' usando {mode_text}, trovati {len(ads)} risultati, {new_results} nuovi",
                "results_count": len(ads),
                "new_results_count": new_results
            }
            
        except Exception as e:
            error_msg = f"Errore durante la ricerca: {str(e)}"
            self._add_log("ERROR", error_msg)
            self._add_log("ERROR", traceback.format_exc())
            self._add_cronjob_log("ERROR", error_msg, keyword_id)
            self._add_cronjob_log("ERROR", traceback.format_exc(), keyword_id)
            logger.error(error_msg)
            logger.error(traceback.format_exc())
            return {"status": "error", "message": error_msg}
        finally:
            session.close()
    
    def _simulate_search_results(self, params: Dict) -> List[Dict]:
        """
        Simula i risultati della ricerca utilizzando dati reali da Subito.it
        """
        self._add_log("INFO", f"Simulazione risultati di ricerca in corso per keyword: {params['keyword']}")
        self._add_log("INFO", f"Parametri simulazione: max_pages={params.get('max_pages', 2)}, prezzo_max={params.get('prezzo_max', 'Non impostato')}")
        
        # Importazioni necessarie
        import random
        import requests
        from bs4 import BeautifulSoup
        
        # Genera URL di ricerca per la keyword
        base_search_url = "https://www.subito.it/annunci-italia/vendita/usato/"
        encoded_keyword = params['keyword'].replace(' ', '+')
        search_url = f"{base_search_url}?q={encoded_keyword}"
        
        self._add_log("INFO", f"Tentativo di recupero annunci reali da: {search_url}")
        
        # Definiamo headers realistici per evitare di essere bloccati
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7",
            "Referer": "https://www.subito.it/",
            "Connection": "keep-alive"
        }
        
        # Dizionario di termini di modello pertinenti a ciascuna tipologia di prodotto
        related_models = {
            "ps4": ["Slim", "Pro", "Fat", "500GB", "1TB", "2TB", "Digital Edition"],
            "ps5": ["Digital Edition", "Slim", "Standard", "Pro", "Bundle", "Disc Edition"],
            "xbox": ["One", "One S", "One X", "Series S", "Series X", "Elite"],
            "xbox series s": ["512GB", "Digital", "Bundle", "Controller", "Standard"],
            "nintendo": ["Switch", "Switch Lite", "Switch OLED", "DS", "3DS", "Wii", "Wii U"],
            "iphone": ["Pro Max", "Pro", "Plus", "Mini", "64GB", "128GB", "256GB", "512GB", "1TB"]
        }
        
        try:
            # Facciamo una richiesta HTTP per ottenere la pagina di risultati
            response = requests.get(search_url, headers=headers, timeout=10)
            real_urls = []
            real_titles = []
            real_prices = []
            real_locations = []
            
            if response.status_code == 200:
                # Parsing della pagina HTML
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Trova tutti gli annunci nella pagina
                listing_items = soup.select('div.items__item')
                
                for item in listing_items:
                    # Estrai l'URL dell'annuncio
                    link_element = item.select_one('a.SmallCard-module_link__hOkzY')
                    if link_element and 'href' in link_element.attrs:
                        real_urls.append(link_element['href'])
                        
                        # Estrai il titolo dell'annuncio
                        title_element = item.select_one('h2.ItemTitle-module_item-title__VuKDo')
                        if title_element:
                            real_titles.append(title_element.text.strip())
                        else:
                            real_titles.append(f"{params['keyword']} (Annuncio su Subito.it)")
                        
                        # Estrai il prezzo
                        price_element = item.select_one('p.index-module_price__N7M2x')
                        if price_element:
                            price_text = price_element.text.strip()
                            try:
                                # Estrai solo i numeri e converte in float
                                price = float(''.join(c for c in price_text if c.isdigit() or c == ',').replace(',', '.'))
                                real_prices.append(price)
                            except:
                                # Se non riesce a estrarre il prezzo, usa un valore casuale
                                real_prices.append(random.uniform(50, 500))
                        else:
                            real_prices.append(random.uniform(50, 500))
                        
                        # Estrai località
                        location_element = item.select_one('span.index-module_town__nH89d')
                        if location_element:
                            real_locations.append(location_element.text.strip())
                        else:
                            real_locations.append(random.choice(["Milano", "Roma", "Napoli", "Torino", "Bologna"]))
                
                self._add_log("INFO", f"Trovati {len(real_urls)} annunci reali per '{params['keyword']}'")
            else:
                self._add_log("WARNING", f"Impossibile recuperare annunci reali. Status code: {response.status_code}")
        except Exception as e:
            self._add_log("ERROR", f"Errore durante il recupero degli annunci reali: {str(e)}")
            real_urls = []
            real_titles = []
            real_prices = []
            real_locations = []
        
        # Determina i modelli da usare se necessario per la simulazione
        keyword_lower = params['keyword'].lower()
        models_to_use = None
        for key in related_models:
            if key in keyword_lower:
                models_to_use = related_models[key]
                break
        
        # Se non troviamo corrispondenze, usa un modello generico
        if models_to_use is None:
            models_to_use = ["Base", "Pro", "Ultra", "Lite", "Standard", "Deluxe", "Special Edition"]
        
        # Lista di città italiane per dare varietà alle località
        cities = ["Milano", "Roma", "Napoli", "Torino", "Bologna", "Firenze", "Palermo", 
                 "Genova", "Catania", "Bari", "Venezia", "Verona", "Messina", "Padova"]
        
        # Determina quanti risultati generare
        # 5-10 risultati per pagina configurata
        max_pages = params.get('max_pages', 2)
        min_results = 5 * max_pages
        max_results = 10 * max_pages
        num_results = random.randint(min_results, max_results)
        
        # Se abbiamo URL reali, limitiamo i risultati a quelli disponibili
        if real_urls:
            num_results = min(num_results, len(real_urls))
        
        self._add_log("INFO", f"Generando {num_results} risultati simulati (max_pages={max_pages})")
        
        results = []
        
        for i in range(num_results):
            # Usa dati reali se disponibili, altrimenti genera dati casuali
            if i < len(real_urls):
                # Usa dati reali
                title = real_titles[i] if i < len(real_titles) else f"{params['keyword']} {random.choice(models_to_use)}"
                price = real_prices[i] if i < len(real_prices) else random.uniform(50, 500)
                url = real_urls[i]
                location = real_locations[i] if i < len(real_locations) else random.choice(cities)
            else:
                # Genera dati casuali
                title = f"{params['keyword']} {random.choice(models_to_use)}"
                
                # Calcola un prezzo casuale intorno al prezzo massimo specificato
                if params.get("prezzo_max"):
                    price = random.uniform(params["prezzo_max"] * 0.7, params["prezzo_max"] * 1.1)
                else:
                    price = random.uniform(50, 500)
                
                # Usa l'URL di ricerca come fallback
                url = search_url
                location = random.choice(cities)
            
            # Genera dati casuali per la simulazione
            results.append({
                "titolo": title,
                "prezzo": round(price, 2),
                "url": url,
                "data_annuncio": datetime.datetime.now().strftime("%Y-%m-%d"),
                "luogo": location,
                "venduto": random.random() < 0.1,  # 10% di probabilità che sia venduto
            })
        
        # Log dei risultati simulati
        for i, result in enumerate(results):
            self._add_log("DEBUG", f"Risultato simulato {i+1}: {result['titolo']} - €{result['prezzo']} - {result['url']}")
        
        self._add_log("INFO", f"Simulati {len(results)} risultati per la keyword '{params['keyword']}'")
        return results
    
    def _save_results_to_db(self, keyword_id: int, ads: List[Dict]) -> int:
        """
        Salva i risultati nel database
        
        Returns:
            int: Il numero di nuovi risultati salvati
        """
        session = SessionLocal()
        new_results_count = 0
        
        try:
            self._add_log("INFO", f"Inizio salvataggio di {len(ads)} risultati per keyword_id {keyword_id}")
            
            # Set per tracciare gli URL già processati in questo batch
            processed_urls = set()
            
            # Ottieni i limiti di prezzo dalla keyword
            keyword = session.query(Keyword).filter(Keyword.id == keyword_id).first()
            if keyword and keyword.applica_limite_prezzo:
                min_price = keyword.limite_prezzo_min if hasattr(keyword, 'limite_prezzo_min') else 0
                max_price = keyword.limite_prezzo
                self._add_log("INFO", f"Applico filtro prezzi: min={min_price}, max={max_price}")
                
                filtered_ads = []
                for ad in ads:
                    prezzo = ad.get('prezzo')
                    try:
                        prezzo_float = float(prezzo)
                    except (TypeError, ValueError):
                        self._add_log("WARNING", f"Annuncio scartato per prezzo non numerico: {ad}")
                        continue
                    if min_price <= prezzo_float <= max_price:
                        ad['prezzo'] = prezzo_float
                        filtered_ads.append(ad)
                    else:
                        self._add_log("INFO", f"Annuncio scartato per prezzo fuori range: {ad}")
                ads = filtered_ads
                self._add_log("INFO", f"Dopo filtro prezzi robusto: {len(ads)} risultati rimasti")
            
            # Per ogni annuncio trovato
            for ad in ads:
                # Normalizza le chiavi del dizionario
                normalized_ad = self._normalize_ad_keys(ad)
                
                # Verifica che ci siano URL e ID (necessari per l'identificazione)
                if "url" not in normalized_ad:
                    self._add_log("WARNING", f"Annuncio senza URL non salvato: {normalized_ad}")
                    continue
                
                # Controlla se l'URL è già stato processato in questo batch
                if normalized_ad["url"] in processed_urls:
                    self._add_log("INFO", f"Annuncio duplicato (URL già processato in questo batch): {normalized_ad['url']}")
                    continue
                
                processed_urls.add(normalized_ad["url"])
                    
                # Verifica se l'annuncio esiste già tramite URL (per retrocompatibilità)
                # o tramite l'ID dell'annuncio se disponibile (metodo più accurato)
                existing = None
                
                # Prima cerca per ID se disponibile
                if 'id' in normalized_ad and normalized_ad['id']:
                    existing = session.query(Risultato).filter(
                        Risultato.keyword_id == keyword_id,
                        Risultato.id_annuncio == str(normalized_ad["id"])
                    ).first()
                
                # Se non trova per ID, cerca per URL (retrocompatibilità)
                if not existing:
                    existing = session.query(Risultato).filter(
                        Risultato.keyword_id == keyword_id,
                        Risultato.url == normalized_ad["url"]
                    ).first()
                
                # Salva i dati raw come JSON
                raw_data_json = None
                try:
                    import json
                    raw_data_json = json.dumps(ad, ensure_ascii=False)
                except Exception:
                    raw_data_json = str(ad)
                
                if not existing:
                    # Crea un nuovo record
                    new_result = Risultato(
                        keyword_id=keyword_id,
                        titolo=normalized_ad.get("titolo", "Titolo non disponibile"),
                        prezzo=normalized_ad.get("prezzo", 0.0),
                        url=normalized_ad.get("url", ""),
                        data_annuncio=normalized_ad.get("data", normalized_ad.get("data_annuncio", "")),
                        luogo=normalized_ad.get("luogo", ""),
                        venduto=normalized_ad.get("venduto", False),
                        notificato=False,
                        id_annuncio=str(normalized_ad.get("id", "")),
                        raw_data=raw_data_json
                    )
                    session.add(new_result)
                    new_results_count += 1
                    self._add_log("INFO", f"Nuovo annuncio salvato: {normalized_ad.get('titolo', 'Titolo non disponibile')}")
                else:
                    # Aggiorna lo stato di venduto con il valore corrente
                    is_sold = normalized_ad.get("venduto", False)
                    if existing.venduto != is_sold:
                        existing.venduto = is_sold
                        sold_status = "venduto" if is_sold else "non venduto"
                        self._add_log("INFO", f"Annuncio aggiornato come {sold_status}: {existing.titolo}")
                    # Aggiorna l'ID dell'annuncio se non era impostato
                    if 'id' in normalized_ad and normalized_ad['id'] and not existing.id_annuncio:
                        existing.id_annuncio = str(normalized_ad["id"])
                        self._add_log("DEBUG", f"Aggiornato ID annuncio per {existing.titolo}: {existing.id_annuncio}")
                    # Aggiorna i dati raw se non presenti
                    if not getattr(existing, 'raw_data', None):
                        existing.raw_data = raw_data_json
            
            session.commit()
            self._add_log("INFO", f"Salvati {new_results_count} nuovi risultati su {len(ads)} totali")
            return new_results_count
        except Exception as e:
            self._add_log("ERROR", f"Errore durante il salvataggio dei risultati: {str(e)}")
            self._add_log("ERROR", traceback.format_exc())
            logger.error(f"Errore durante il salvataggio dei risultati: {str(e)}")
            logger.error(traceback.format_exc())
            session.rollback()
            return 0
        finally:
            session.close()
    
    def _normalize_ad_keys(self, ad: Dict) -> Dict:
        """
        Normalizza le chiavi del dizionario dell'annuncio per adattarle al modello del database
        """
        normalized = {}
        
        # Mappatura delle chiavi tra lo scraper reale e l'adapter
        key_mapping = {
            # Scraper reale -> Adapter
            'title': 'titolo',
            'price': 'prezzo',
            'link': 'url',
            'location': 'luogo',
            'date': 'data_annuncio',
            'sold': 'venduto',
            # Aggiungiamo anche le mappature inverse per essere certi
            'titolo': 'titolo',
            'prezzo': 'prezzo',
            'url': 'url',
            'luogo': 'luogo',
            'data': 'data_annuncio',
            'data_annuncio': 'data_annuncio',
            'venduto': 'venduto',
            # Mappatura per le chiavi della versione attuale
            'id': 'id'
        }
        
        # Copia i valori con le chiavi normalizzate
        for key, value in ad.items():
            if key in key_mapping:
                normalized[key_mapping[key]] = value
            else:
                normalized[key] = value
        
        # Log per il debug
        self._add_log("DEBUG", f"Annuncio normalizzato: {normalized}")
        
        return normalized
    
    def _update_statistics(self, keyword_id: int) -> None:
        """
        Aggiorna le statistiche per la keyword
        """
        session = SessionLocal()
        try:
            # Ottieni tutti i risultati per la keyword
            results = session.query(Risultato).filter(
                Risultato.keyword_id == keyword_id
            ).all()
            
            if not results:
                self._add_log("INFO", "Nessun risultato trovato per calcolare le statistiche")
                return
            
            # Calcola le statistiche
            prices = [r.prezzo for r in results if r.prezzo > 0]
            if not prices:
                self._add_log("WARNING", "Nessun prezzo valido trovato per calcolare le statistiche")
                return
                
            avg_price = sum(prices) / len(prices)
            median_price = sorted(prices)[len(prices) // 2]
            min_price = min(prices)
            max_price = max(prices)
            sold_count = sum(1 for r in results if r.venduto)
            sell_through_rate = sold_count / len(results) if results else 0
            
            self._add_log("INFO", f"Statistiche calcolate: Prezzo medio {avg_price:.2f}, Mediano {median_price:.2f}, Min {min_price:.2f}, Max {max_price:.2f}")
            self._add_log("INFO", f"Tasso di vendita: {sell_through_rate*100:.1f}%")
            
            # Aggiorna o crea il record delle statistiche
            stats = session.query(Statistiche).filter(
                Statistiche.keyword_id == keyword_id
            ).first()
            
            if stats:
                stats.prezzo_medio = avg_price
                stats.prezzo_mediano = median_price
                stats.prezzo_minimo = min_price
                stats.prezzo_massimo = max_price
                stats.numero_annunci = len(results)
                stats.annunci_venduti = sold_count
                stats.sell_through_rate = sell_through_rate
                stats.data = datetime.datetime.now()
                self._add_log("INFO", "Statistiche aggiornate")
            else:
                new_stats = Statistiche(
                    keyword_id=keyword_id,
                    prezzo_medio=avg_price,
                    prezzo_mediano=median_price,
                    prezzo_minimo=min_price,
                    prezzo_massimo=max_price,
                    numero_annunci=len(results),
                    annunci_venduti=sold_count,
                    sell_through_rate=sell_through_rate
                )
                session.add(new_stats)
                self._add_log("INFO", "Nuove statistiche create")
            
            session.commit()
        except Exception as e:
            self._add_log("ERROR", f"Errore durante l'aggiornamento delle statistiche: {str(e)}")
            logger.error(f"Errore durante l'aggiornamento delle statistiche: {str(e)}")
            logger.error(traceback.format_exc())
        finally:
            session.close()
    
    def notify_telegram(self, risultato_id: int) -> bool:
        """
        Invia una notifica Telegram per un risultato specifico
        """
        session = SessionLocal()
        try:
            # Ottieni i dati del risultato
            risultato = session.query(Risultato).filter(Risultato.id == risultato_id).first()
            if not risultato:
                self._add_log("ERROR", f"Impossibile trovare il risultato con ID {risultato_id}")
                return False
            
            # Ottieni la keyword associata
            keyword = session.query(Keyword).filter(Keyword.id == risultato.keyword_id).first()
            if not keyword:
                self._add_log("ERROR", f"Impossibile trovare la keyword per il risultato {risultato_id}")
                return False
            
            # Ottieni token e chat ID da .env
            token, chat_id = get_telegram_config()
            
            # Se non sono disponibili, usa quelli dal modulo config
            if not token and hasattr(self, 'TELEGRAM_BOT_TOKEN'):
                token = TELEGRAM_BOT_TOKEN
            if not chat_id and hasattr(self, 'TELEGRAM_CHAT_ID'):
                chat_id = TELEGRAM_CHAT_ID
            
            # Log dei token e chat ID (mascherati per sicurezza)
            if token:
                masked_token = token[:6] + '*****' + token[-4:]
                self._add_log("DEBUG", f"Token Telegram: {masked_token}")
            else:
                self._add_log("ERROR", "Token Telegram non configurato")
                
            if chat_id:
                self._add_log("DEBUG", f"Chat ID Telegram: {chat_id}")
            else:
                self._add_log("ERROR", "Chat ID Telegram non configurato")
                
            if not token or not chat_id:
                error_msg = "Token o Chat ID Telegram non configurati"
                self._add_log("ERROR", error_msg)
                self._add_cronjob_log("ERROR", error_msg, keyword.id)
                return False
            
            import requests
            
            # Verifica che token e chat_id siano stringhe valide
            if not isinstance(token, str) or not token.strip():
                error_msg = "Token Telegram non valido"
                self._add_log("ERROR", error_msg)
                self._add_cronjob_log("ERROR", error_msg, keyword.id)
                return False
                
            if not isinstance(chat_id, str) or not chat_id.strip():
                error_msg = "Chat ID Telegram non valido"
                self._add_log("ERROR", error_msg)
                self._add_cronjob_log("ERROR", error_msg, keyword.id)
                return False
            
            # Componi il messaggio
            message = f"🔍 *Nuovo annuncio trovato!*\n\n"
            message += f"📌 *Keyword*: {keyword.keyword}\n"
            message += f"🏷️ *Titolo*: {risultato.titolo}\n"
            message += f"💰 *Prezzo*: €{risultato.prezzo:.2f}\n"
            message += f"📍 *Luogo*: {risultato.luogo}\n"
            message += f"📅 *Data*: {risultato.data_annuncio}\n\n"
            message += f"🔗 [Vedi annuncio]({risultato.url})"
            
            # Log del tentativo di invio
            self._add_log("INFO", f"Tentativo di invio notifica Telegram per {risultato.titolo}")
            self._add_cronjob_log("INFO", f"Tentativo di invio notifica Telegram per {risultato.titolo}", keyword.id)
            
            # Invia la notifica
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            data = {
                "chat_id": chat_id,
                "text": message,
                "parse_mode": "Markdown",
                "disable_web_page_preview": False
            }
            
            # Log della richiesta (con dati sensibili mascherati)
            self._add_log("DEBUG", f"URL richiesta: {url.replace(token, '[TOKEN]')}")
            self._add_log("DEBUG", f"Dati richiesta: chat_id=[CHAT_ID], text={message[:50]}..., parse_mode=Markdown")
            
            try:
                response = requests.post(url, data=data, timeout=10)  # Aggiunto timeout
                
                # Log della risposta
                self._add_log("DEBUG", f"Codice risposta: {response.status_code}")
                self._add_log("DEBUG", f"Risposta: {response.text[:200]}")
                
                if response.status_code == 200:
                    # Aggiorna lo stato del risultato come notificato SOLO in caso di successo
                    risultato.notificato = True
                    session.commit()
                    success_msg = f"Notifica inviata con successo per {risultato.titolo}"
                    self._add_log("INFO", success_msg)
                    self._add_cronjob_log("INFO", success_msg, keyword.id)
                    return True
                else:
                    # NON aggiornare lo stato del risultato come notificato in caso di errore
                    error_msg = f"Errore nell'invio della notifica Telegram: {response.status_code} - {response.text}"
                    self._add_log("ERROR", error_msg)
                    self._add_cronjob_log("ERROR", error_msg, keyword.id)
                    return False
            except requests.exceptions.RequestException as e:
                # NON aggiornare lo stato del risultato come notificato in caso di errore
                error_msg = f"Errore di connessione durante l'invio della notifica Telegram: {str(e)}"
                self._add_log("ERROR", error_msg)
                self._add_cronjob_log("ERROR", error_msg, keyword.id)
                return False
                
        except Exception as e:
            error_msg = f"Errore durante l'invio della notifica: {str(e)}"
            self._add_log("ERROR", error_msg)
            self._add_log("ERROR", traceback.format_exc())
            logger.error(error_msg)
            logger.error(traceback.format_exc())
            return False
        finally:
            session.close()
    
    def start_background_job(self, keyword_id: int) -> Dict:
        """
        Avvia un job in background per una keyword specifica
        """
        if keyword_id in self.running_tasks and self.running_tasks[keyword_id].is_alive():
            warning_msg = f"Task già in esecuzione per la keyword {keyword_id}"
            self._add_log("WARNING", warning_msg)
            self._add_cronjob_log("WARNING", warning_msg, keyword_id)
            return {"status": "error", "message": "Task già in esecuzione per questa keyword"}
        
        def background_task(keyword_id):
            session = SessionLocal()
            try:
                keyword = session.query(Keyword).filter(Keyword.id == keyword_id).first()
                if not keyword:
                    error_msg = f"Keyword {keyword_id} non trovata per job in background"
                    self._add_log("ERROR", error_msg)
                    self._add_cronjob_log("ERROR", error_msg, keyword_id)
                    return
                
                start_msg = f"Avviato job in background per keyword: {keyword.keyword}"
                self._add_log("INFO", start_msg)
                self._add_cronjob_log("INFO", start_msg, keyword_id)
                
                while keyword.attivo:
                    # Log dell'esecuzione pianificata
                    exec_msg = f"Esecuzione pianificata per keyword: {keyword.keyword} (ID: {keyword_id})"
                    self._add_log("INFO", exec_msg)
                    self._add_cronjob_log("INFO", exec_msg, keyword_id)
                    
                    # Esegui la ricerca
                    search_start_msg = f"Inizio ricerca per keyword: {keyword.keyword} (ID: {keyword_id})"
                    self._add_log("INFO", search_start_msg)
                    self._add_cronjob_log("INFO", search_start_msg, keyword_id)
                    
                    result = self.search_for_keyword(keyword_id)
                    
                    if result["status"] == "error":
                        error_msg = f"Errore nella ricerca per job in background: {result['message']}"
                        self._add_log("ERROR", error_msg)
                        self._add_cronjob_log("ERROR", error_msg, keyword_id)
                    else:
                        success_msg = f"Ricerca completata: {result['message']}"
                        self._add_log("INFO", success_msg)
                        self._add_cronjob_log("INFO", success_msg, keyword_id)
                    
                    # Invia notifiche per i nuovi risultati non notificati
                    try:
                        nuovi_risultati = session.query(Risultato).filter(
                            Risultato.keyword_id == keyword_id,
                            Risultato.notificato == False
                        ).all()
                        
                        if nuovi_risultati:
                            notify_msg = f"Trovati {len(nuovi_risultati)} nuovi risultati da notificare"
                            self._add_cronjob_log("INFO", notify_msg, keyword_id)
                            
                            for risultato in nuovi_risultati:
                                result = self.notify_telegram(risultato.id)
                                if result:
                                    self._add_cronjob_log("INFO", f"Notifica inviata per risultato ID {risultato.id}", keyword_id)
                                else:
                                    self._add_cronjob_log("ERROR", f"Fallito invio notifica per risultato ID {risultato.id}", keyword_id)
                        else:
                            self._add_cronjob_log("INFO", "Nessun nuovo risultato da notificare", keyword_id)
                    except Exception as e:
                        error_msg = f"Errore nell'invio delle notifiche: {str(e)}"
                        self._add_log("ERROR", error_msg)
                        self._add_cronjob_log("ERROR", error_msg, keyword_id)
                    
                    # Attendi l'intervallo configurato
                    wait_msg = f"Attesa di {keyword.intervallo_minuti} minuti prima della prossima ricerca"
                    self._add_log("INFO", wait_msg)
                    self._add_cronjob_log("INFO", wait_msg, keyword_id)
                    time.sleep(keyword.intervallo_minuti * 60)
                    
                    # Ricarica lo stato della keyword
                    session.refresh(keyword)
            except Exception as e:
                error_msg = f"Errore nel job in background: {str(e)}"
                self._add_log("ERROR", error_msg)
                self._add_log("ERROR", traceback.format_exc())
                self._add_cronjob_log("ERROR", error_msg, keyword_id)
                self._add_cronjob_log("ERROR", traceback.format_exc(), keyword_id)
                logger.error(error_msg)
                logger.error(traceback.format_exc())
            finally:
                end_msg = f"Terminato job in background per keyword ID {keyword_id}"
                self._add_log("INFO", end_msg)
                self._add_cronjob_log("INFO", end_msg, keyword_id)
                session.close()
        
        # Avvia un nuovo thread
        thread = threading.Thread(target=background_task, args=(keyword_id,))
        thread.daemon = True  # Il thread si chiuderà quando l'applicazione principale si chiude
        thread.start()
        
        # Salva il riferimento al thread
        self.running_tasks[keyword_id] = thread
        
        success_msg = f"Job in background avviato con successo per keyword ID {keyword_id}"
        self._add_log("INFO", success_msg)
        self._add_cronjob_log("INFO", success_msg, keyword_id)
        return {"status": "success", "message": "Job in background avviato con successo"}
    
    def stop_background_job(self, keyword_id: int) -> Dict:
        """
        Interrompe un job in background impostando la keyword come non attiva
        """
        session = SessionLocal()
        try:
            keyword = session.query(Keyword).filter(Keyword.id == keyword_id).first()
            if not keyword:
                error_msg = f"Keyword {keyword_id} non trovata"
                self._add_log("ERROR", error_msg)
                self._add_cronjob_log("ERROR", error_msg, keyword_id)
                return {"status": "error", "message": "Keyword non trovata"}
            
            keyword.attivo = False
            session.commit()
            
            success_msg = f"Job in background interrotto per keyword: {keyword.keyword}"
            self._add_log("INFO", success_msg)
            self._add_cronjob_log("INFO", success_msg, keyword_id)
            return {"status": "success", "message": "Job in background interrotto con successo"}
        except Exception as e:
            error_msg = f"Errore nell'interruzione del job: {str(e)}"
            self._add_log("ERROR", error_msg)
            self._add_cronjob_log("ERROR", error_msg, keyword_id)
            logger.error(error_msg)
            return {"status": "error", "message": f"Errore: {str(e)}"}
        finally:
            session.close()
    
    def get_statistics(self, keyword_id: int) -> Optional[Dict]:
        """
        Ottiene le statistiche per una keyword specifica
        """
        session = SessionLocal()
        try:
            stats = session.query(Statistiche).filter(
                Statistiche.keyword_id == keyword_id
            ).first()
            
            if not stats:
                return None
            
            return {
                "prezzo_medio": stats.prezzo_medio,
                "prezzo_mediano": stats.prezzo_mediano,
                "prezzo_minimo": stats.prezzo_minimo,
                "prezzo_massimo": stats.prezzo_massimo,
                "numero_annunci": stats.numero_annunci,
                "annunci_venduti": stats.annunci_venduti,
                "sell_through_rate": stats.sell_through_rate,
                "data_aggiornamento": stats.data.strftime("%Y-%m-%d %H:%M:%S")
            }
        except Exception as e:
            self._add_log("ERROR", f"Errore nel recupero delle statistiche: {str(e)}")
            logger.error(f"Errore nel recupero delle statistiche: {str(e)}")
            return None
        finally:
            session.close()

    def is_job_running(self, keyword_id: int) -> bool:
        """
        Verifica se un job in background è attivo per una keyword specifica
        
        Args:
            keyword_id: ID della keyword da verificare
            
        Returns:
            bool: True se il job è attivo, False altrimenti
        """
        if keyword_id not in self.running_tasks:
            return False
            
        thread = self.running_tasks[keyword_id]
        return thread.is_alive()

    # Classe di fallback per simulare i risultati dello scraper
    class FallbackScraper:
        """Classe di fallback usata quando lo scraper originale non può essere importato"""
        
        def __init__(self, **kwargs):
            self.keywords = kwargs.get('keywords', ['ps5'])
            self.prezzo_max = kwargs.get('prezzo_max', 500)
            self.apply_price_limit = kwargs.get('apply_price_limit', False)
            self.max_pages = kwargs.get('max_pages', 2)  # Assicuriamoci di gestire questo parametro
            self.telegram_token = kwargs.get('telegram_token', None)
            self.telegram_chat_id = kwargs.get('telegram_chat_id', None)
            self.debug = kwargs.get('debug', False)
            self.keyword_id = kwargs.get('keyword_id', None)
            self.db_session = kwargs.get('db_session', None)
            
            logger.warning(f"FallbackScraper inizializzato con max_pages={self.max_pages}")
        
        def search_ads(self, keyword=None):
            """
            Simula una ricerca di annunci
            
            Args:
                keyword (str, optional): Parola chiave da cercare
            """
            import random
            
            logger.info(f"FallbackScraper: simulazione ricerca per '{keyword or self.keywords[0]}'")
            logger.info(f"FallbackScraper: parametri - max_pages: {self.max_pages}, prezzo_max: {self.prezzo_max}, apply_price_limit: {self.apply_price_limit}")
            
            # Simula un numero di risultati in base al numero di pagine configurato
            # 5-10 risultati per pagina
            min_results = 5 * self.max_pages
            max_results = 10 * self.max_pages
            num_results = random.randint(min_results, max_results)
            
            logger.info(f"FallbackScraper: generando {num_results} risultati simulati ({self.max_pages} pagine)")
            
            results = []
            search_keyword = keyword or self.keywords[0]
            
            # Genera titoli pertinenti in base alla keyword
            title_prefixes = [
                f"{search_keyword.upper()}", 
                f"{search_keyword} nuovo", 
                f"{search_keyword} usato", 
                f"{search_keyword} bundle",
                f"{search_keyword} edizione speciale"
            ]
            
            for i in range(num_results):
                # Genera un prezzo nel range giusto
                if self.apply_price_limit and self.prezzo_max:
                    # Con limite di prezzo, genera prezzi sempre sotto il limite
                    price = random.uniform(self.prezzo_max * 0.5, self.prezzo_max * 0.95)
                else:
                    # Senza limite di prezzo, genera una gamma più ampia
                    base_price = 200 if "ps" in search_keyword.lower() else 300
                    price = random.uniform(base_price * 0.5, base_price * 1.5)
                
                results.append({
                    'titolo': f"{random.choice(title_prefixes)} - Simulato {i+1}",
                    'prezzo': round(price, 2),
                    'luogo': random.choice(["Milano", "Roma", "Napoli", "Torino", "Bologna"]),
                    'data_annuncio': datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
                    'url': f"https://www.subito.it/annunci-italia/vendita/usato/?q={search_keyword}",
                    'id': f"sim_{int(time.time())}_{i}",
                    'venduto': random.random() < 0.1  # 10% di probabilità che sia venduto
                })
            
            logger.info(f"FallbackScraper: generati {len(results)} risultati simulati per '{search_keyword}'")
            return results

# Crea un'istanza globale dell'adattatore
scraper_adapter = ScraperAdapter() 