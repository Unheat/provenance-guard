from flask import Flask, request, jsonify
from signals import get_llm_score, get_stylometric_score
from scoring import combine_signals
import json
import uuid
from datetime import datetime, timezone
from audit_log import log_audit
app = Flask(__name__)

@app.route('/submit', methods=['POST'])
def submit(): 
    """
    POST /submit - Classify a piece of content
    
    1. Extract text and creator_id from request
    2. Call get_llm_score(text)
    3. Call get_stylometric_score(text)
    4. Call combine_signals(llm_result, stylometric_score)
    5. Generate content_id (UUID)
    6. Log to audit file (JSONL format)
    7. Return response
    receive { text: "...", creator_id: "..." }
    return { combined_confidence, attribution, label, reasoning }
    """
    """
    POST /submit - Classify a piece of content
    """
    # 1. Extract text and creator_id from request safely
    # We use .get_json() just like Express's req.body
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


if __name__ == '__main__':
    app.run(debug=True, port=5000)
