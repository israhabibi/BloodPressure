import os
import google.generativeai as genai

# --- Configuration & Initialization ---

# 1. Load and validate GOOGLE_API_KEY
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    # Logger might not be configured yet, so print is used.
    print("🚨 GOOGLE_API_KEY environment variable not set.")
    print("Please set it before running the script.")
    print("Example (Linux/macOS): export GOOGLE_API_KEY='YOUR_API_KEY'")
    print("Example (Windows PowerShell): $env:GOOGLE_API_KEY='YOUR_API_KEY'")
    exit(1)

# 2. Configure Gemini
try:
    genai.configure(api_key=GOOGLE_API_KEY)
except Exception as e:
    print(f"🚨 Error configuring Gemini: {e}")
    exit(1)

# 3. Load other environment variables
APP_SCRIPT_URL = os.getenv("APP_SCRIPT_URL") # Used in send_to_gsheet, can be None
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
AUTHORIZED_USER_ID_STR = os.getenv("AUTHORIZED_USER_ID")

# 4. Validate critical environment variables
if not TELEGRAM_BOT_TOKEN:
    print("🚨 TELEGRAM_BOT_TOKEN environment variable not set. The bot cannot start.")
    exit(1)

AUTHORIZED_USER_ID = None
if AUTHORIZED_USER_ID_STR:
    try:
        AUTHORIZED_USER_ID = int(AUTHORIZED_USER_ID_STR)
    except ValueError:
        print(f"🚨 AUTHORIZED_USER_ID ('{AUTHORIZED_USER_ID_STR}') is not a valid integer. Please check your .env file or environment variables.")
        exit(1)
else:
    # Assuming AUTHORIZED_USER_ID is mandatory for the bot to operate securely.
    # If it's optional, you might want to handle this differently (e.g., log a warning).
    print("🚨 AUTHORIZED_USER_ID environment variable not set or empty. This is required for bot operation.")
    exit(1)

# --- Constants ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DOWNLOAD_DIR = os.path.join(SCRIPT_DIR, "downloaded_gemini")

# Export variables for other modules to import
__all__ = [
    "GOOGLE_API_KEY",
    "APP_SCRIPT_URL",
    "TELEGRAM_BOT_TOKEN",
    "AUTHORIZED_USER_ID",
    "SCRIPT_DIR",
    "DOWNLOAD_DIR",
]