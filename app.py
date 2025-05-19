import google.generativeai as genai
from PIL import Image
import os
import json
import dotenv
import requests
import logging
from telegram import Update, File as TelegramFile
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from datetime import datetime # Add this import

# from prompt import GEMINI_PROMPT_V2

dotenv.load_dotenv()


# --- Configuration ---
# 1. Ensure your API key is set as an environment variable: GOOGLE_API_KEY
# 2. Set TELEGRAM_BOT_TOKEN for the bot to run.
# 3. Optionally, set APP_SCRIPT_URL to send data to Google Sheets.
#    OR, less securely, uncomment and set it directly here:

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
 
 
# Setup logging first
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Set higher logging level for libraries to avoid excessive noise
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram.ext").setLevel(logging.WARNING) # For python-telegram-bot library

# --- Constants ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DOWNLOAD_DIR = os.path.join(SCRIPT_DIR, "downloaded_gemini")

# --- Function to call Gemini ---
def analyze_tensimeter_image(image_path, prompt_text):
    """
    Sends an image and a prompt to Gemini and attempts to parse the structured response.
    """
    try:
        img = Image.open(image_path)
        # Use a model that supports vision, like 'gemini-1.5-pro-latest' or 'gemini-pro-vision'
        # 'gemini-1.5-flash-latest' is also a good, faster option for vision.
        model = genai.GenerativeModel('gemini-1.5-flash-latest')

        # Count tokens for the input
        token_count_response = model.count_tokens([prompt_text, img])
        # logger.info(f"🪙 Estimated token count for this request: {token_count_response.total_tokens}")

        logger.info(f"🖼️  Sending image '{image_path}' to Gemini...")
        # The API expects a list of parts for multimodal input
        response = model.generate_content([prompt_text, img])


        # Check for safety blocks or other issues
        if not response.parts:
            if response.prompt_feedback and response.prompt_feedback.block_reason:
                print(f"🛑 Request was blocked. Reason: {response.prompt_feedback.block_reason_message or response.prompt_feedback.block_reason}")
                return {"error": f"Request blocked: {response.prompt_feedback.block_reason_message or response.prompt_feedback.block_reason}"}
            else:
                print(f"🛑 No content parts in response. Full response: {response}")
                return {"error": "No content parts in response."}


        response_text = response.text.strip()
        logger.debug(f"Gemini's raw response for image analysis:\n{response_text}")

        # Attempt to parse as JSON
        try:
            # Handle potential markdown code block for JSON
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]
            
            data = json.loads(response_text)
            data["_token_count"] = token_count_response.total_tokens # Add token count to successful response
            logger.info("✅ Successfully parsed JSON response.")
            return data
        except json.JSONDecodeError as json_err:
            logger.warning(f"⚠️ Gemini did not return valid JSON. Error: {json_err}")
            logger.warning("   Returning raw text as a fallback.")
            return {"raw_text": response_text, "error_detail": str(json_err)} # Fallback

    except FileNotFoundError:
        logger.error(f"🚨 Error: Image file not found at '{image_path}'")
        return {"error": f"Image file not found: {image_path}"}
    except Exception as e:
        logger.error(f"🚨 An unexpected error occurred while calling Gemini: {e}", exc_info=True)
        # Log the full response if available and an error occurs
        if 'response' in locals() and hasattr(response, 'prompt_feedback') and response.prompt_feedback.block_reason:
             logger.error(f"   Gemini Block Reason: {response.prompt_feedback.block_reason}")
        return {"error": str(e)}

# --- Function to call Gemini for text analysis ---
def analyze_text_with_gemini(text_content, prompt_text):
    """
    Sends text content and a prompt to Gemini and attempts to parse the structured response.
    """
    try:
        # Use a model that supports text generation, like 'gemini-1.5-flash-latest'
        model = genai.GenerativeModel('gemini-1.5-flash-latest')

        # Count tokens for the input
        token_count_response = model.count_tokens([prompt_text, text_content])
        # logger.info(f"🪙 Estimated token count for this text request: {token_count_response.total_tokens}")

        logger.info(f"📝 Sending text content to Gemini for analysis: '{text_content[:100]}...'")
        response = model.generate_content([prompt_text, text_content])

        # Check for safety blocks or other issues
        if not response.parts:
            if response.prompt_feedback and response.prompt_feedback.block_reason:
                logger.error(f"🛑 Text analysis request was blocked. Reason: {response.prompt_feedback.block_reason_message or response.prompt_feedback.block_reason}")
                return {"error": f"Request blocked: {response.prompt_feedback.block_reason_message or response.prompt_feedback.block_reason}"}
            else:
                logger.error(f"🛑 No content parts in text analysis response. Full response: {response}")
                return {"error": "No content parts in response."}

        response_text = response.text.strip()
        logger.debug(f"Gemini's raw response for text analysis:\n{response_text}")

        # Attempt to parse as JSON
        try:
            # Handle potential markdown code block for JSON
            if response_text.startswith("```json"):
                response_text = response_text[7:] # len("```json")
            elif response_text.startswith("```"): # More generic markdown block
                response_text = response_text[3:]
            
            if response_text.endswith("```"):
                response_text = response_text[:-3]
            
            data = json.loads(response_text)
            data["_token_count"] = token_count_response.total_tokens # Add token count to successful response
            logger.info("✅ Successfully parsed JSON response from text analysis.")
            return data
        except json.JSONDecodeError as json_err:
            logger.warning(f"⚠️ Gemini did not return valid JSON from text analysis. Error: {json_err}")
            logger.warning("   Returning raw text as a fallback for text analysis.")
            return {"raw_text": response_text, "error_detail": str(json_err)} # Fallback

    except Exception as e:
        logger.error(f"🚨 An unexpected error occurred while calling Gemini for text analysis: {e}", exc_info=True)
        return {"error": str(e)}

# --- Function to send data to Google Sheets ---
def send_to_gsheet(data_json, webhook_url):
    """Sends JSON data to the specified Google Apps Script webhook URL."""
    if not webhook_url:
        logger.info("ℹ️ Google Sheets webhook URL (APP_SCRIPT_URL) is not configured. Skipping sending data to GSheet.")
        return False
    try:
        # Ensure data_json is a dictionary (JSON object)
        if not isinstance(data_json, dict):
            logger.error(f"❌ Data to be sent to GSheet is not a valid JSON object (dict): {data_json}")
            return False
        response = requests.post(webhook_url, json=data_json, timeout=20)
        response.raise_for_status() # Raise an exception for HTTP errors (4xx or 5xx)
        logger.info(f"✅ Data successfully sent to Google Sheets: {response.status_code}")
        return True
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Failed to send data to Google Sheets: {e}")
        return False

# --- Gemini Prompt ---
# This prompt instructs Gemini on what to look for and how to format the output.
GEMINI_PROMPT = """
You are an expert AI assistant specialized in reading medical device displays, specifically blood pressure monitors.
Analyze the provided image of a TensiOne blood pressure monitor.

Extract the following information:
1.  **Systolic blood pressure (SYS)**: The top large number, usually labeled SYS, in mmHg.
2.  **Diastolic blood pressure (DIA)**: The middle large number, usually labeled DIA, in mmHg.
3.  **Heart rate (P/min)**: The bottom smaller number, often labeled P/min or with a heart icon, in beats per minute.
4.  **Date**: If a date is visible on the display, extract it. Format as YYYY-MM-DD if possible.

Please return the extracted data in a structured JSON format.
Use the following keys: "systolic", "diastolic", "heart_rate", "date".
If a value is not clearly visible or not present on the display, use "Not visible" as the string value for that key.
Do not make up values. Only report what is visible.

Example of expected JSON output:
{
  "systolic": "105",
  "diastolic": "63",
  "heart_rate": "91",
  "date": "Not visible"
}

Another example if a date was present:
{
  "systolic": "120",
  "diastolic": "80",
  "heart_rate": "75",
  "date": "2024-07-28"
}
"""

# --- Gemini Prompt for Text Extraction ---
GEMINI_TEXT_EXTRACTION_PROMPT = """
You are an expert AI assistant specialized in extracting health-related information from text messages.
Analyze the provided text message.

Extract the following information if present:
1.  **Systolic blood pressure (SYS)**: e.g., "SYS 120", "tensi 120/80".
2.  **Diastolic blood pressure (DIA)**: e.g., "DIA 80", "tensi 120/80".
3.  **Heart rate (P/min)**: e.g., "HR 70", "nadi 70".
4.  **Waist circumference (lingkar perut)**: May be referred to as "lingkar perut", "lingkar pinggang", "LP", usually in centimeters (cm).
5.  **Body weight (berat badan)**: May be referred to as "berat badan", "BB", or "berat", usually in kilograms (kg).
6.  **Date**: If a date is mentioned in the text, extract it (format YYYY-MM-DD). If no date is mentioned, use "Not visible".

Please return the extracted data ONLY in a structured JSON format.
Use the following keys: "systolic", "diastolic", "heart_rate", "lingkar_perut", "berat_badan", "date".
If a value is not found in the text, use "Not visible" as the string value for that key.
Do not make up values. Only report what is found. Do not include any explanatory text before or after the JSON block.

Example of input text: "Hari ini LP 92 cm, BB 75.5 kg. Tensi kemarin 130/85, nadi 78."
Expected JSON output:
{
  "systolic": "130",
  "diastolic": "85",
  "heart_rate": "78",
  "lingkar_perut": "92",
  "berat_badan": "75.5",
  "date": "Not visible"
}

Another example: "BB 60kg, LP 80cm on 2024-07-20"
Expected JSON output:
{
  "systolic": "Not visible",
  "diastolic": "Not visible",
  "heart_rate": "Not visible",
  "lingkar_perut": "80",
  "berat_badan": "60",
  "date": "2024-07-20"
}
"""

# --- Telegram Bot Handlers ---
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a welcome message when the /start command is issued."""
    user = update.effective_user
    await update.message.reply_html(
        rf"Hi {user.mention_html()}! Send me an image of a TensiOne blood pressure monitor, and I'll try to read it using Gemini.",
    )

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles incoming photos, processes them with Gemini, and sends results."""
    if not update.message.photo:
        await update.message.reply_text("Please send an image file.")
        return

    if update.effective_user.id != AUTHORIZED_USER_ID:
        logger.info(f"Message from unauthorized user {update.effective_user.id}. Skipping processing.")
        await update.message.reply_text("Maaf, Anda tidak berwenang untuk menggunakan fitur ini.")
        return

    # Ensure the download directory exists
    if not os.path.exists(DOWNLOAD_DIR):
        os.makedirs(DOWNLOAD_DIR)
        logger.info(f"Created download directory: {DOWNLOAD_DIR}")

    photo_file: TelegramFile = await context.bot.get_file(update.message.photo[-1].file_id)
    
    timestamp = update.message.date.strftime('%Y%m%d_%H%M%S')
    file_extension = ".jpg" # Assuming JPEG, Telegram usually converts
    image_filename = f"gemini_{update.message.photo[-1].file_unique_id}_{timestamp}{file_extension}"
    image_path = os.path.join(DOWNLOAD_DIR, image_filename)

    await photo_file.download_to_drive(image_path)
    logger.info(f"Image downloaded to: {image_path}")

    await update.message.reply_text("Image received! Processing with Gemini... 🧠✨")

    try:
        extracted_data = analyze_tensimeter_image(image_path, GEMINI_PROMPT)

        reply_message = "--- Extracted Data (Gemini) ---\n"
        token_count_for_reply = extracted_data.get("_token_count", "N/A")
        if extracted_data and "error" in extracted_data:
            reply_message += f"Error: {extracted_data['error']}\n"
            if "error_detail" in extracted_data: # From JSON parsing error
                reply_message += f"Detail: {extracted_data['error_detail']}\n"
            if "raw_text" in extracted_data: # If analyze_tensimeter_image returned raw_text on JSON error
                reply_message += f"Raw text from Gemini: {extracted_data['raw_text']}\n"
            logger.error(f"Error processing image for user {update.effective_user.id} with Gemini: {extracted_data}")
        elif extracted_data and "raw_text" in extracted_data: # Fallback if JSON parsing failed inside analyze_tensimeter_image
            reply_message += "Could not parse JSON from Gemini. Raw output:\n"
            reply_message += extracted_data["raw_text"]
            logger.warning(f"JSON parsing failed for user {update.effective_user.id} with Gemini. Raw: {extracted_data['raw_text']}")
        elif extracted_data:
            systolic = extracted_data.get('systolic', 'N/A')
            diastolic = extracted_data.get('diastolic', 'N/A')
            heart_rate = extracted_data.get('heart_rate', 'N/A')
            date_val = extracted_data.get('date', 'Not visible') # Get date from Gemini

            # Ensure 'date' key exists for GSheet, even if "Not visible" or N/A
            # If date is "Not visible" or not found, use today's date
            if date_val == 'Not visible' or 'date' not in extracted_data:
                today_date_str = datetime.now().strftime('%Y-%m-%d')
                date_val = today_date_str # Update for reply message
                extracted_data['date'] = today_date_str # Update for GSheet
            # elif 'date' not in extracted_data: # This case is covered by the .get() default and the check above.
            #      extracted_data['date'] = datetime.now().strftime('%Y-%m-%d')

            reply_message += f"Systolic (SYS): {systolic} mmHg\n"
            reply_message += f"Diastolic (DIA): {diastolic} mmHg\n"
            reply_message += f"Heart Rate (P/min): {heart_rate} bpm\n"
            reply_message += f"Date: {date_val}\n"
            
            logger.info(f"Successfully processed image and extracted data for user {update.effective_user.id} with Gemini.")

            # Send to Google Sheets
            if APP_SCRIPT_URL:
                # Note: The Google Apps Script and Sheet headers will need to be updated
                # to include columns for 'lingkar_perut' and 'berat_badan' if you want
                # to store these new fields.
                if send_to_gsheet(extracted_data, APP_SCRIPT_URL):
                    reply_message += "\n✅ Data also saved to Google Sheets."
                else:
                    reply_message += "\n⚠️ Failed to save data to Google Sheets."
            else:
                reply_message += "\nℹ️ Google Sheets URL not configured; data not saved to GSheet."
        else:
            reply_message = "No data was extracted by Gemini or an unknown error occurred."
            logger.error(f"Unknown error or no data extracted by Gemini for user {update.effective_user.id}")

        reply_message += f"\n🪙 Estimated input tokens: {token_count_for_reply}"
        await update.message.reply_text(reply_message)

    except Exception as e:
        logger.error(f"Unhandled exception in handle_photo (Gemini) for user {update.effective_user.id}: {e}", exc_info=True)
        await update.message.reply_text(f"An unexpected error occurred while processing your image with Gemini: {e}")
    # Downloaded files are kept in DOWNLOAD_DIR

async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles incoming text messages, processes them with Gemini, and sends results."""
    if not update.message.text:
        return # Should be caught by filter, but good practice

    if update.effective_user.id != AUTHORIZED_USER_ID:
        logger.info(f"Text message from unauthorized user {update.effective_user.id}. Skipping processing.")
        await update.message.reply_text("Maaf, Anda tidak berwenang untuk menggunakan fitur ini.")
        return

    message_text = update.message.text
    logger.info(f"Received text message from user {update.effective_user.id}: \"{message_text}\"")
    await update.message.reply_text("Text message received! Analyzing with Gemini... 🧠💬")

    try:
        extracted_data = analyze_text_with_gemini(message_text, GEMINI_TEXT_EXTRACTION_PROMPT)

        reply_message = "--- Extracted Data from Text (Gemini) ---\n"
        token_count_for_reply = extracted_data.get("_token_count", "N/A")

        if extracted_data and "error" in extracted_data:
            reply_message += f"Error: {extracted_data['error']}\n"
            if "error_detail" in extracted_data:
                reply_message += f"Detail: {extracted_data['error_detail']}\n"
            if "raw_text" in extracted_data:
                reply_message += f"Raw text from Gemini: {extracted_data['raw_text']}\n"
            logger.error(f"Error processing text for user {update.effective_user.id} with Gemini: {extracted_data}")
        elif extracted_data and "raw_text" in extracted_data: # Fallback if JSON parsing failed
            reply_message += "Could not parse JSON from Gemini. Raw output:\n"
            reply_message += extracted_data["raw_text"]
            logger.warning(f"JSON parsing failed for text for user {update.effective_user.id} with Gemini. Raw: {extracted_data['raw_text']}")
        elif extracted_data:
            systolic = extracted_data.get('systolic', 'N/A')
            diastolic = extracted_data.get('diastolic', 'N/A')
            heart_rate = extracted_data.get('heart_rate', 'N/A')
            lingkar_perut = extracted_data.get('lingkar_perut', 'N/A')
            berat_badan = extracted_data.get('berat_badan', 'N/A')
            date_val = extracted_data.get('date', 'Not visible')

            # Ensure 'date' key exists for GSheet, default to today if "Not visible" or missing
            if date_val == 'Not visible' or not date_val or 'date' not in extracted_data : # Check for empty string too
                today_date_str = datetime.now().strftime('%Y-%m-%d')
                date_val = today_date_str # Update for reply message
                extracted_data['date'] = today_date_str # Update for GSheet

            reply_message += f"Systolic (SYS): {systolic} mmHg\n"
            reply_message += f"Diastolic (DIA): {diastolic} mmHg\n"
            reply_message += f"Heart Rate (P/min): {heart_rate} bpm\n"
            reply_message += f"Waist Circumference (LP): {lingkar_perut} cm\n"
            reply_message += f"Body Weight (BB): {berat_badan} kg\n"
            reply_message += f"Date: {date_val}\n"
            
            logger.info(f"Successfully processed text and extracted data for user {update.effective_user.id} with Gemini.")

            # Send to Google Sheets
            if APP_SCRIPT_URL:
                # Note: The Google Apps Script and Sheet headers will need to be updated
                # to include columns for 'lingkar_perut' and 'berat_badan'.
                # Ensure core BP keys are present for GSheet compatibility if script isn't updated yet.
                for key in ["systolic", "diastolic", "heart_rate"]:
                    extracted_data.setdefault(key, "Not visible")

                if send_to_gsheet(extracted_data, APP_SCRIPT_URL):
                    reply_message += "\n✅ Data also saved to Google Sheets."
                else:
                    reply_message += "\n⚠️ Failed to save data to Google Sheets."
            else:
                reply_message += "\nℹ️ Google Sheets URL not configured; data not saved to GSheet."
        else:
            reply_message = "No data was extracted from text by Gemini or an unknown error occurred."
            logger.error(f"Unknown error or no data extracted from text by Gemini for user {update.effective_user.id}")

        reply_message += f"\n🪙 Estimated input tokens: {token_count_for_reply}"
        await update.message.reply_text(reply_message)
    except Exception as e:
        logger.error(f"Unhandled exception in handle_text_message (Gemini) for user {update.effective_user.id}: {e}", exc_info=True)
        await update.message.reply_text(f"An unexpected error occurred while processing your text message with Gemini: {e}")

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log Errors caused by Updates."""
    logger.error(f"Update {update} caused error {context.error}", exc_info=context.error)

def main() -> None:
    """Start the bot."""
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))
    application.add_error_handler(error_handler)

    logger.info("Telegram bot (Gemini OCR) starting...")
    application.run_polling()

if __name__ == "__main__":
    main()