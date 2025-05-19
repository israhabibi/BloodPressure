import google.generativeai as genai
from PIL import Image
import json
import logging

logger = logging.getLogger(__name__)

# Ensure Gemini is configured (this happens when config.py is imported)
# import config

# --- Function to call Gemini for Image Analysis ---
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
                logger.error(f"🛑 Request was blocked. Reason: {response.prompt_feedback.block_reason_message or response.prompt_feedback.block_reason}")
                return {"error": f"Request blocked: {response.prompt_feedback.block_reason_message or response.prompt_feedback.block_reason}"}
            else:
                logger.error(f"🛑 No content parts in response. Full response: {response}")
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

__all__ = [
    "analyze_tensimeter_image",
    "analyze_text_with_gemini",
]