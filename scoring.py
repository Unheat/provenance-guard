def combine_signals(llm_result: dict, stylometric_score: float) -> dict:
    """
    Combine two signals into a single confidence score and label.
    
    Args:
        llm_result: dict with keys "llm_score" and "reasoning"
        stylometric_score: float 0.0-1.0
    
    Returns:
        dict with:
        - combined_confidence: float 0.0-1.0
        - attribution: "likely_human" | "likely_ai" | "uncertain"
        - label: transparency label text (what users see)
        - reasoning: dict with both signal details
    """
    try:
        llm_score = llm_result.get("llm_score", 0.0)
        llm_reasoning = llm_result.get("reasoning", "No reasoning provided.")
        
        combined_confidence = (llm_score + stylometric_score) / 2
        if combined_confidence < 0.35:
            attribution = "likely_human"
            label = "This text appears to be human-written."
        elif combined_confidence > 0.65:
            attribution = "likely_ai"
            label = "This text appears to be AI-generated with high confidence."
        else:
            attribution = "uncertain"
            label = "We're uncertain whether this text is human-written or AI-generated. The creator has been notified."
        return {
            "combined_confidence": combined_confidence, 
            "attribution": attribution,
            "label": label,
            "reasoning": {
                "llm_reasoning": llm_reasoning
            }
        }
    except Exception as e:
        print(f"Error in combine_signals: {e}")
        return {
            "combined_confidence": 0.0,
            "attribution": "uncertain",
            "label": "Error",
            "reasoning": {
                "llm_reasoning": "Error occurred while combining signals."
            }
        }
