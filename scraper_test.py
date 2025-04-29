import requests
from bs4 import BeautifulSoup
import logging
from typing import List, Dict
import time
import random
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from app.config import KEYWORDS, PREZZO_MAX, LOG_FORMAT, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, APPLY_PRICE_LIMIT, MAX_PAGES
import os
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format=LOG_FORMAT
)
logger = logging.getLogger(__name__)

class SubitoScraper:
    BASE_URL = "https://www.subito.it/annunci-italia/vendita/usato/"
    RESULTS_FILE = "results.txt"

    def __init__(self, proxy=None):
        self.session = requests.Session()
        
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
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            data = {
                "chat_id": TELEGRAM_CHAT_ID,
                "text": message,
                "parse_mode": "HTML"
            }
            response = requests.post(url, data=data)
            response.raise_for_status()
            return True
        except Exception as e:
            logger.error(f"Error sending Telegram message: {e}")
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

        # Invia il riepilogo via Telegram
        summary = (
            f"🔍 <b>Risultati ricerca iPhone 15 256</b>\n\n"
            f"📊 Annunci trovati: {len(ads)}\n"
            f"📊 Disponibili: {len(available_ads)}\n"
            f"📊 Venduti: {len(sold_ads)}\n"
            f"❌ Ignorati (senza prezzo): {len(ignored_ads)} ({ignored_percentage:.1f}%)\n"
            f"📈 STR: {str_rate:.1f}%\n"
            f"💰 Prezzo medio disponibili: €{available_avg:.2f}\n"
            f"💰 Prezzo medio venduti: €{sold_avg:.2f}\n"
            f"📅 Periodo: da {oldest_date} a {newest_date} ({days_str})\n\n"
            f"<i>Dettagli completi nel file results.txt</i>"
        )
        self._send_telegram_message(summary)

        # Invia gli annunci più interessanti via Telegram (solo quelli con prezzo valido)
        if available_ads:
            # Ordina per prezzo (dal più basso)
            sorted_ads = sorted(available_ads, key=lambda x: x['price'])
            # Prendi i primi 3 annunci
            for ad in sorted_ads[:3]:
                message = (
                    f"🔍 <b>Annuncio interessante</b>\n\n"
                    f"📌 {ad['title']}\n"
                    f"💰 Prezzo: €{ad['price']}\n"
                    f"📍 Località: {ad['location']}\n"
                    f"📅 Data: {ad['date']}\n"
                    f"🔗 <a href='{ad['link']}'>Vedi annuncio</a>"
                )
                self._send_telegram_message(message)
                time.sleep(1)  # Pausa tra i messaggi

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
            for keyword in KEYWORDS:
                page = 1
                while True:
                    url = f"{self.BASE_URL}?q={keyword}&o={page}"
                    logger.info(f"Searching for: {keyword} at URL: {url}")
                    
                    # Aggiungi ritardo casuale tra le richieste
                    time.sleep(random.uniform(2, 5))
                    
                    response = self.session.get(url)
                    response.raise_for_status()
                    
                    # Salva l'HTML di debug
                    with open(f'debug_{keyword}_page_{page}.html', 'w', encoding='utf-8') as f:
                        f.write(response.text)
                    
                    soup = BeautifulSoup(response.text, 'html.parser')
                    
                    # Conta gli annunci in questa pagina
                    ads_in_page = 0
                    
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
                            
                            # Check if price is within limit (solo se APPLY_PRICE_LIMIT è True)
                            if not APPLY_PRICE_LIMIT or price <= PREZZO_MAX:
                                all_ads.append({
                                    'id': ad_id,
                                    'title': title,
                                    'price': price,
                                    'link': link,
                                    'location': location,
                                    'date': date,
                                    'details': details,
                                    'sold': sold
                                })
                                logger.info(f"Found matching ad: {title} - €{price} - {'Venduto' if sold else 'Disponibile'} - {location} - {date}")
                                ads_in_page += 1
                        
                        except (AttributeError, ValueError) as e:
                            logger.error(f"Error parsing ad: {e}")
                            continue
                    
                    # Se non ci sono annunci in questa pagina, abbiamo finito
                    if ads_in_page == 0:
                        break
                    
                    # Passa alla pagina successiva
                    page += 1
                    
                    # Limita il numero di pagine per evitare di sovraccaricare il server
                    if page > MAX_PAGES:
                        logger.warning(f"Raggiunto il limite massimo di {MAX_PAGES} pagine")
                        break
            
            # Salva i risultati in TXT
            self._save_to_txt(all_ads)
            
            return all_ads
            
        except requests.RequestException as e:
            logger.error(f"Error fetching ads: {e}")
            return []

def main():
    scraper = SubitoScraper()
    print("\n🔍 Inizio ricerca annunci...")
    print("=" * 50)
    
    ads = scraper.search_ads()
    
    if ads:
        print(f"\n✅ Trovati {len(ads)} annunci corrispondenti:")
        print(f"📊 Risultati salvati in {scraper.RESULTS_FILE}")
        print("=" * 50)
        # Mostra solo i primi 20 risultati
        for ad in ads[:20]:
            print(f"\n📌 {ad['title']}")
            print(f"💰 €{ad['price']} | 📍 {ad['location']} | 📅 {ad['date']}")
            print(f"📊 Stato: {'Venduto' if ad['sold'] else 'Disponibile'}")
            print(f"🔗 {ad['link']}")
            print("-" * 50)
    else:
        print("\n❌ Nessun annuncio trovato")

if __name__ == "__main__":
    main() 