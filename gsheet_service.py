import requests
import logging

logger = logging.getLogger(__name__)

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

__all__ = [
    "send_to_gsheet",
]