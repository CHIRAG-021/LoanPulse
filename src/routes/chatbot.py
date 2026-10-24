"""Chatbot route endpoints for LoanPulse customer support assistant."""
import time
from flask import Blueprint, request, jsonify, session
from flask_login import current_user

from src.services.chatbot_service import (
    get_assistant_config,
    process_customer_message,
    MAX_MESSAGE_LENGTH,
)

chatbot_bp = Blueprint("chatbot", __name__)

RATE_LIMIT_WINDOW_SECONDS = 60
RATE_LIMIT_MAX_REQUESTS = 25


def _check_rate_limit() -> bool:
    """Session-based sliding window rate limiter."""
    now = time.time()
    history = session.get("_chat_rate_history", [])
    # Keep only timestamps within window
    history = [t for t in history if now - t < RATE_LIMIT_WINDOW_SECONDS]
    if len(history) >= RATE_LIMIT_MAX_REQUESTS:
        return False
    history.append(now)
    session["_chat_rate_history"] = history
    return True


@chatbot_bp.route("/chatbot/config", methods=["GET"])
def chatbot_config():
    """Return assistant configuration, metadata, and starter suggested questions."""
    return jsonify(get_assistant_config()), 200


@chatbot_bp.route("/chatbot/message", methods=["POST"])
def chatbot_message():
    """Process incoming customer support chat message.

    Accepts JSON: {"message": str}
    Enforces rate-limiting, character limits, CSRF protection, and role-safe processing.
    """
    if not _check_rate_limit():
        return jsonify({
            "error": "Rate limit exceeded. Please wait a moment before sending more messages.",
            "reply": "You have sent several messages quickly. Please wait a moment before asking another question.",
            "suggested_questions": []
        }), 429

    data = request.get_json(silent=True) or request.form
    message = data.get("message", "") if data else ""

    if not isinstance(message, str):
        return jsonify({"error": "Invalid message format.", "reply": "Invalid message payload."}), 400

    result = process_customer_message(message, current_user=current_user)

    if "error" in result:
        return jsonify(result), 400

    return jsonify(result), 200
