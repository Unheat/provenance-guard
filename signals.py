from dotenv import load_dotenv
import os
from groq import Groq
import json
from config import LLM_MODEL, LLM_TEMPERATURE, STYLOMETRIC_MAX_VARIANCE
load_dotenv()

# for stat score
import statistics
import nltk
nltk.download("punkt_tab")
client = Groq(api_key=os.getenv("GROQ_API_KEY"))
SYSTEM_PROMPT = """You are an AI-text-detection analyzer. Score text on AI-generation likelihood.

Look for these AI indicators (score higher if present):
- Repetitive phrasing or word choices (e.g., "It is important to note that")
- Overly formal or structured reasoning without personal voice
- Generic transitions and connecting phrases
- Lack of contractions, idioms, or conversational tone
- Absence of personal anecdotes or specific details
- Uniform sentence length and rhythm
- Over-explanation of obvious points
- Formulaic structure (intro→body→conclusion)

RESPOND WITH ONLY A JSON OBJECT, nothing else. No text before or after.

{"llm_score": 0.75, "reasoning": "The text uses repetitive formal phrases and lacks personal voice"}

Where llm_score is 0.0 (human) to 1.0 (AI)."""
def get_llm_score(text: str) -> dict: # return a json object with llm_score and reasoning
    """
    Ask Groq: does this text look AI-generated?
    
    Args:
        text: The text to analyze
    
    Returns:
        {
        "llm_score": float 0.0-1.0,
        "reasoning": str
        }
    """ 
    try:
        response = client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT
                },
                {
                    "role": "user",
                    "content": text
                }
            ],
            model=LLM_MODEL,
            temperature=LLM_TEMPERATURE
        )
        content_str = response.choices[0].message.content

        if content_str is None:
            return {"llm_score": 0.0, "reasoning": "Error: Received empty response from LLM."}

        # Try to extract JSON from the response (in case LLM adds extra text)
        content_str = content_str.strip()
        if content_str.startswith('{'):
            # Find the closing brace
            brace_count = 0
            for i, char in enumerate(content_str):
                if char == '{':
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        return json.loads(content_str[:i+1])

        # Fallback: try parsing the whole thing
        return json.loads(content_str)
        
    except Exception as e:
        print(f"Error in get_llm_score: {e}")
        return {"llm_score": 0.0, "reasoning": "Error occurred while processing the text."}
def get_stylometric_score(text: str) -> float:
    """
    Measure statistical properties that differ between human and AI writing.
    
    Args:
        text: The text to analyze
    
    Returns:
        {
        "stylometric_score": float 0.0-1.0
        0.0 = likely human, 1.0 = likely AI
        }
    """
    # Step 1: Split text into sentences
    # Step 2: Calculate sentence length variance
    # Step 3: Calculate type-token ratio (vocabulary diversity)
    # Step 4: Calculate punctuation density
    # Step 5: Combine the three metrics into one score
    # Step 6: Return the score
    try:
        sentences = nltk.tokenize.sent_tokenize(text)
        if not sentences:
            raise ValueError("Text must contain at least one sentence.")
        # Edge case: If there are fewer than 2 sentences, we cannot measure variance.
        # We default to 0.5 (neutral/inconclusive).
        if len(sentences) < 2:
            return 0.5
        len_list = [len(sentence.split()) for sentence in sentences]
        # metric 1 sentence length variance
        variance = statistics.variance(len_list)
        std_dev = statistics.stdev(len_list)
        
        # metric 2 type-token ratio unique_words / total_words
        words = text.lower().split()
        unique_words = len(set(words))
        ttr = unique_words / len(words) if len(words) > 0 else 0
        
        # Metric 3: Punctuation Density punctuation_marks / word_count
        punctuation = {'.', ',', ';', ':', '!', '?'}
        punctuation_marks = sum(1 for char in text if char in punctuation)
        punctuation_density = punctuation_marks / len(words) if len(words) > 0 else 0
        
        # Normalize metrics to 0-1 range
        normalized_variance = 1 - (variance / STYLOMETRIC_MAX_VARIANCE)  # Invert: low variance = high AI score
        normalized_ttr = 1 - ttr                              # Invert: low TTR = high AI score
        normalized_density = punctuation_density           # Keep as-is? Or adjust?

        
        Score = (normalized_variance + normalized_ttr + normalized_density) / 3
        return Score
    except Exception as e:  
        print(f"Error in get_stylometric_score: {e}")
        return 0.5  # Neutral score in case of error    