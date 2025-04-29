import requests
from bs4 import BeautifulSoup
import logging
from typing import List, Dict
import time
import random
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from app.config import (
    KEYWORDS, PREZZO_MAX, LOG_FORMAT, TELEGRAM_BOT_TOKEN, 
    TELEGRAM_CHAT_ID, APPLY_PRICE_LIMIT, MAX_PAGES, 
    INTERVALLO_MINUTI, LOG_FILE, DEBUG_DIR
)
import os
from datetime import datetime, timedelta
import schedule
import sys
import signal
import json

# File for saving PID and seen ads
PID_FILE = os.path.join(os.path.dirname(LOG_FILE), "snipe.pid")
RESULTS_FILE = os.path.join(os.path.dirname(LOG_FILE), "results.txt")
SEEN_ADS_FILE = os.path.join(os.path.dirname(LOG_FILE), "seen_ads.json")

# Create debug directory if it doesn't exist
os.makedirs(DEBUG_DIR, exist_ok=True)

def load_seen_ads() -> Dict:
    """Load seen ads from JSON file"""
    if os.path.exists(SEEN_ADS_FILE):
        try:
            with open(SEEN_ADS_FILE, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            return {}
    return {}

def save_seen_ads(seen_ads: Dict):
    """Save seen ads to JSON file"""
    with open(SEEN_ADS_FILE, 'w') as f:
        json.dump(seen_ads, f)

def clean_old_ads(seen_ads: Dict, days: int = 7) -> Dict:
    """Remove ads older than specified days"""
    current_time = datetime.now()
    cleaned_ads = {}
    
    for ad_id, ad_data in seen_ads.items():
        ad_time = datetime.fromisoformat(ad_data['timestamp'])
        if (current_time - ad_time).days <= days:
            cleaned_ads[ad_id] = ad_data
    
    return cleaned_ads

def save_pid():
    """Save the process PID"""
    with open(PID_FILE, 'w') as f:
        f.write(str(os.getpid()))

def remove_pid():
    """Rimuove il file PID"""
    if os.path.exists(PID_FILE):
        os.remove(PID_FILE)

def signal_handler(signum, frame):
    """Gestisce i segnali di terminazione"""
    logger.info("👋 Ricevuto segnale di terminazione")
    remove_pid()
    sys.exit(0)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format=LOG_FORMAT,
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8', mode='a'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class SubitoScraper:
    BASE_URL = "https://www.subito.it/annunci-italia/vendita/usato/"
    RESULTS_FILE = RESULTS_FILE

    def __init__(self, proxy=None):
        self.session = requests.Session()
        self.seen_ads = load_seen_ads()
        
        # Configurazione headers più realistici
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Cache-Control': 'max-age=0'
        })

        # Configurazione proxy se fornito
        if proxy:
            self.session.proxies = {
                'http': proxy,
                'https': proxy
            }

        # Configurazione retry strategy
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    def _extract_price(self, price_text: str) -> float:
        """Extract price from text and convert to float"""
        try:
            # Log del testo originale
            logger.debug(f"Original price text: {price_text}")
            
            # Rimuovi il simbolo dell'euro e gli spazi
            price_text = price_text.replace('€', '').replace(' ', '').strip()
            
            # Gestisci i casi speciali
            if 'trattabile' in price_text.lower():
                logger.info(f"Prezzo trattabile: {price_text}")
                return 0.0
            if 'scambio' in price_text.lower():
                logger.info(f"Prezzo scambio: {price_text}")
                return 0.0
            if 'gratis' in price_text.lower():
                logger.info(f"Prezzo gratis: {price_text}")
                return 0.0
            if 'permuta' in price_text.lower():
                logger.info(f"Prezzo permuta: {price_text}")
                return 0.0
            if 'vendita' in price_text.lower() and 'scambio' in price_text.lower():
                logger.info(f"Prezzo vendita/scambio: {price_text}")
                return 0.0
                
            # Sostituisci il punto con la virgola per i numeri decimali
            price_text = price_text.replace('.', '').replace(',', '.')
            
            # Rimuovi eventuali caratteri non numerici
            price_text = ''.join(c for c in price_text if c.isdigit() or c == '.')
            
            # Se il prezzo è vuoto o 0, logga il caso
            if not price_text:
                logger.warning(f"Prezzo vuoto dopo la pulizia: {price_text}")
                return 0.0
                
            price = float(price_text)
            if price == 0:
                logger.warning(f"Prezzo 0 dopo la conversione: {price_text}")
            
            return price
        except (ValueError, AttributeError) as e:
            logger.error(f"Error extracting price from '{price_text}': {e}")
            return 0.0

    def _check_sold_status(self, ad_element) -> bool:
        """Check if the ad is marked as sold"""
        try:
            # Cerca il badge "Venduto"
            sold_badge = ad_element.find('span', class_='item-sold-badge')
            return sold_badge is not None and 'Venduto' in sold_badge.text
        except (AttributeError, ValueError):
            return False

    def _extract_details(self, info_elements) -> Dict:
        """Extract details from info elements"""
        details = {}
        for element in info_elements:
            text = element.text.strip()
            if 'Km' in text:
                details['km'] = text
            elif any(year in text for year in ['/', '20']):
                details['anno'] = text
            elif text in ['Diesel', 'Benzina', 'Elettrica', 'Ibrida']:
                details['carburante'] = text
            elif text in ['Manuale', 'Automatico']:
                details['cambio'] = text
            elif 'Euro' in text:
                details['euro'] = text
            else:
                details['condizione'] = text
        return details

    def _send_telegram_message(self, message: str) -> bool:
        """Send message to Telegram"""
        try:
            if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
                logger.error("❌ Configurazione Telegram mancante! Verifica il file .env")
                return False
                
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            data = {
                "chat_id": TELEGRAM_CHAT_ID,
                "text": message,
                "parse_mode": "HTML"
            }
            logger.info(f"📤 Invio notifica Telegram a {TELEGRAM_CHAT_ID}")
            response = requests.post(url, data=data)
            response.raise_for_status()
            logger.info(f"✅ Notifica Telegram inviata con successo")
            return True
        except Exception as e:
            logger.error(f"❌ Errore nell'invio della notifica Telegram: {e}")
            return False

    def _save_to_txt(self, ads: List[Dict]):
        """Save results to text file with nice formatting"""
        # Rimuovi il file se esiste
        if os.path.exists(self.RESULTS_FILE):
            os.remove(self.RESULTS_FILE)
            
        # Filtra gli annunci con prezzo valido (> 0)
        valid_ads = [ad for ad in ads if ad['price'] > 0]
        ignored_ads = [ad for ad in ads if ad['price'] == 0]
        
        # Conta gli annunci disponibili e venduti (solo quelli con prezzo valido)
        available_ads = [ad for ad in valid_ads if not ad['sold']]
        sold_ads = [ad for ad in valid_ads if ad['sold']]
        
        # Calcola i prezzi medi (solo per annunci con prezzo valido)
        available_avg = sum(ad['price'] for ad in available_ads) / len(available_ads) if available_ads else 0
        sold_avg = sum(ad['price'] for ad in sold_ads) / len(sold_ads) if sold_ads else 0
        
        # Calcola il Sell Through Rate (solo per annunci con prezzo valido)
        str_rate = (len(sold_ads) / len(valid_ads)) * 100 if valid_ads else 0
        
        # Calcola la percentuale di annunci ignorati
        ignored_percentage = (len(ignored_ads) / len(ads)) * 100 if ads else 0
        
        # Estrai le date valide (escludendo gli ID)
        valid_dates = [ad['date'] for ad in valid_ads if not ad['date'].startswith('ID:')]
        if valid_dates:
            oldest_date = min(valid_dates)
            newest_date = max(valid_dates)
            
            # Calcola il numero di giorni
            try:
                # Converti le date in oggetti datetime
                date_format = "%d %b alle %H:%M"
                oldest = datetime.strptime(oldest_date, date_format)
                newest = datetime.strptime(newest_date, date_format)
                
                # Calcola la differenza in giorni
                days_diff = (newest - oldest).days
                if days_diff == 0:
                    days_str = "1 giorno"
                else:
                    days_str = f"{days_diff + 1} giorni"
            except ValueError:
                # Se il formato non è corretto, prova a estrarre solo il giorno
                try:
                    oldest_day = int(oldest_date.split()[0])
                    newest_day = int(newest_date.split()[0])
                    days_diff = newest_day - oldest_day
                    if days_diff == 0:
                        days_str = "1 giorno"
                    else:
                        days_str = f"{days_diff + 1} giorni"
                except (ValueError, IndexError):
                    days_str = "N/A"
        else:
            oldest_date = "N/A"
            newest_date = "N/A"
            days_str = "N/A"
            
        # Crea il file di testo con formattazione migliorata
        with open(self.RESULTS_FILE, 'w', encoding='utf-8') as f:
            f.write(f"🔍 Risultati ricerca: {len(ads)} annunci trovati\n")
            f.write(f"📊 Annunci disponibili: {len(available_ads)}\n")
            f.write(f"📊 Annunci venduti: {len(sold_ads)}\n")
            f.write(f"❌ Annunci ignorati (senza prezzo): {len(ignored_ads)} ({ignored_percentage:.1f}%)\n")
            f.write(f"📈 Sell Through Rate: {str_rate:.1f}%\n")
            f.write(f"💰 Prezzo medio disponibili: €{available_avg:.2f}\n")
            f.write(f"💰 Prezzo medio venduti: €{sold_avg:.2f}\n")
            f.write(f"📅 Periodo: da {oldest_date} a {newest_date} ({days_str})\n")
            f.write("=" * 80 + "\n\n")
            
            # Scrivi i dati (solo annunci con prezzo valido)
            for ad in valid_ads:
                f.write(f"📌 {ad['title']}\n")
                f.write(f"💰 Prezzo: €{ad['price']}\n")
                f.write(f"📍 Località: {ad['location']}\n")
                f.write(f"📅 Data: {ad['date']}\n")
                f.write(f"📊 Stato: {'Venduto' if ad['sold'] else 'Disponibile'}\n")
                f.write(f"🔗 Link: {ad['link']}\n")
                f.write("-" * 80 + "\n\n")

    def _extract_location(self, ad_element) -> str:
        """Extract location from ad element"""
        try:
            # Prova prima con il selettore standard
            location_element = ad_element.find('span', class_='index-module_town__2H3jy')
            if location_element:
                return location_element.text.strip()
            
            # Prova con il selettore alternativo
            location_element = ad_element.find('span', class_='index-module_city__2H3jy')
            if location_element:
                return location_element.text.strip()
            
            # Prova a estrarre dalla URL
            link_element = ad_element.find('a', class_='SmallCard-module_link__hOkzY')
            if link_element and 'href' in link_element.attrs:
                url = link_element['href']
                # Estrai la città dall'URL (es. ...-milano-123456.htm)
                parts = url.split('-')
                if len(parts) >= 2:
                    return parts[-2].capitalize()
            
            return "N/A"
        except (AttributeError, ValueError):
            return "N/A"

    def _extract_date(self, ad_element) -> str:
        """Extract date from ad element"""
        try:
            # Prova tutti i possibili selettori per la data
            date_selectors = [
                'span.index-module_date__Fmf-4',
                'span.index-module_time__Fmf-4',
                'span.index-module_date__Fmf-4.index-module_with-spacer__UNkQz',
                'span.index-module_sbt-text-atom__ifYVU.index-module_token-caption__tLxvZ.index-module_size-small__qLPdh.index-module_weight-semibold__p5-q6.index-module_date__Fmf-4',
                'span.index-module_sbt-text-atom__ifYVU.index-module_token-caption__tLxvZ.index-module_size-small__qLPdh.index-module_weight-semibold__p5-q6.index-module_date__Fmf-4.index-module_with-spacer__UNkQz'
            ]
            
            for selector in date_selectors:
                date_element = ad_element.select_one(selector)
                if date_element and date_element.text.strip():
                    return date_element.text.strip()
            
            # Se non trova la data, prova a cercare in altri elementi
            date_elements = ad_element.find_all('span', class_=lambda x: x and 'date' in x.lower())
            for element in date_elements:
                if element.text.strip():
                    return element.text.strip()
            
            # Se ancora non trova la data, prova a cercare in altri elementi
            date_elements = ad_element.find_all('span', class_=lambda x: x and 'time' in x.lower())
            for element in date_elements:
                if element.text.strip():
                    return element.text.strip()
            
            # Se non trova la data, mostra l'ID dell'annuncio
            link_element = ad_element.find('a', class_='SmallCard-module_link__hOkzY')
            if link_element and 'href' in link_element.attrs:
                url = link_element['href']
                ad_id = url.split('/')[-1].replace('.htm', '')
                logger.warning(f"Data non trovata per l'annuncio {ad_id}, usando ID come fallback")
                return f"ID: {ad_id}"
            
            logger.warning("Data non trovata e nessun ID disponibile, usando N/A")
            return "N/A"
        except (AttributeError, ValueError) as e:
            logger.error(f"Error extracting date: {e}")
            return "N/A"

    def search_ads(self) -> List[Dict]:
        """Search for ads matching keywords and price criteria"""
        try:
            # Search for each keyword
            all_ads = []
            new_ads = []  # Lista per tenere traccia dei nuovi annunci
            
            for keyword in KEYWORDS:
                url = f"{self.BASE_URL}?q={keyword}"
                logger.info(f"🔍 Ricerca in corso per: {keyword} at URL: {url}")
                response = self.session.get(url)
                response.raise_for_status()
                
                # Debug: save HTML to file
                debug_file = os.path.join(DEBUG_DIR, f"debug_{keyword}.html")
                with open(debug_file, "w", encoding="utf-8") as f:
                    f.write(response.text)
                logger.info(f"💾 HTML salvato in {debug_file}")
                
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Cerca gli annunci usando il nuovo selettore
                for ad in soup.find_all('div', class_='SmallCard-module_card__3hfzu'):
                    try:
                        # Estrai il titolo
                        title_element = ad.find('h2', class_='ItemTitle-module_item-title__VuKDo')
                        if not title_element:
                            continue
                        title = title_element.text.strip()
                        
                        # Estrai il prezzo
                        price_element = ad.find('p', class_='index-module_price__N7M2x')
                        if not price_element:
                            continue
                        price = self._extract_price(price_element.text)
                        
                        # Estrai il link
                        link_element = ad.find('a', class_='SmallCard-module_link__hOkzY')
                        if not link_element:
                            continue
                        link = link_element['href']
                        ad_id = link.split('/')[-1].replace('.htm', '')
                        
                        # Estrai la località e la data
                        location = self._extract_location(ad)
                        date = self._extract_date(ad)
                        
                        # Estrai i dettagli
                        info_elements = ad.find_all('p', class_='index-module_info__GDGgZ')
                        details = self._extract_details(info_elements)
                        
                        # Verifica se l'annuncio è venduto
                        sold = self._check_sold_status(ad)
                        
                        # Check if price is within limit
                        if price <= PREZZO_MAX:
                            # Verifica se l'annuncio è già stato visto
                            is_new = ad_id not in self.seen_ads
                            
                            # Se l'annuncio è nuovo e disponibile, aggiungilo alla lista
                            if not sold and is_new:
                                new_ads.append({
                                    'title': title,
                                    'price': price,
                                    'location': location,
                                    'date': date,
                                    'link': link
                                })
                                
                                # Salva l'annuncio come visto
                                self.seen_ads[ad_id] = {
                                    'title': title,
                                    'price': price,
                                    'timestamp': datetime.now().isoformat()
                                }
                            
                            all_ads.append({
                                'id': ad_id,
                                'title': title,
                                'price': price,
                                'link': link,
                                'location': location,
                                'date': date,
                                'details': details,
                                'sold': sold,
                                'notification_sent': False
                            })
                            logger.info(f"✅ Annuncio trovato: {title} - €{price} - {location} - {'Venduto' if sold else 'Disponibile'}")
                    
                    except (AttributeError, ValueError) as e:
                        logger.error(f"❌ Errore nel parsing dell'annuncio: {e}")
                        continue
            
            # Salva i risultati nel file
            if all_ads:
                self._save_to_txt(all_ads)
                logger.info(f"💾 Risultati salvati in {self.RESULTS_FILE}")
                
                # Invia il messaggio combinato solo se ci sono nuovi annunci
                if new_ads:
                    available_ads = [ad for ad in all_ads if not ad['sold']]
                    sold_ads = [ad for ad in all_ads if ad['sold']]
                    ignored_ads = [ad for ad in all_ads if ad['price'] == 0]
                    
                    # Calcola le statistiche
                    str_rate = (len(sold_ads) / len(all_ads)) * 100 if all_ads else 0
                    available_avg = sum(ad['price'] for ad in available_ads) / len(available_ads) if available_ads else 0
                    sold_avg = sum(ad['price'] for ad in sold_ads) / len(sold_ads) if sold_ads else 0
                    ignored_percentage = (len(ignored_ads) / len(all_ads)) * 100 if all_ads else 0
                    
                    # Estrai le date valide
                    valid_dates = [ad['date'] for ad in all_ads if not ad['date'].startswith('ID:')]
                    if valid_dates:
                        oldest_date = min(valid_dates)
                        newest_date = max(valid_dates)
                        days_str = "1 giorno"  # Per ora hardcoded a 1 giorno
                    else:
                        oldest_date = "N/A"
                        newest_date = "N/A"
                        days_str = "N/A"
                    
                    # Prepara il messaggio combinato
                    message = f"🔍 <b>Nuovi annunci trovati per {keyword}</b>\n\n"
                    
                    # Aggiungi i dettagli dei nuovi annunci
                    for ad in new_ads:
                        message += (
                            f"📱 {ad['title']}\n"
                            f"💰 €{ad['price']}\n"
                            f"📍 {ad['location']}\n"
                            f"📅 {ad['date']}\n"
                            f"🔗 {ad['link']}\n\n"
                        )
                    
                    # Aggiungi il riassunto
                    message += (
                        f"📊 <b>Riepilogo</b>\n"
                        f"📊 Annunci trovati: {len(all_ads)}\n"
                        f"📊 Disponibili: {len(available_ads)}\n"
                        f"📊 Venduti: {len(sold_ads)}\n"
                        f"❌ Ignorati (senza prezzo): {len(ignored_ads)} ({ignored_percentage:.1f}%)\n"
                        f"📈 STR: {str_rate:.1f}%\n"
                        f"💰 Prezzo medio disponibili: €{available_avg:.2f}\n"
                        f"💰 Prezzo medio venduti: €{sold_avg:.2f}\n"
                        f"📅 Periodo: da {oldest_date} a {newest_date} ({days_str})\n\n"
                        f"<i>Dettagli completi nel file results.txt</i>"
                    )
                    
                    # Invia il messaggio
                    self._send_telegram_message(message)
            
            # Pulisci gli annunci vecchi e salva
            self.seen_ads = clean_old_ads(self.seen_ads)
            save_seen_ads(self.seen_ads)
            
            return all_ads
            
        except requests.RequestException as e:
            logger.error(f"❌ Errore nel recupero degli annunci: {e}")
            return []

def log_execution(keyword, status, num_ads=None, error=None, notification_sent=False):
    """Logga una riga con le informazioni essenziali dell'esecuzione"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Prepara il messaggio base
    message = f"[{timestamp}] 🔍 {keyword} | "
    
    # Aggiungi lo stato
    if status == "success":
        message += f"✅ Ricerca completata con successo | {num_ads} annunci trovati"
        if notification_sent:
            message += " | 📱 Notifica inviata"
    elif status == "error":
        message += f"❌ Errore: {error}"
    else:
        message += f"⚠️ {status}"
    
    # Scrivi direttamente nel file di log
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(message + "\n")
    
    # Log anche su console
    logger.info(message)

def job():
    """Esegue lo scraper e logga i risultati"""
    logger.info(f"\n{'='*50}")
    logger.info(f"🔄 Esecuzione programmata: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    for keyword in KEYWORDS:
        try:
            scraper = SubitoScraper()
            ads = scraper.search_ads()
            
            if ads:
                # Verifica se sono state inviate notifiche
                notification_sent = any(ad.get('notification_sent', False) for ad in ads)
                log_execution(keyword, "success", len(ads), notification_sent=notification_sent)
            else:
                log_execution(keyword, "no_results")
                
        except Exception as e:
            log_execution(keyword, "error", error=str(e))
    
    logger.info(f"{'='*50}\n")

def main():
    """Funzione principale con scheduler integrato"""
    # Gestione dei segnali
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    # Salva il PID
    save_pid()
    
    # Crea il file di log se non esiste
    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, 'w', encoding='utf-8') as f:
            f.write("=== LOGS SCRAPER SUBITO.IT ===\n")
            f.write(f"Intervallo di esecuzione: {INTERVALLO_MINUTI} minuti\n")
            f.write("=" * 50 + "\n\n")
    
    # Scrivi l'avvio nel file di log
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 🚀 Avvio del programma (PID: {os.getpid()})\n")
        f.write(f"⏰ Intervallo di esecuzione: {INTERVALLO_MINUTI} minuti\n")
    
    logger.info("🚀 Avvio del programma")
    logger.info(f"⏰ Intervallo di esecuzione: {INTERVALLO_MINUTI} minuti")
    logger.info(f"📝 PID: {os.getpid()}")
    
    # Esegui subito la prima volta
    job()
    
    # Programma l'esecuzione periodica
    schedule.every(INTERVALLO_MINUTI).minutes.do(job)
    
    logger.info("📅 Scheduler avviato - In attesa di nuove esecuzioni...")
    
    # Loop principale
    try:
        while True:
            schedule.run_pending()
            time.sleep(1)
    except Exception as e:
        logger.error(f"❌ Errore nel loop principale: {e}")
    finally:
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 👋 Programma terminato\n")
        remove_pid()
        logger.info("👋 Programma terminato")

if __name__ == "__main__":
    main() 