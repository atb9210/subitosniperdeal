import requests
from bs4 import BeautifulSoup
import logging
from typing import List, Dict
from .config import KEYWORDS, PREZZO_MAX, LOG_FORMAT

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format=LOG_FORMAT
)
logger = logging.getLogger(__name__)

class SubitoScraper:
    BASE_URL = "https://www.subito.it/auto-accessori/"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })

    def search_ads(self) -> List[Dict]:
        """Search for ads matching keywords and price criteria"""
        try:
            # Search for each keyword
            all_ads = []
            for keyword in KEYWORDS:
                url = f"{self.BASE_URL}?q={keyword}"
                logger.info(f"Searching for: {keyword} at URL: {url}")
                response = self.session.get(url)
                response.raise_for_status()
                
                # Debug: save HTML to file
                with open(f"debug_{keyword}.html", "w", encoding="utf-8") as f:
                    f.write(response.text)
                logger.info(f"Saved HTML to debug_{keyword}.html")
                
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Debug: print all div classes
                div_classes = set()
                for div in soup.find_all('div', class_=True):
                    div_classes.add(div['class'][0])
                logger.info(f"Found div classes: {div_classes}")
                
                for ad in soup.find_all('div', class_='item-card'):
                    try:
                        title = ad.find('h2', class_='item-title').text.strip()
                        price_text = ad.find('p', class_='item-price').text.strip()
                        price = float(price_text.replace('€', '').replace('.', '').replace(',', '.').strip())
                        link = ad.find('a')['href']
                        ad_id = link.split('/')[-1]
                        
                        # Check if price is within limit
                        if price <= PREZZO_MAX:
                            all_ads.append({
                                'id': ad_id,
                                'title': title,
                                'price': price,
                                'link': link
                            })
                            logger.info(f"Found matching ad: {title} - €{price}")
                    
                    except (AttributeError, ValueError) as e:
                        logger.error(f"Error parsing ad: {e}")
                        continue
            
            return all_ads
            
        except requests.RequestException as e:
            logger.error(f"Error fetching ads: {e}")
            return [] 