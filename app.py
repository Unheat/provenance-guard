from flask import Flask, request, jsonify
from signals import get_llm_score, get_stylometric_score
from scoring import combine_signals
from config import RATE_LIMITS, PORT, DEBUG
import json
import uuid
from datetime import datetime, timezone
from audit_log import log_audit
from collections import deque
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

app = Flask(__name__)

# Custom key function: extract creator_id from JSON body
# NOTE: must be defined BEFORE the Limiter that references it
def get_creator_id():
    """
    Extract creator_id from request body for rate limiting.
    Falls back to IP address if creator_id is missing.
    """
    try:
        data = request.get_json()
        if data and data.get("creator_id"):
            return f"creator_{data.get('creator_id')}"  # Prefix to avoid conflicts
    except:
        pass
    return f"ip_{get_remote_address()}"  # Fallback to IP

# Initialize limiter with custom key function
limiter = Limiter(
    app=app,
    key_func=get_creator_id,
    default_limits=["200 per day", "50 per hour"]  # Global defaults
)


@app.route('/submit', methods=['POST'])
@limiter.limit(RATE_LIMITS["submit"])
def submit():
    """
    Classify text content to detect AI-generated work.

    Accepts a text submission and creator ID, runs two independent detection signals
    (LLM semantic analysis and stylometric heuristics), combines them into a confidence
    score, and returns a transparency label.

    Request body:
        {
            "text": "string (required) - text to classify",
            "creator_id": "string (required) - identifier for the creator"
        }

    Returns:
        {
            "content_id": "UUID string - unique identifier for this submission",
            "status": "success",
            "timestamp": "ISO 8601 string - when submission was processed",
            "combined_result": {
                "combined_confidence": float 0.0-1.0,
                "attribution": "likely_human" | "likely_ai" | "uncertain",
                "label": "transparency label text shown to users",
                "reasoning": {...}
            },
            "llm_reasoning": "string - explanation of LLM signal"
        }

    Status codes:
        200: Success - classification complete, logged to audit trail
        400: Bad request - missing text or creator_id
    """
    # 1. Extract text and creator_id from request safely
    # We use .get_json() just like Express's req.body
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Missing JSON request body"}), 400
        creator_id = data.get("creator_id")
        text = data.get("text")
        if not text or not creator_id:
            return jsonify({"error": "Missing 'text' or 'creator_id' in payload"}), 400
        
        llm_result = get_llm_score(text)
        stylometric_score = get_stylometric_score(text)
        llm_reasoning = llm_result.get("reasoning", "No reasoning provided.")
        combined_result = combine_signals(llm_result, stylometric_score)
        
        # generate data for both audit log and the response
        content_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc).isoformat() # ISO 8601 string format
        # step 6: Log to audit file (JSONL format)
        audit_entry = { 
            "creator_id": creator_id,
            "content_id": content_id, # Generate a UUID for this content
            "input_text": text[:500], # truncate to first 500 chars for storage efficiency
            "status": "success",
            "event_type": "classification",
            "timestamp": timestamp, # ISO 8601 string format
            "combined_result": combined_result,
            "llm_score": llm_result.get("llm_score", 0.0),
            "llm_reasoning": llm_reasoning,
            "stylometric_score": stylometric_score
        }
        # TODO : write audit_entry to a JSONL file for auditing purposes
        log_audit(audit_entry)
        # keep only data for frontend response, not the full audit log
        return jsonify({
            "content_id": content_id,
            "status": "success",
            "timestamp": timestamp, # ISO 8601 string format
            "combined_result": combined_result,
            "llm_reasoning": llm_reasoning,
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
    
@app.route('/log', methods=['GET'])
@limiter.limit(RATE_LIMITS["log"])
def get_log():
    """
    Retrieve the most recent audit log entries.

    Reads the append-only audit_log.jsonl file and returns the last 10 entries.
    Entries are ordered chronologically (newest entries appear last in the list,
    as per JSONL append semantics).

    No request body required.

    Returns:
        JSON array of up to 10 audit log entries, each containing:
        {
            "timestamp": "ISO 8601 string",
            "event_type": "submission" | "classification" | "appeal",
            "content_id": "UUID string",
            "creator_id": "string",
            "status": "success" | "classified" | "under_review",
            ... (other fields depend on event_type)
        }

    Status codes:
        200: Success - returns array (may be empty if no logs exist yet)
        500: Error reading audit log file
    """
    # Step 1: Read audit_log.jsonl (append-only, one JSON per line)
    # Step 2: Parse each line as JSON
    # Step 3: Keep only the last 10 entries
    # Step 4: Return as JSON array
    recent_entries = deque(maxlen=10)
    try:
        with open("audit_log.jsonl", "r", encoding="utf-8") as file:
            for line in file:
                clean_line = line.strip()
                if not clean_line:
                    continue
                # Step 2: Parse each line as JSON
                log_object = json.loads(clean_line)
                # Append to our fixed-size queue
                recent_entries.append(log_object)
    except FileNotFoundError:
        # Guard clause: return an empty list if no logs exist yet
        return jsonify([]), 200

    # Step 4: Return as a standard JSON array
    # We cast the deque back to a native Python list so jsonify can process it
    return jsonify(list(recent_entries)), 200

@app.route('/appeal', methods=['POST'])
@limiter.limit(RATE_LIMITS["appeal"])
def appeal():
    """
    Submit an appeal to contest a classification decision.

    Creators can appeal a classification they believe is incorrect. The appeal reason
    is logged with the original classification data, allowing human reviewers to
    re-evaluate the content with context provided by the creator.

    Request body:
        {
            "content_id": "UUID string (required) - from /submit response",
            "creator_reasoning": "string (required) - explanation of why classification is wrong"
        }

    Returns:
        {
            "status": "success",
            "content_id": "UUID string - the content being appealed",
            "message": "confirmation message",
            "next_steps": "guidance on human review timeline"
        }

    Status codes:
        200: Success - appeal logged and queued for human review
        400: Bad request - missing content_id or creator_reasoning
    """
    # 1. Get JSON data from request (same as /submit)
    data = request.get_json()
    if not data:
        return jsonify({"error": "Missing JSON request body"}), 400

    # 2. Extract fields from the request
    content_id = data.get("content_id")
    creator_reasoning = data.get("creator_reasoning")

    # 3. Validate required fields
    if not content_id or not creator_reasoning:
        return jsonify({"error": "Missing 'content_id' or 'creator_reasoning'"}), 400

    # 4. Create an appeal audit log entry (dict)
    # Hint: Use datetime.now(timezone.utc).isoformat() for timestamp
    appeal_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(), #Add ISO 8601 timestamp
        "event_type": "appeal",  # Important: this is an appeal event
        "content_id": content_id,
        "creator_reasoning": creator_reasoning,
        "status": "under_review"  # Mark as under review
    }

    # 5. Log the appeal to audit_log.jsonl
    log_audit(appeal_entry)


    # 6. Return success response
    # Should include: status, content_id, message, next_steps
    return jsonify({
        "status": "success",
        "content_id": content_id,
        "message": "Your appeal has been received and logged for human review.",
        "next_steps": "A member of our team will review your appeal within 48 hours."
    }), 200
# @app.route("/boom")
# def boom():
#     x = 1 / 0   # ZeroDivisionError
#     return str(x)
if __name__ == '__main__':
    app.run(debug=DEBUG, port=PORT)
