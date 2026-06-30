"""
Configuration for Provenance Guard system.
Centralized settings for model, scoring, rate limiting, and server behavior.
"""

# LLM Configuration
LLM_MODEL = "llama-3.1-8b-instant"
LLM_TEMPERATURE = 0.8

# Confidence Scoring Thresholds
SCORE_THRESHOLD_LOW = 0.35   # Below this = human-written
SCORE_THRESHOLD_HIGH = 0.65  # Above this = AI-generated
# Between 0.35-0.65 = uncertain

# Stylometric Signal Configuration
STYLOMETRIC_MAX_VARIANCE = 100  # Used for variance normalization

# Rate Limiting Configuration
RATE_LIMITS = {
    "submit": "10 per minute; 100 per day",
    "log": "20 per minute; 200 per day",
    "appeal": "10 per minute; 100 per day"
}

# Server Configuration
PORT = 5000
DEBUG = True
