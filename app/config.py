import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Search configuration
KEYWORDS = ["iphone 15 256"]
PREZZO_MAX = 250
APPLY_PRICE_LIMIT = False  # Flag per controllare se applicare il limite di prezzo
MAX_PAGES = 10  # Numero massimo di pagine da leggere

# Logging configuration
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

# Telegram configuration
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

# Database configuration
DB_FILE = "seen_ads.json"

# Logging configuration
LOG_FILE = "logs/snipe.log" 