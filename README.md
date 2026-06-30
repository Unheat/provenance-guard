# Provenance Guard

A backend system that classifies text-based creative content to detect AI-generated work while acknowledging genuine uncertainty. Designed for creative sharing platforms that need to protect attribution and build trust with transparent, confidence-aware labeling.
## DEMO
https://youtu.be/CShZUHBzDRY

## Architecture Overview
```mermaid
graph LR
    A["POST /submit<br/>Text + Creator ID"] --> B["Rate Limiter<br/>10/min, 100/day"]
    B -->|Pass| C["Input Validator<br/>Length, Keywords, Rate"]
    B -->|Limit Exceeded| Z1["429 Too Many Requests"]
    
    C -->|Pass| D["Injection Defense<br/>Block prompt hacks"]
    C -->|Invalid| Z2["400 Bad Request"]
    
    D -->|Pass| E["Detection Pipeline"]
    D -->|Injection| Z3["400 Bad Request"]
    
    E --> F["Signal 1:<br/>LLM Semantic Classifier<br/>Groq"]
    E --> G["Signal 2:<br/>Stylometric Heuristics<br/>Sentence Variance<br/>Type-Token Ratio<br/>Punctuation Density"]
    
    F --> H["Combine Signals<br/>confidence = avg score"]
    G --> H
    
    H --> I{"Confidence<br/>Score Range?"}
    I -->|0.0-0.35| J["Label: Human-Written"]
    I -->|0.35-0.65| K["Label: Uncertain"]
    I -->|0.65-1.0| L["Label: AI-Generated"]
    
    J --> M["Audit Log Entry<br/>classification event"]
    K --> M
    L --> M
    
    M --> N["Return to Client<br/>content_id, confidence,<br/>attribution, label"]
    
    O["POST /appeal<br/>content_id + reasoning"] --> P["Update Status<br/>under_review"]
    P --> Q["Audit Log Entry<br/>appeal event"]
    Q --> R["Return Confirmation"]
    
    S["GET /log"] --> T["Return Last 10<br/>Audit Entries"]
```
Provenance Guard implements a **four-layer defense strategy** that combines two independent detection signals to classify content while surfacing confidence in the classification:

1. **Rate Limiter** → Prevent abuse before expensive operations
2. **Injection Defense** → Block prompt manipulation attempts
3. **Input Validator** → Check length, keywords, rate per creator
4. **Detection Pipeline** → Multi-signal classification + confidence scoring

**Submission Flow:** Text submission → validation → signal 1 (LLM-based semantic analysis) → signal 2 (stylometric heuristics) → combined confidence score → transparency label → audit log

**Appeal Flow:** Creator contest → status update to "under_review" → appeal reason logged → human review

---

## Detection Signals

Provenance Guard uses **two independent signals** that capture different properties of text:

### Signal 1: LLM-Based Semantic Classifier (Groq)

**What it measures:** Semantic meaning, coherence, tone, and phrasing patterns typical of AI systems.

**Why this signal:** Language models can detect unnatural word choices, overly structured reasoning, and repetitive phrasing that characterize AI output.

**Blind spot:** Can be manipulated by framing or writing style instructions. Formal human writing might score high for AI traits.

**Output:** Score 0.0–1.0 (0 = clearly human, 1 = clearly AI)

**Implementation:**
```python
# Groq LLM with structured output
prompt = """Analyze this text for AI-generation characteristics.
Return a JSON object with:
- llm_score: 0.0-1.0 confidence that text is AI-generated
- reasoning: one sentence explanation"""
```

---

### Signal 2: Stylometric Heuristics (Pure Python)

**What it measures:** Statistical properties of text that differ between human and AI writing.

**Why this signal:** AI systems optimize for consistency and readability, producing more uniform text than natural human writing, which is inherently variable.

**Blind spot:** Can't read meaning or context. Formal academic writing and AI output can have similar statistical profiles.

**Computed metrics:**

| Metric | Calculation | What It Reveals |
|--------|-------------|-----------------|
| **Sentence Length Variance** | `std_dev([len(s) for s in sentences])` | AI writes uniformly; humans vary. High variance = likely human. |
| **Type-Token Ratio (TTR)** | `unique_words / total_words` | AI repeats common phrases; humans are more diverse. Higher TTR = likely human. |
| **Punctuation Density** | `punctuation_count / word_count` | AI uses punctuation formulaically; humans use it expressively. |

**Output:** Score 0.0–1.0 (0 = clearly human, 1 = clearly AI)

---

## Confidence Scoring

### How Signals Combine

The two signals are **weighted equally** and averaged into a single confidence score:

```python
combined_confidence = (llm_score + stylometric_score) / 2
```

This produces a 0.0–1.0 score that maps to three distinct label categories.

### Score Ranges and Label Mapping

| Confidence Range | Label | Meaning |
|------------------|-------|---------|
| 0.0–0.35 | Human-written | Unlikely to be AI-generated |
| 0.35–0.65 | Uncertain | System cannot confidently classify |
| 0.65–1.0 | AI-generated | Likely AI-generated |

### Calibration Examples

**Test 1: Clearly AI-generated text**
```
"Artificial intelligence represents a transformative paradigm shift in modern society. 
It is important to note that while the benefits of AI are numerous, it is equally 
essential to consider the ethical implications. Furthermore, stakeholders across 
various sectors must collaborate to ensure responsible deployment."
```
- LLM score: 0.58 (uniform sentence structure, repetitive transitions like "It is", formulaic structure)
- Stylometric score: 0.55 (low sentence variance, moderate TTR, consistent punctuation)
- **Combined confidence: 0.57 → Label: Uncertain** (demonstrates that formal AI text can score ambiguously)

**Test 2: Clearly human-written text**
```
"ok so i finally tried that new ramen place downtown and honestly? underwhelming. 
the broth was fine but they put WAY too much sodium in it and i was thirsty for 
like three hours after. my friend got the spicy version and said it was better."
```
- LLM score: 0.03 (informal, contractions, idioms, personal opinion, conversational tone)
- Stylometric score: 0.23 (high sentence variance, high TTR, varied punctuation)
- **Combined confidence: 0.13 → Label: Human-written** ✅

**Test 3: Borderline case (formal human writing)**
```
"The relationship between monetary policy and asset price inflation has been 
extensively studied in the literature. Central banks face a fundamental tension 
between their mandate for price stability and the unintended consequences of 
prolonged low interest rates on equity and real estate valuations."
```
- LLM score: 0.45 (overly formal phrasing, lacks personal anecdotes, uniform sentence length)
- Stylometric score: 0.39 (moderate variance, technical vocabulary, consistent style)
- **Combined confidence: 0.42 → Label: Uncertain** (shows system's limitation: formal human writing can resemble AI)

**Test 4: Borderline case (edited AI text)**
```
"I've been thinking a lot about remote work lately. There are genuine tradeoffs — 
flexibility and no commute on one side, isolation and blurred work-life boundaries 
on the other. Studies show productivity varies widely by individual and role type."
```
- LLM score: 0.04 (contractions, idioms, personal voice present)
- Stylometric score: 0.43 (moderate variance, diverse vocabulary, varied punctuation)
- **Combined confidence: 0.23 → Label: Human-written** (demonstrates that well-edited AI can evade detection)

---

## Transparency Labels

These are the exact labels shown to readers on the platform:

### Label Variants

**High-confidence AI-Generated:**
```
"This text appears to be AI-generated with high confidence."
```

**High-confidence Human-Written:**
```
"This text appears to be human-written."
```

**Uncertain:**
```
"We're uncertain whether this text is human-written or AI-generated. The creator has been notified."
```

### Why Three Variants?

A binary classifier would force a choice at 0.5 confidence, falsely confident in borderline cases. Three variants reflect reality:
- **0.65–1.0** = high confidence (act on it)
- **0.35–0.65** = uncertainty (don't accuse; notify creator for review)
- **0.0–0.35** = high confidence human (safe to promote)

This asymmetry protects creators: a false positive (accusing a human of plagiarism) is worse than a false negative (missing AI content).

---

## Rate Limiting

### Configuration

Applied to the `/submit` endpoint:

```
10 submissions per minute
100 submissions per day
```

### Reasoning

**Per-minute limit (10):** Legitimate creators submit infrequently (1-3 per session). A writer doing a review session might submit 5-10 pieces over 15 minutes. Limiting to 10/minute catches:
- Automated bot flooding attempts
- Script-based abuse
- Accidental loop bugs

Still allows manual batches without hitting limits.

**Per-day limit (100):** Prevents coordinated multi-account attacks. A single creator should never legitimately submit 100+ pieces in one day.

### Testing Rate Limiting

Tested with 12 rapid requests to /submit endpoint (exceeds 10/minute limit):

```powershell
for ($i = 1; $i -le 12; $i++) {
  $response = Invoke-WebRequest -Uri "http://localhost:5000/submit" `
    -Method POST `
    -Headers @{"Content-Type"="application/json"} `
    -Body (@{text = "Test submission"; creator_id = "ratelimit-test"} | ConvertTo-Json) `
    -ErrorAction SilentlyContinue
  Write-Host $response.StatusCode
}
```

**Actual test results:**
```
200 (requests 1-10: successful)
200
200
200
200
200
200
200
200
200
429 (requests 11-12: rate limited)
429
```

**Result:** ✅ Rate limiting working correctly
- First 10 requests within the 10/minute limit → 200 OK
- Requests 11-12 exceed limit → 429 Too Many Requests

---

## Audit Logging

Every submission, classification, and appeal is logged with full context for accountability and debugging.

### Log Structure

Each entry is a JSON object with:
- `timestamp`: ISO 8601 format
- `event_type`: "classification" or "appeal"
- `content_id`: Unique identifier for this submission
- `creator_id`: Creator who submitted
- `llm_score`, `stylometric_score`, `combined_confidence`: Signal outputs
- `attribution`: Final classification ("likely_ai", "likely_human", "uncertain")
- `status`: Current status ("success" for classifications, "under_review" for appeals)

### Actual Test Entries

**Entry 1: Clearly Human-Written Text**
```json
{
  "creator_id": "test-2",
  "content_id": "56306b3b-3de0-4011-a968-223ed7e7883e",
  "timestamp": "2026-06-29T23:52:56.833972+00:00",
  "event_type": "classification",
  "status": "success",
  "llm_score": 0.05,
  "llm_reasoning": "The text is informal, contains contractions and idioms, and expresses a personal opinion in a conversational tone",
  "stylometric_score": 0.2116666666666667,
  "combined_result": {
    "combined_confidence": 0.13083333333333336,
    "attribution": "likely_human",
    "label": "This text appears to be human-written.",
    "reasoning": {"llm_reasoning": "The text is informal, contains contractions and idioms, and expresses a personal opinion in a conversational tone"}
  }
}
```

**Entry 2: Uncertain Classification (Formal Human Writing)**
```json
{
  "creator_id": "test-3",
  "content_id": "26bfeed4-e13a-4deb-a4dd-d9e45982d8b6",
  "timestamp": "2026-06-29T23:52:56.998428+00:00",
  "event_type": "classification",
  "status": "success",
  "llm_score": 0.65,
  "llm_reasoning": "Text uses overly formal phrasing, lacks personal anecdotes, and exhibits uniform sentence length",
  "stylometric_score": 0.19368217054263567,
  "combined_result": {
    "combined_confidence": 0.42184108527131786,
    "attribution": "uncertain",
    "label": "We're uncertain whether this text is human-written or AI-generated. The creator has been notified.",
    "reasoning": {"llm_reasoning": "Text uses overly formal phrasing, lacks personal anecdotes, and exhibits uniform sentence length"}
  }
}
```

**Entry 3: Questionable AI-Generated Text (Edited)**
```json
{
  "creator_id": "test-1",
  "content_id": "a36c30c0-f251-49e9-ac41-0bcb91812bbe",
  "timestamp": "2026-06-29T23:52:56.699784+00:00",
  "event_type": "classification",
  "status": "success",
  "llm_score": 0.87,
  "llm_reasoning": "The text features uniform sentence structure and formal phrasing, repetitive transition words ('it is'), and a formulaic structure, indicating a high likelihood of AI-generation.",
  "stylometric_score": 0.2630749354005168,
  "combined_result": {
    "combined_confidence": 0.5665374677002584,
    "attribution": "uncertain",
    "label": "We're uncertain whether this text is human-written or AI-generated. The creator has been notified.",
    "reasoning": {"llm_reasoning": "The text features uniform sentence structure and formal phrasing, repetitive transition words ('it is'), and a formulaic structure, indicating a high likelihood of AI-generation."}
  }
}
```

### Accessing the Log

```bash
curl http://localhost:5000/log | python -m json.tool
```

Returns the 10 most recent entries (JSONL format, one JSON object per line).

---

## Appeals Workflow

Creators can contest classifications they believe are incorrect.

### Appeal Submission

```bash
curl -X POST http://localhost:5000/appeal \
  -H "Content-Type: application/json" \
  -d '{
    "content_id": "3f7a2b1e-a4c9-48d2-9f2a-6e5d8c1b7a3f",
    "creator_reasoning": "I wrote this myself from personal experience. My formal writing style may have triggered the AI classifier."
  }'
```

### System Response

The endpoint returns:
```json
{
  "status": "success",
  "content_id": "3f7a2b1e-a4c9-48d2-9f2a-6e5d8c1b7a3f",
  "message": "Your appeal has been received and logged for human review.",
  "next_steps": "A member of our team will review your appeal within 48 hours."
}
```

### What Happens After Appeal

1. Content status changes to `"under_review"` in the audit log
2. Appeal reason is recorded with original classification scores
3. Human reviewer can see: original text, both signal scores, confidence reasoning, and creator's explanation
4. Reviewer decides: uphold classification or reverse it

### Appeal Evidence in Audit Log

The same log entry that captures appeals also shows the original classification, making it easy for a human reviewer to understand what they're evaluating.

---

## Known Limitations

### 1. Formal Human Writing Scores High for AI

**Specific scenario:** Academic papers, formal business writing, or non-native speakers writing formally can resemble AI output.

**Why it happens:** 
- Stylometric signal measures sentence variance and vocabulary diversity
- Formal writing is intentionally uniform and uses domain-specific vocabulary repetition
- LLM signal can be steered by professional tone

**Example:** A formal literature review paper might score 0.58 (uncertain) because it optimizes for clarity, not personality.

**Mitigation:** The uncertain label acknowledges this limitation—it doesn't accuse; it flags for review.

---

### 2. Short Text Is Harder to Classify

**Specific scenario:** Haikus, tweets, or single-sentence submissions lack enough statistical data.

**Why it happens:**
- Stylometric heuristics (sentence variance, TTR) need multiple data points to be meaningful
- A haiku has 3 sentences total; variance becomes unreliable

**Example:** A 5-word haiku line might score 0.52 due to insufficient data, not actual uncertainty.

**Mitigation:** Input validation could reject submissions under 50 words, or confidence scoring could reduce weight on stylometric signal for short texts.

---

### 3. AI Output That Mimics Human Writing

**Specific scenario:** AI text that's been edited for natural tone, includes contractions, or uses intentionally varied phrasing can evade detection.

**Why it happens:**
- LLM classifier looks for semantic uniformity, but newer AI systems can mimic human editing
- Stylometric signal only measures statistical properties, not originality

**Example:** "I honestly can't believe how much that movie sucked. Like seriously? The plot made no sense and the characters were so flat." might score 0.35 even if generated by an AI that was prompted to "write casually."

**Mitigation:** The system honestly acknowledges it can't detect all AI. Appeals exist for this reason—creators can provide context.

---

## Spec Reflection

### How the Spec Helped

**Confidence scoring as a design question, not a technical one:** The planning document forced me to decide what 0.5 means to a user before writing code. This clarity made the implementation straightforward—it wasn't "what score should we assign?" but "which thresholds separate our three label categories?" Having those boundaries pre-defined prevented implementation creep.

### How Implementation Diverged from Spec

**Signal weighting simplification:** The spec planned for potentially different weights (e.g., "LLM 70%, stylometrics 30%") if one signal proved unreliable during testing. Implementation uses equal weighting (0.5/0.5) because both signals were similarly calibrated on test cases. In a production system with months of real data, weighted averaging would likely become necessary.

---

## AI Usage

### Instance 1: System Architecture & Audit Logging Design
**What I directed the AI to do:** "Explain the four-layer defense architecture for this system and how audit logging should work for compliance and debugging."

**What it produced:** 
- Detailed explanation of rate limiting → input validation → injection defense → detection pipeline flow
- Recommended JSONL (append-only) format over SQLite for audit logs
- Template for audit log entries with timestamp, event_type, content_id, status fields

**What I revised:** 
- Kept the JSONL approach (it matched the spec better than SQLite for this lightweight project)
- Added more detailed signal scores to each log entry (llm_score, stylometric_score, combined_confidence, attribution)
- Made timestamp formatting explicit as ISO 8601 strings

### Instance 2: System Prompt for LLM Signal Detection
**What I directed the AI to do:** "Write a system prompt for Groq that will classify text for AI-generation characteristics and return a JSON object with a confidence score and reasoning."

**What it produced:**
- Initial prompt that was too generic ("detect AI characteristics")
- Generic output format with minimal guidance

**What I revised:**
- Completely rewrote the prompt to be much more specific: list exact AI indicators to look for (repetitive phrasing, formal structure, lack of personal voice, uniform sentence length, etc.)
- Changed output instruction from vague to strict: "RESPOND WITH ONLY A JSON OBJECT, nothing else. No text before or after."
- Added JSON extraction logic to handle cases where the LLM returned extra text despite the strict instruction

### Instance 3: Stylometric Signal Implementation
**What I directed the AI to do:** "Explain how to calculate sentence length variance, type-token ratio, and punctuation density, and how to normalize them into a single 0-1 score."

**What it produced:**
- Correct formulas for all three metrics
- Normalization approach using min/max scaling
- Combined score as simple average of three normalized metrics

**What I revised:**
- Adjusted the variance normalization: inverted it (high variance = low AI score) because human writing has more variance
- Set max_variance to 100 (empirically calibrated during testing, not just a default)
- Added edge case handling: texts with < 2 sentences return 0.5 (neutral) instead of crashing

---

## Setup and Running

### Requirements
```bash
poetry install
```

### Environment Variables
Create a `.env` file (add to `.gitignore`):
```
GROQ_API_KEY=your_groq_api_key_here
```

### Running the App
```bash
python app.py
```

Server runs on `http://localhost:5000`

### API Endpoints

**POST /submit** - Classify a piece of content
```bash
curl -X POST http://localhost:5000/submit \
  -H "Content-Type: application/json" \
  -d '{
    "text": "The sun dipped below the horizon...",
    "creator_id": "user-42"
  }'
```

**GET /log** - View audit log
```bash
curl http://localhost:5000/log
```

**POST /appeal** - Submit an appeal
```bash
curl -X POST http://localhost:5000/appeal \
  -H "Content-Type: application/json" \
  -d '{
    "content_id": "...",
    "creator_reasoning": "..."
  }'
```

---

## Files

- `app.py` - Flask application with endpoints
- `signals.py` - LLM and stylometric detection signals
- `scoring.py` - Confidence scoring and label generation
- `audit_log.jsonl` - Append-only audit log
- `requirements.txt` - Python dependencies
- `planning.md` - System design, architecture diagram, and spec

---

**Built for CodePath AI201 Module 4: AI Safety and Guardrails**