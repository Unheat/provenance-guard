import json
def log_audit(audit_entry :dict) -> None:
    """
    log_audit: Log an audit entry to a JSONL file.
    AGRS:
        audit_entry: dict containing the audit log entry to be written to the file.
        audit_entry = {
            "creator_id": str,
            "content_id": str,
            "input_text": str,
            "status": str,
            "timestamp": str,
            "combined_result": dict,
            "llm_score": float,
            "llm_reasoning": str,
            "stylometric_score": float
        }
    """
    try:
        with open('audit_log.jsonl', 'a') as f:
            json.dump(audit_entry, f)
            f.write('\n')  # Newline for JSONL format
    except Exception as e:
        print(f"Error logging audit entry: {e}")