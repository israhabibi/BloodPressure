import os
import dotenv
import logging

from telegram.ext import Application, CommandHandler, MessageHandler, filters

dotenv.load_dotenv()

from config import TELEGRAM_BOT_TOKEN, AUTHORIZED_USER_ID, APP_SCRIPT_URL, DOWNLOAD_DIR

# --- Configuration ---
# 1. Ensure your API key is set as an environment variable: GOOGLE_API_KEY
# 2. Set TELEGRAM_BOT_TOKEN for the bot to run.
# 3. Optionally, set APP_SCRIPT_URL to send data to Google Sheets.
#    OR, less securely, uncomment and set it directly here:

# Setup logging first
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Set higher logging level for libraries to avoid excessive noise
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram.ext").setLevel(logging.WARNING) # For python-telegram-bot library

from telegram_handlers import start_command, handle_photo, handle_text_message, error_handler

def main() -> None:
    """Start the bot."""
    # Ensure download directory exists early
    if not os.path.exists(DOWNLOAD_DIR):
        os.makedirs(DOWNLOAD_DIR)
        logging.info(f"Created download directory: {DOWNLOAD_DIR}")

    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))
    application.add_error_handler(error_handler)

    logging.info("Telegram bot (Gemini OCR) starting...")
    application.run_polling()

if __name__ == "__main__":
    main()