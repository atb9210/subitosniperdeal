import os
from dotenv import load_dotenv

# Base directory
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Load environment variables from .env file in the backend directory
load_dotenv(os.path.join(BASE_DIR, '.env'))

# Search configuration
KEYWORDS = ["xbox series s 512gb"]
PREZZO_MAX = 150
APPLY_PRICE_LIMIT = False  # Flag per controllare se applicare il limite di prezzo
MAX_PAGES = 3  # Numero massimo di pagine da leggere
# Execution interval (in minutes)
INTERVALLO_MINUTI = 1  # Default to 1 minute if not specified

# Directory configuration
DATA_DIR = os.path.join(BASE_DIR, 'data')
LOGS_DIR = os.path.join(BASE_DIR, 'logs')

# Create necessary directories if they don't exist
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(LOGS_DIR, exist_ok=True)

# File paths
DB_FILE = os.path.join(DATA_DIR, "seen_ads.json")
LOG_FILE = os.path.join(LOGS_DIR, "snipe.log")
DEBUG_DIR = os.path.join(DATA_DIR, "debug")

# Logging configuration
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

# Telegram configuration
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')