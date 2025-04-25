import os
import logging
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

# Load env variables
load_dotenv(dotenv_path=".env.local")

# Constants
FLASK_PORT = os.getenv("FLASK_PORT", 5000)
CHARS_PER_SECOND = float(os.getenv("CHARS_PER_SECOND", 12.5))
MAX_AUDIO_DURATION_SECONDS = float(os.getenv("MAX_AUDIO_DURATION_SECONDS", 60))
APPROVAL_THRESHOLD = MAX_AUDIO_DURATION_SECONDS * CHARS_PER_SECOND

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("validation-server")

# App setup
app = Flask(__name__)
CORS(app)

@app.route('/validate', methods=['POST'])
def validate_audio_length():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({
            "error": "Invalid or missing JSON payload",
            "required": ["text", "estimated_length"]
        }), 400

    text = data.get("text")
    estimated_length = data.get("estimated_length")

    if not text or estimated_length is None:
        return jsonify({
            "error": "Missing required parameters",
            "required": ["text", "estimated_length"]
        }), 400

    try:
        estimated_length = float(estimated_length)
    except (ValueError, TypeError):
        return jsonify({"error": "'estimated_length' must be a number"}), 400

    logger.info(f"Received request: {estimated_length:.2f}s, text preview: '{text[:50]}...'")

    if estimated_length <= MAX_AUDIO_DURATION_SECONDS:
        logger.info("Text approved without modifications")
        return jsonify({
            "approved": True,
            "message": "Audio length within acceptable limits"
        })

    logger.info("Text exceeds limit, trimming...")

    # Trim the text to the center part
    chars_limit = int(APPROVAL_THRESHOLD)
    middle = len(text) // 2
    half_limit = chars_limit // 2
    start = max(0, middle - half_limit)
    end = min(len(text), middle + half_limit)
    trimmed_text = text[start:end]

    # Improve boundary alignment
    if start > 0:
        first_period = trimmed_text.find('. ')
        if 0 <= first_period < len(trimmed_text) // 4:
            trimmed_text = trimmed_text[first_period + 2:]

    last_periods = [trimmed_text.rfind(p) for p in ['. ', '? ', '! ']]
    last_valid_end = max(last_periods)
    if last_valid_end > len(trimmed_text) * 3 // 4:
        trimmed_text = trimmed_text[:last_valid_end + 1]

    logger.info("Text trimmed and ready to return")
    return jsonify({
        "approved": False,
        "modified_text": trimmed_text,
        "original_length": estimated_length,
        "modified_length": len(trimmed_text) / CHARS_PER_SECOND
    })


if __name__ == '__main__':
    port = int(os.getenv("PORT", FLASK_PORT))
    debug = os.getenv("FLASK_ENV", "development") == "development"

    logger.info(f"Starting server on port {port} (debug={debug})")
    app.run(host="0.0.0.0", port=port, debug=debug)
