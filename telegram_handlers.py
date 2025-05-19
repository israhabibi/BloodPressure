import os
import logging
from datetime import datetime
from telegram import Update, File as TelegramFile
from telegram.ext import ContextTypes

from config import AUTHORIZED_USER_ID, APP_SCRIPT_URL, DOWNLOAD_DIR
from gemini_service import analyze_tensimeter_image, analyze_text_with_gemini
from gsheet_service import send_to_gsheet
from prompts import GEMINI_IMAGE_ANALYSIS_PROMPT, GEMINI_TEXT_EXTRACTION_PROMPT

logger = logging.getLogger(__name__)

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

    # Ensure the download directory exists (should be done in main, but defensive here too)
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
        extracted_data = analyze_tensimeter_image(image_path, GEMINI_IMAGE_ANALYSIS_PROMPT)

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

__all__ = [
    "start_command",
    "handle_photo",
    "handle_text_message",
    "error_handler",
]