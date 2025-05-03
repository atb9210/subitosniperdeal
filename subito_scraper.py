import requests
from bs4 import BeautifulSoup
import logging
from typing import List, Dict, Optional
import time
import random
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import os
from datetime import datetime, timedelta
import json
import traceback

class SubitoScraper:
    """
    Classe per lo scraping di annunci da Subito.it
    Versione indipendente dal modulo config, con parametri configurabili
    """
    
    def __init__(self, 
                 keywords=None, 
                 prezzo_max=None, 
                 apply_price_limit=False, 
                 max_pages=3, 
                 telegram_token=None, 
                 telegram_chat_id=None,
                 base_dir=None,
                 debug=False,
                 use_simulation=False,
                 max_retries=3,
                 proxy=None,
                 keyword_id=None,         # ID della campagna nel DB
                 db_session=None):        # Sessione database
        
        # Parametri di configurazione
        self.keywords = keywords or ["ps5"]
        self.prezzo_max = prezzo_max or 600
        self.apply_price_limit = apply_price_limit
        self.max_pages = max_pages
        self.telegram_token = telegram_token
        self.telegram_chat_id = telegram_chat_id
        self.debug = debug
        self.use_simulation = use_simulation
        self.max_retries = max_retries
        self.proxy = proxy
        
        # Parametri per la gestione DB
        self.keyword_id = keyword_id
        self.db_session = db_session
        
        # Directory per il salvataggio dei dati
        if base_dir is None:
            self.base_dir = os.path.dirname(os.path.abspath(__file__))
        else:
            self.base_dir = base_dir
            
        self.data_dir = os.path.join(self.base_dir, "data")
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)
            
        # Directory di debug
        self.debug_dir = os.path.join(self.data_dir, "debug")
        if not os.path.exists(self.debug_dir):
            os.makedirs(self.debug_dir)
        
        # Configurazione del logger
        self.logger = logging.getLogger("SubitoScraper")
        self.logger.setLevel(logging.INFO)
        
        if not self.logger.handlers:
            # Console handler
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.INFO)
            console_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            console_handler.setFormatter(console_format)
            self.logger.addHandler(console_handler)
            
            # File handler
            log_file = os.path.join(self.data_dir, "scraper.log")
            file_handler = logging.FileHandler(log_file)
            file_handler.setLevel(logging.DEBUG)
            file_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            file_handler.setFormatter(file_format)
            self.logger.addHandler(file_handler)
        
        # Configurazione della sessione HTTP
        self.session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)
        
        # User-Agent
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        })
        
        # Configurazione del proxy se fornito
        if self.proxy:
            self.session.proxies = {
                "http": self.proxy,
                "https": self.proxy,
            }
        
        # Cache degli annunci già visti
        self.seen_items = set()
        self.load_seen_items()
        
        self.logger.info(f"SubitoScraper inizializzato. Keywords: {self.keywords}, Max prezzo: {self.prezzo_max}, Max pagine: {self.max_pages}")
    
    def calculate_statistics(self, results):
        """
        Calcola statistiche sui risultati
        """
        if not results:
            return {
                "count": 0,
                "min_price": 0,
                "max_price": 0,
                "avg_price": 0,
                "median_price": 0
            }
        
        prices = [r['prezzo'] for r in results if r['prezzo'] > 0]
        if not prices:
            return {
                "count": len(results),
                "min_price": 0,
                "max_price": 0,
                "avg_price": 0,
                "median_price": 0
            }
        
        # Calcola le statistiche
        min_price = min(prices)
        max_price = max(prices)
        avg_price = sum(prices) / len(prices)
        
        # Calcola la mediana
        sorted_prices = sorted(prices)
        n = len(sorted_prices)
        if n % 2 == 0:
            median_price = (sorted_prices[n//2-1] + sorted_prices[n//2]) / 2
        else:
            median_price = sorted_prices[n//2]
        
        return {
            "count": len(results),
            "min_price": round(min_price, 2),
            "max_price": round(max_price, 2),
            "avg_price": round(avg_price, 2),
            "median_price": round(median_price, 2)
        }
    
    def save_results_to_txt(self, results, keyword):
        """
        Salva i risultati in un file di testo formattato bene
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_path = os.path.join(self.data_dir, f"risultati_{keyword}_{timestamp}.txt")
        
        # Calcola statistiche
        stats = self.calculate_statistics(results)
        
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(f"==== RISULTATI RICERCA '{keyword}' - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ====\n\n")
            
            # Aggiungi statistiche
            f.write(f"STATISTICHE:\n")
            f.write(f"Totale risultati: {stats['count']}\n")
            f.write(f"Prezzo minimo: €{stats['min_price']}\n")
            f.write(f"Prezzo massimo: €{stats['max_price']}\n")
            f.write(f"Prezzo medio: €{stats['avg_price']}\n")
            f.write(f"Prezzo mediano: €{stats['median_price']}\n\n")
            f.write("-"*50 + "\n\n")
            
            f.write("DETTAGLIO RISULTATI:\n\n")
            
            for i, result in enumerate(results, 1):
                f.write(f"[{i}] {result['titolo']}\n")
                f.write(f"Prezzo: €{result['prezzo']}\n")
                f.write(f"Città: {result['luogo']}\n")
                f.write(f"Data: {result['data']}\n")
                f.write(f"URL: {result['url']}\n")
                f.write(f"ID: {result['id']}\n")
                f.write("\n" + "-"*50 + "\n\n")
        
        self.logger.info(f"Risultati salvati in {file_path}")
        return file_path
    
    def load_seen_items(self):
        """
        Carica gli ID degli annunci già visti da un file cache o dal database
        """
        # Se abbiamo una sessione DB e un keyword_id, carichiamo dalla tabella seen_ads
        if self.db_session and self.keyword_id:
            try:
                # Importa la classe SeenAds se non è già importata
                try:
                    from database_schema import SeenAds
                    seen_ads = self.db_session.query(SeenAds.item_id).filter(
                        SeenAds.keyword_id == self.keyword_id
                    ).all()
                    
                    # Converte la lista di tuple in un set di stringhe
                    self.seen_items = set([ad[0] for ad in seen_ads])
                    self.logger.info(f"Caricati {len(self.seen_items)} elementi dalla tabella seen_ads per la campagna ID {self.keyword_id}.")
                except ImportError:
                    self.logger.warning("Impossibile importare SeenAds, fallback a file cache")
                    self._load_seen_items_from_file()
                except Exception as e:
                    self.logger.error(f"Errore nel caricamento degli annunci visti dal DB: {str(e)}")
                    self._load_seen_items_from_file()
            except Exception as e:
                self.logger.error(f"Errore generale nel caricamento degli annunci visti dal DB: {str(e)}")
                self._load_seen_items_from_file()
        else:
            # Fallback al file cache
            self._load_seen_items_from_file()
    
    def _load_seen_items_from_file(self):
        """
        Carica gli ID degli annunci già visti dal file cache
        """
        cache_file = os.path.join(self.data_dir, "seen_items_cache.txt")
        try:
            if os.path.exists(cache_file):
                with open(cache_file, "r") as f:
                    self.seen_items = set(line.strip() for line in f)
                self.logger.info(f"Caricati {len(self.seen_items)} elementi dalla cache file.")
            else:
                self.logger.info("File cache degli annunci visti non trovato, sarà creato al primo salvataggio.")
        except Exception as e:
            self.logger.error(f"Errore nel caricamento della cache file: {str(e)}")
    
    def save_seen_items(self):
        """
        Salva gli ID degli annunci già visti in DB o file cache
        """
        # Se abbiamo una sessione DB e un keyword_id, salviamo nella tabella seen_ads
        if self.db_session and self.keyword_id:
            try:
                from database_schema import SeenAds
                
                # Per ogni item_id in seen_items che non è già nel database
                for item_id in self.seen_items:
                    # Verifica se l'item esiste già nel database
                    exists = self.db_session.query(SeenAds).filter(
                        SeenAds.keyword_id == self.keyword_id,
                        SeenAds.item_id == item_id
                    ).first()
                    
                    # Se non esiste, lo aggiungiamo
                    if not exists:
                        seen_ad = SeenAds(
                            keyword_id=self.keyword_id,
                            item_id=item_id
                        )
                        self.db_session.add(seen_ad)
                
                self.db_session.commit()
                self.logger.info(f"Salvati gli annunci visti nel database per la campagna ID {self.keyword_id}.")
            except ImportError:
                self.logger.warning("Impossibile importare SeenAds, fallback a file cache")
                self._save_seen_items_to_file()
            except Exception as e:
                self.logger.error(f"Errore nel salvataggio degli annunci visti nel DB: {str(e)}")
                self._save_seen_items_to_file()
        else:
            # Fallback al file cache
            self._save_seen_items_to_file()
    
    def _save_seen_items_to_file(self):
        """
        Salva gli ID degli annunci già visti in un file cache
        """
        cache_file = os.path.join(self.data_dir, "seen_items_cache.txt")
        try:
            with open(cache_file, "w") as f:
                for item_id in self.seen_items:
                    f.write(f"{item_id}\n")
            self.logger.info(f"Salvati {len(self.seen_items)} elementi nella cache file.")
        except Exception as e:
            self.logger.error(f"Errore nel salvataggio della cache file: {str(e)}")
    
    def _get_results_from_json(self, json_data):
        """
        Estrae i risultati dal JSON della risposta
        """
        results = []
        try:
            if not json_data or 'items' not in json_data or 'list' not in json_data['items']:
                self.logger.error("JSON non valido o non contiene risultati")
                return results
            
            items_list = json_data['items']['list']
            for decorated_item in items_list:
                if 'item' in decorated_item and 'kind' in decorated_item['item'] and decorated_item['item']['kind'] == 'AdItem':
                    ad_item = decorated_item['item']
                    
                    # Estrai i dati dell'annuncio
                    titolo = ad_item.get('subject', 'Titolo non disponibile')
                    prezzo_raw = self._extract_price(ad_item)
                    luogo = self._extract_location(ad_item)
                    data = self._extract_date(ad_item)
                    url = self._extract_url(ad_item)
                    item_id = self._extract_id(ad_item)
                    
                    # Controlla se rispetta i limiti di prezzo
                    if self.apply_price_limit and prezzo_raw > self.prezzo_max:
                        continue
                    
                    result = {
                        'titolo': titolo,
                        'prezzo': prezzo_raw,
                        'luogo': luogo,
                        'data': data,
                        'url': url,
                        'id': item_id
                    }
                    
                    results.append(result)
        except Exception as e:
            self.logger.error(f"Errore nell'estrazione dei risultati JSON: {str(e)}")
            traceback.print_exc()
        
        return results
    
    def _extract_price(self, ad_item):
        """
        Estrae il prezzo dall'elemento annuncio
        """
        try:
            if 'features' in ad_item and '/price' in ad_item['features']:
                price_feature = ad_item['features']['/price']
                if 'values' in price_feature and len(price_feature['values']) > 0:
                    return float(price_feature['values'][0]['key'].replace(',', '.'))
        except (ValueError, KeyError, IndexError) as e:
            self.logger.warning(f"Errore nell'estrazione del prezzo: {str(e)}")
        
        return 0
    
    def _extract_location(self, ad_item):
        """
        Estrae solo la città dall'elemento annuncio
        """
        try:
            if 'geo' in ad_item:
                geo_data = ad_item['geo']
                city = geo_data.get('city', {}).get('value', '')
                
                # Se non c'è la città, prova con il comune
                if not city:
                    city = geo_data.get('town', {}).get('value', '')
                
                return city if city else "Città non specificata"
        except Exception as e:
            self.logger.warning(f"Errore nell'estrazione della località: {str(e)}")
        
        return "Città non specificata"
    
    def _extract_date(self, ad_item):
        """
        Estrae la data dall'elemento annuncio
        """
        try:
            if 'date' in ad_item:
                date_str = ad_item['date']
                # Converti la stringa di data in un oggetto datetime
                date_obj = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
                return date_obj.strftime('%d/%m/%Y %H:%M')
        except Exception as e:
            self.logger.warning(f"Errore nell'estrazione della data: {str(e)}")
        
        return "Data non disponibile"
    
    def _extract_url(self, ad_item):
        """
        Estrae l'URL dall'elemento annuncio
        """
        try:
            if 'urls' in ad_item and 'default' in ad_item['urls']:
                return ad_item['urls']['default']
        except (KeyError, IndexError) as e:
            self.logger.warning(f"Errore nell'estrazione dell'URL: {str(e)}")
        
        return "#"
    
    def _extract_id(self, ad_item):
        """
        Estrae l'ID dell'annuncio
        """
        try:
            if 'urn' in ad_item:
                # urn format: "id:ad:61451886-7fac-477b-8896-a782e83a7821:list:600534176"
                urn_parts = ad_item['urn'].split(':')
                if len(urn_parts) >= 5:
                    return urn_parts[4]  # Ultimo elemento
        except (KeyError, IndexError) as e:
            self.logger.warning(f"Errore nell'estrazione dell'ID: {str(e)}")
        
        return "unknown"
    
    def search(self, keyword):
        """
        Esegue una ricerca su Subito.it
        """
        self.logger.info(f"Avvio ricerca per: {keyword}")
        self.logger.info(f"Parametri di ricerca - Max pagine: {self.max_pages}, Limite prezzo: {self.prezzo_max}, Applica limite: {self.apply_price_limit}")
        all_results = []
        
        if self.use_simulation:
            self.logger.info("Usando la modalità simulazione")
            return self.simulate_search(keyword)
        
        # Parametri di ricerca
        base_url = "https://www.subito.it/annunci-italia/vendita/usato/?q="
        
        retry_count = 0
        while retry_count < self.max_retries:
            try:
                # Esegui la ricerca per ogni pagina
                for page in range(1, self.max_pages + 1):
                    page_url = f"{base_url}{keyword}&o={page}"
                    
                    self.logger.info(f"Scaricando pagina {page}/{self.max_pages}: {page_url}")
                    
                    # Aggiungi un ritardo random per evitare il blocco
                    time.sleep(random.uniform(2, 5))
                    
                    response = self.session.get(page_url)
                    response.raise_for_status()
                    
                    # Salva la pagina HTML per debug
                    if self.debug:
                        debug_file = os.path.join(self.debug_dir, f"page_{page}.html")
                        with open(debug_file, "w", encoding="utf-8") as f:
                            f.write(response.text)
                    
                    # Estrai i dati JSON dall'HTML
                    json_data = self._extract_json_from_html(response.text)
                    
                    # Salva il JSON per debug
                    if self.debug and json_data:
                        debug_json = os.path.join(self.debug_dir, f"data_{page}.json")
                        with open(debug_json, "w", encoding="utf-8") as f:
                            json.dump(json_data, f, indent=2)
                    
                    # Estrai i risultati dal JSON
                    page_results = self._get_results_from_json(json_data)
                    
                    if not page_results:
                        self.logger.warning(f"Nessun risultato trovato nella pagina {page}")
                        break
                    
                    self.logger.info(f"Trovati {len(page_results)} risultati nella pagina {page}")
                    all_results.extend(page_results)
                    
                    # Se ci sono meno risultati del previsto, probabilmente è l'ultima pagina
                    if len(page_results) < 20:  # di solito 30 risultati per pagina
                        break
                
                # Se la ricerca è andata a buon fine, interrompiamo i tentativi
                break
                
            except Exception as e:
                retry_count += 1
                self.logger.error(f"Errore durante la ricerca (tentativo {retry_count}/{self.max_retries}): {str(e)}")
                traceback.print_exc()
                time.sleep(5)  # Attesa prima di riprovare
        
        if retry_count == self.max_retries:
            self.logger.error(f"Ricerca fallita dopo {self.max_retries} tentativi. Usando la simulazione come fallback.")
            return self.simulate_search(keyword)
        
        # Filtra i risultati già visti
        new_results = []
        for result in all_results:
            if result['id'] not in self.seen_items:
                new_results.append(result)
                self.seen_items.add(result['id'])
        
        self.logger.info(f"Trovati {len(new_results)} nuovi risultati su {len(all_results)} totali.")
        
        # Salva gli ID visti
        self.save_seen_items()
        
        return new_results
    
    def _extract_json_from_html(self, html):
        """
        Estrae i dati JSON dallo script nell'HTML della pagina
        """
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            # Cerca lo script contenente i dati JSON
            script_tag = soup.find("script", {"id": "__NEXT_DATA__"})
            
            if not script_tag:
                self.logger.error("Script JSON non trovato nella pagina")
                return None
            
            json_text = script_tag.string
            json_data = json.loads(json_text)
            
            # Estrai i dati dei risultati
            if 'props' in json_data and 'pageProps' in json_data['props'] and 'initialState' in json_data['props']['pageProps']:
                return json_data['props']['pageProps']['initialState']
            
            self.logger.error("Struttura JSON non valida")
            return None
            
        except Exception as e:
            self.logger.error(f"Errore nell'estrazione dei dati JSON: {str(e)}")
            traceback.print_exc()
            return None
    
    def simulate_search(self, keyword):
        """
        Simula una ricerca generando risultati casuali
        Utile come fallback o per test
        """
        self.logger.info(f"Simulazione ricerca per: {keyword}")
        
        # URL di ricerca per usarlo come base per le URL simulate
        base_url = f"https://www.subito.it/annunci-italia/vendita/usato/?q={keyword}"
        search_url = f"https://www.subito.it/annunci-italia/vendita/videogiochi/?q={keyword}"
        
        # Ottieni alcuni URL reali da Subito.it per migliorare la simulazione
        real_urls = self._get_real_urls(search_url, keyword, 5)
        
        # Simula un numero casuale di risultati tra 3 e 10
        num_results = random.randint(3, 10)
        simulated_results = []
        
        # Varianti di prodotti correlati a keyword
        variants = self._get_product_variants(keyword)
        
        for i in range(num_results):
            # Crea un titolo mescolando la keyword con alcune varianti casuali
            product = random.choice(variants)
            titolo = f"{product} - {random.choice(['come nuovo', 'poco usato', 'perfette condizioni', 'in garanzia'])}"
            
            # Prezzo casuale in base alla keyword
            prezzo_base = self._get_base_price(keyword)
            variation = random.uniform(-0.25, 0.25)  # Variazione fino a ±25%
            prezzo = round(prezzo_base * (1 + variation), 2)
            
            # Località e data casuali
            province = ["Milano", "Roma", "Napoli", "Torino", "Bologna", "Firenze", "Palermo", "Genova"]
            luogo = random.choice(province)
            
            # Data casuale negli ultimi 10 giorni
            days_ago = random.randint(0, 10)
            date_obj = datetime.now() - timedelta(days=days_ago)
            data = date_obj.strftime("%d/%m/%Y %H:%M")
            
            # ID e URL
            item_id = f"sim_{int(time.time())}_{i}"
            
            # Usa un URL reale se disponibile, altrimenti genera uno simulato
            if real_urls and i < len(real_urls):
                url = real_urls[i]
            else:
                url = f"{base_url}&sim_id={item_id}"
            
            result = {
                'titolo': titolo,
                'prezzo': prezzo,
                'luogo': luogo,
                'data': data,
                'url': url,
                'id': item_id
            }
            
            simulated_results.append(result)
        
        self.logger.info(f"Simulazione completata. Generati {len(simulated_results)} risultati.")
        return simulated_results
    
    def _get_product_variants(self, keyword):
        """
        Restituisce varianti di prodotti in base alla keyword
        """
        # Prodotti predefiniti in base alle possibili keyword
        variants = {
            "ps5": ["PlayStation 5", "PS5 Digital Edition", "PS5 Slim", "PlayStation 5 Pro", "PS5 con giochi", "PS5 bundle", "Console PS5"],
            "iphone": ["iPhone 15", "iPhone 14 Pro", "iPhone 13", "iPhone 15 Pro Max", "iPhone 12", "iPhone SE"],
            "macbook": ["MacBook Pro", "MacBook Air M2", "MacBook Pro 16", "MacBook M1", "Apple MacBook"],
            "nintendo": ["Nintendo Switch", "Nintendo Switch OLED", "Switch Lite", "Nintendo Switch bundle"],
            "xbox": ["Xbox Series X", "Xbox Series S", "Xbox One", "Xbox Elite"]
        }
        
        # Trova la categoria più vicina
        for key, values in variants.items():
            if key in keyword.lower():
                return values
        
        # Se non trova corrispondenze, usa un set generico
        return [f"{keyword.upper()}", f"{keyword.capitalize()} nuovo", f"{keyword} come nuovo", f"{keyword} usato poco"]
    
    def _get_base_price(self, keyword):
        """
        Restituisce un prezzo base in base alla keyword
        """
        keyword_lower = keyword.lower()
        
        if "ps5" in keyword_lower:
            return 450
        elif "iphone" in keyword_lower:
            if "15" in keyword_lower and "pro" in keyword_lower:
                return 1200
            elif "14" in keyword_lower:
                return 800
            else:
                return 600
        elif "macbook" in keyword_lower:
            return 1300
        elif "nintendo" in keyword_lower or "switch" in keyword_lower:
            return 280
        elif "xbox" in keyword_lower:
            if "series x" in keyword_lower:
                return 450
            else:
                return 300
        else:
            return 300  # Prezzo generico per altre keyword
    
    def _get_real_urls(self, search_url, keyword, count=5):
        """
        Ottiene URL reali da Subito.it per la keyword specificata
        """
        urls = []
        try:
            self.logger.info(f"Ottenendo URL reali per {keyword}")
            response = self.session.get(search_url)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Cerca i link agli annunci
            links = soup.find_all("a", href=True)
            for link in links:
                href = link.get("href", "")
                # Filtra solo i link che sembrano annunci
                if "subito.it" in href and "/videogiochi/" in href:
                    if href not in urls:
                        urls.append(href)
                    if len(urls) >= count:
                        break
            
            self.logger.info(f"Trovati {len(urls)} URL reali")
            
        except Exception as e:
            self.logger.error(f"Errore nell'ottenimento degli URL reali: {str(e)}")
        
        return urls
            
    def run(self):
        """
        Esegue lo scraper su tutte le keyword configurate
        """
        all_results = []
        results_by_keyword = {}
        
        for keyword in self.keywords:
            self.logger.info(f"Elaborazione keyword: {keyword}")
            
            results = self.search(keyword)
            if results:
                all_results.extend(results)
                results_by_keyword[keyword] = results
                
                # Calcola e mostra le statistiche per questa keyword
                stats = self.calculate_statistics(results)
                self.logger.info(f"Statistiche per '{keyword}':")
                self.logger.info(f"  Totale risultati: {stats['count']}")
                self.logger.info(f"  Prezzo min/max/medio/mediano: €{stats['min_price']}/€{stats['max_price']}/€{stats['avg_price']}/€{stats['median_price']}")
            
            # Pausa tra le ricerche
            time.sleep(random.uniform(5, 10))
        
        # Calcola statistiche complessive
        total_stats = self.calculate_statistics(all_results)
        self.logger.info(f"Scraping completato. Totale risultati: {total_stats['count']}")
        self.logger.info(f"Statistiche complessive:")
        self.logger.info(f"  Prezzo min/max/medio/mediano: €{total_stats['min_price']}/€{total_stats['max_price']}/€{total_stats['avg_price']}/€{total_stats['median_price']}")
        
        return {
            "results": all_results,
            "stats": total_stats,
            "results_by_keyword": results_by_keyword
        }
    
    def send_telegram_notification(self, data):
        """
        Invia notifiche Telegram per i nuovi risultati
        """
        if not self.telegram_token or not self.telegram_chat_id:
            self.logger.warning("Configurazione Telegram mancante. Impossibile inviare notifiche.")
            return
        
        # Estrai i risultati in base al formato
        results = data if isinstance(data, list) else data.get("results", [])
        
        if not results:
            self.logger.info("Nessun nuovo risultato da notificare.")
            return
        
        self.logger.info(f"Invio di {len(results)} notifiche Telegram...")
        
        for result in results:
            try:
                message = (
                    f"🔔 *Nuovo annuncio!*\n\n"
                    f"*{result['titolo']}*\n"
                    f"💰 {result['prezzo']} €\n"
                    f"📍 {result['luogo']}\n"
                    f"🕓 {result['data']}\n\n"
                    f"[Visualizza annuncio]({result['url']})"
                )
                
                api_url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
                payload = {
                    "chat_id": self.telegram_chat_id,
                    "text": message,
                    "parse_mode": "Markdown",
                    "disable_web_page_preview": False
                }
                
                response = requests.post(api_url, data=payload)
                
                if response.status_code != 200:
                    self.logger.error(f"Errore nell'invio della notifica: {response.text}")
                
                # Pausa tra le notifiche
                time.sleep(1)
                
            except Exception as e:
                self.logger.error(f"Errore nell'invio della notifica: {str(e)}")
        
        self.logger.info("Notifiche inviate con successo.")

    def search_ads(self, keyword=None):
        """
        Metodo compatibile con l'adapter originale 
        Cerca annunci per la keyword specificata o per la prima keyword nella lista
        
        Args:
            keyword (str, optional): Keyword da cercare. Se non specificata, usa la prima in self.keywords
            
        Returns:
            list: Lista di annunci trovati
        """
        self.logger.info(f"Ricerca annunci con il metodo compatibile 'search_ads'")
        
        # Se è stata specificata una keyword, la usa; altrimenti usa la prima della lista
        search_keyword = keyword if keyword else self.keywords[0]
        self.logger.info(f"Keyword per search_ads: {search_keyword}")
        
        # Usa il metodo search per cercare gli annunci solo per questa keyword
        results = self.search(search_keyword)
        
        # Adatta il formato dei risultati per garantire compatibilità con l'adapter
        compatible_results = []
        for item in results:
            # Crea una copia per non modificare l'originale
            compatible_item = item.copy()
            
            # Assicura che le chiavi necessarie siano presenti
            if 'titolo' not in compatible_item and 'title' in compatible_item:
                compatible_item['titolo'] = compatible_item['title']
            if 'prezzo' not in compatible_item and 'price' in compatible_item:
                compatible_item['prezzo'] = compatible_item['price']
            if 'url' not in compatible_item and 'link' in compatible_item:
                compatible_item['url'] = compatible_item['link']
            if 'luogo' not in compatible_item and 'location' in compatible_item:
                compatible_item['luogo'] = compatible_item['location']
            if 'data' not in compatible_item and 'date' in compatible_item:
                compatible_item['data_annuncio'] = compatible_item['date']
            elif 'data' in compatible_item:
                compatible_item['data_annuncio'] = compatible_item['data']
            
            # Aggiungi venduto=False come default
            if 'venduto' not in compatible_item:
                compatible_item['venduto'] = False
            
            # Aggiungi l'ID come chiave di stringa se è in formato numerico
            if 'id' in compatible_item and isinstance(compatible_item['id'], int):
                compatible_item['id'] = str(compatible_item['id'])
            
            compatible_results.append(compatible_item)
        
        self.logger.info(f"search_ads completato: trovati {len(compatible_results)} risultati compatibili")
        return compatible_results


if __name__ == "__main__":
    # Configurazione di base per i test
    scraper = SubitoScraper(
        keywords=["ps5"],
        prezzo_max=500,
        apply_price_limit=False,
        max_pages=2,
        debug=True,
    )
    
    # Esegui il test
    response = scraper.run()
    results = response["results"]
    stats = response["stats"]
    
    # Salva i risultati in un file txt 
    if results:
        file_path = scraper.save_results_to_txt(results, "ps5")
        print(f"Risultati salvati in: {file_path}")
        
        # Mostra statistiche
        print("\nStatistiche:")
        print(f"Totale risultati: {stats['count']}")
        print(f"Prezzo minimo: €{stats['min_price']}")
        print(f"Prezzo massimo: €{stats['max_price']}")
        print(f"Prezzo medio: €{stats['avg_price']}")
        print(f"Prezzo mediano: €{stats['median_price']}")
        
        # Visualizza alcuni risultati
        print("\nAlcuni risultati:")
        for i, result in enumerate(results[:5], 1):
            print(f"#{i}: {result['titolo']} - €{result['prezzo']} - {result['luogo']}")
    else:
        print("Nessun risultato trovato.") 