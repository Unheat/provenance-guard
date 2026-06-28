from dotenv import load_dotenv
import os
from groq import Groq
import json
load_dotenv()

# for stat score
import statistics
import nltk
nltk.download("punkt")
client = Groq(api_key=os.getenv("GROQ_API_KEY"))
SYSTEM_PROMPT = """
    You are a AI-text-detection analyser. 
    You should give high score if you think user's text is AI-generated, and low score for human-write text 
    You also need to provide reasoning for your score provide which AI characteristics you found in user's text contain 
    or human characteristics you found in this text to clarify for your score.
    Return a JSON object with:
    - llm_score: 0.0-1.0 confidence that text is AI-generated, you must just give a float number here
    - reasoning: one sentence explanation"
    example output: {"llm_score": 0.85, "reasoning": "The text has a high degree of repetitiveness and lacks personal anecdotes, which are common in AI-generated content."}
    """
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
            model="llama3-8b-8192",
            temperature=0.8
        )
        content_str = response.choices[0].message.content
        
        # 1. Type guard: explicit check to eliminate 'None' from the type union
        if content_str is None:
            return {"llm_score": 0.0, "reasoning": "Error: Received empty response from LLM."}
        
        # 2. Pylance now knows content_str is strictly 'str'
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
        
        max_variance = 100  # Adjust based on empirical data or domain knowledge
        # Normalize metrics to 0-1 range
        normalized_variance = 1 - (variance / max_variance)  # Invert: low variance = high AI score
        normalized_ttr = 1 - ttr                              # Invert: low TTR = high AI score
        normalized_density = punctuation_density           # Keep as-is? Or adjust?

        
        Score = (normalized_variance + normalized_ttr + normalized_density) / 3
        return Score
    except Exception as e:  
        print(f"Error in get_stylometric_score: {e}")
        return 0.5  # Neutral score in case of error    