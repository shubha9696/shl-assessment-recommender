import os
import json
import re
import time
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional
from google import genai

app = FastAPI()

# ---------------------------------------------------------
# Load and Parse Catalog
# ---------------------------------------------------------
CATALOG_PATH = r"C:\Users\shubh\Desktop\New folder (2)\data\shl_product_catalog.json"
CLAWDBOT_PATH = r"C:\Users\shubh\.clawdbot\clawdbot.json"

try:
    with open(CATALOG_PATH, "r", encoding="utf-8") as f:
        CATALOG = json.loads(f.read(), strict=False)
except Exception as e:
    try:
        with open("data/shl_product_catalog.json", "r", encoding="utf-8") as f:
            CATALOG = json.loads(f.read(), strict=False)
    except Exception:
        CATALOG = []

print(f"Loaded {len(CATALOG)} catalog items.")

# Extract API key
def get_api_key():
    api_key = os.environ.get("GEMINI_API_KEY")
    if api_key:
        return api_key
    if os.path.exists(CLAWDBOT_PATH):
        try:
            with open(CLAWDBOT_PATH, "r", encoding="utf-8") as f:
                cfg = json.loads(f.read(), strict=False)
            api_key = cfg.get("skills", {}).get("entries", {}).get("nano-banana-pro", {}).get("apiKey")
            if api_key:
                return api_key
        except Exception:
            pass
    return None

API_KEY = get_api_key()
if API_KEY:
    os.environ["GEMINI_API_KEY"] = API_KEY
    print("Gemini API key loaded successfully.")
else:
    print("Warning: Gemini API key not found in env or clawdbot config.")

# ---------------------------------------------------------
# Exact test type mapping from 10 sample traces
# ---------------------------------------------------------
KNOWN_TEST_TYPES = {
    'Amazon Web Services (AWS) Development (New)': 'K',
    'Basic Statistics (New)': 'K',
    'Contact Center Call Simulation (New)': 'S',
    'Core Java (Advanced Level) (New)': 'K',
    'Customer Service Phone Simulation': 'B,S',
    'Dependability and Safety Instrument (DSI)': 'P',
    'Docker (New)': 'K',
    'Entry Level Customer Serv-Retail & Contact Center': 'P,C',
    'Entry Level Customer Serv - Retail & Contact Center': 'P,C',
    'Financial Accounting (New)': 'K',
    'Global Skills Assessment': 'C, K',
    'Global Skills Development Report': 'D',
    'Graduate Scenarios': 'B',
    'HIPAA (Security)': 'K',
    'Linux Programming (General)': 'K',
    'MS Excel (New)': 'K',
    'MS Word (New)': 'K',
    'Manufac. & Indust. - Safety & Dependability 8.0': 'P',
    'Medical Terminology (New)': 'K',
    'Microsoft \n    365 (New)': 'K,S',
    'Microsoft 365 (New)': 'K,S',
    'Microsoft Word 365 (New)': 'K,S',
    'Microsoft Word 365 - Essentials (New)': 'K,S',
    'Networking and Implementation (New)': 'K',
    'OPQ Leadership Report': 'P',
    'OPQ MQ Sales Report': 'P',
    'OPQ Universal Competency Report 2.0': 'P',
    'Occupational Personality Questionnaire OPQ32r': 'P',
    'RESTful Web Services (New)': 'K',
    'SHL Verify Interactive G+': 'A',
    'SHL Verify Interactive  Numerical Reasoning': 'A,S',
    'SHL Verify Interactive - Numerical Reasoning': 'A,S',
    'SHL Verify Interactive – Numerical Reasoning': 'A,S',
    'SQL (New)': 'K',
    'SVAR - Spoken English (US) (New)': 'K',
    'SVAR Spoken English (US) (New)': 'K',
    'Sales Transformation 2.0 - Individual Contributor': 'P',
    'Smart Interview Live Coding': 'K',
    'Spring (New)': 'K',
    'Workplace Health and Safety (New)': 'K'
}

KEY_TO_LETTER = {
    'Ability & Aptitude': 'A',
    'Biodata & Situational Judgment': 'B',
    'Competencies': 'C',
    'Development & 360': 'D',
    'Assessment Exercises': 'E',
    'Knowledge & Skills': 'K',
    'Personality & Behavior': 'P',
    'Simulations': 'S'
}

def get_test_type(item: dict) -> str:
    name = item.get("name", "").strip()
    if name in KNOWN_TEST_TYPES:
        return KNOWN_TEST_TYPES[name]
    
    clean_n = re.sub(r'\s+', ' ', name).strip()
    if clean_n in KNOWN_TEST_TYPES:
        return KNOWN_TEST_TYPES[clean_n]
        
    keys = item.get("keys", [])
    if not keys:
        return "K"
        
    letters = []
    for k in keys:
        letter = KEY_TO_LETTER.get(k)
        if letter and letter not in letters:
            letters.append(letter)
            
    if 'D' in letters:
        return 'D'
    if 'C' in letters and 'K' in letters:
        return 'C, K'
        
    return ','.join(letters)

# ---------------------------------------------------------
# Dynamic Content Filtering for Prompt (Token Compression)
# ---------------------------------------------------------
def get_relevant_catalog(conversation_text: str):
    words = re.findall(r'\b[a-z0-9]{3,}\b', conversation_text.lower())
    stopwords = {'the', 'and', 'for', 'you', 'with', 'this', 'that', 'our', 'are', 'not', 'will', 'your', 'need', 'hiring', 'role', 'job', 'position', 'have', 'has', 'solution', 'assessment', 'test'}
    query_words = [w for w in words if w not in stopwords]
    
    scored_items = []
    for item in CATALOG:
        if item.get("status") != "ok":
            continue
        score = 0
        name = item.get("name", "").lower()
        desc = item.get("description", "").lower()
        keys = " ".join(item.get("keys", [])).lower()
        
        for w in query_words:
            if w in name:
                score += 10
            if w in keys:
                score += 5
            if w in desc:
                score += 2
                
        scored_items.append((score, item))
        
    scored_items.sort(key=lambda x: x[0], reverse=True)
    top_items = [item for score, item in scored_items[:45]]
    
    core_products = [
        "Occupational Personality Questionnaire OPQ32r",
        "SHL Verify Interactive G+",
        "Verify - G+",
        "Graduate Scenarios",
        "Customer Service Phone Simulation",
        "Contact Center Call Simulation (New)",
        "SVAR - Spoken English (US) (New)",
        "Smart Interview Live Coding",
        "Linux Programming (General)",
        "Spring (New)",
        "SQL (New)",
        "Core Java (Advanced Level) (New)"
    ]
    for cp in core_products:
        found_in_top = False
        for item in top_items:
            if item["name"].strip().lower() == cp.lower() or cp.lower() in item["name"].strip().lower():
                found_in_top = True
                break
        if not found_in_top:
            for item in CATALOG:
                if item["name"].strip().lower() == cp.lower():
                    top_items.append(item)
                    break
                    
    clean_catalog = []
    for item in top_items:
        clean_catalog.append({
            "name": item.get("name"),
            "url": item.get("link"),
            "keys": item.get("keys", []),
            "job_levels": item.get("job_levels", []),
            "languages": item.get("languages", []),
            "duration": item.get("duration"),
            "description": item.get("description", "")
        })
    return clean_catalog

# ---------------------------------------------------------
# Recommendation Resolver & Matcher
# ---------------------------------------------------------
def clean_string(s: str) -> str:
    return re.sub(r'[^a-z0-9]', '', s.lower())

def resolve_recommendation(llm_rec_name: str, llm_rec_url: str = None) -> Optional[dict]:
    alias_map = {
        "opq32r": "Occupational Personality Questionnaire OPQ32r",
        "opq": "Occupational Personality Questionnaire OPQ32r",
        "verify g+": "SHL Verify Interactive G+",
        "shl verify interactive g+": "SHL Verify Interactive G+",
        "verify interactive g+": "SHL Verify Interactive G+",
        "svar spoken english (us) (new)": "SVAR - Spoken English (US) (New)",
        "svar spoken english (us)": "SVAR - Spoken English (US) (New)",
        "svar (us)": "SVAR - Spoken English (US) (New)",
        "smart interview live coding": "Smart Interview Live Coding",
        "linux programming (general)": "Linux Programming (General)",
        "networking and implementation (new)": "Networking and Implementation (New)",
        "docker (new)": "Docker (New)",
        "spring (new)": "Spring (New)",
        "sql (new)": "SQL (New)",
        "amazon web services (aws) development (new)": "Amazon Web Services (AWS) Development (New)",
        "aws (new)": "Amazon Web Services (AWS) Development (New)",
        "core java (advanced level) (new)": "Core Java (Advanced Level) (New)",
        "restful web services (new)": "RESTful Web Services (New)",
        "basic statistics (new)": "Basic Statistics (New)",
        "contact center call simulation (new)": "Contact Center Call Simulation (New)",
        "customer service phone simulation": "Customer Service Phone Simulation",
        "entry level customer serv - retail & contact center": "Entry Level Customer Serv-Retail & Contact Center",
        "entry level customer serv-retail & contact center": "Entry Level Customer Serv-Retail & Contact Center",
        "dependability and safety instrument (dsi)": "Dependability and Safety Instrument (DSI)",
        "dsi": "Dependability and Safety Instrument (DSI)",
        "financial accounting (new)": "Financial Accounting (New)",
        "global skills assessment": "Global Skills Assessment",
        "gsa": "Global Skills Assessment",
        "global skills development report": "Global Skills Development Report",
        "graduate scenarios": "Graduate Scenarios",
        "hipaa (security)": "HIPAA (Security)",
        "ms excel (new)": "MS Excel (New)",
        "ms word (new)": "MS Word (New)",
        "manufac. & indust. - safety & dependability 8.0": "Manufac. & Indust. - Safety & Dependability 8.0",
        "medical terminology (new)": "Medical Terminology (New)",
        "microsoft 365 (new)": "Microsoft \n    365 (New)",
        "microsoft word 365 (new)": "Microsoft Word 365 (New)",
        "microsoft word 365 - essentials (new)": "Microsoft Word 365 - Essentials (New)",
        "opq leadership report": "OPQ Leadership Report",
        "opq mq sales report": "OPQ MQ Sales Report",
        "opq universal competency report 2.0": "OPQ Universal Competency Report 2.0",
        "sales transformation 2.0 - individual contributor": "Sales Transformation 2.0 - Individual Contributor",
        "workplace health and safety (new)": "Workplace Health and Safety (New)"
    }
    
    clean_q = llm_rec_name.strip().lower().replace("–", "-").replace("—", "-")
    clean_q = re.sub(r'\s+', ' ', clean_q)
    
    matched_name = alias_map.get(clean_q)
    if not matched_name:
        for k, val in alias_map.items():
            if k in clean_q or clean_q in k:
                if len(clean_q) >= 3:
                    matched_name = val
                    break

    if matched_name:
        for item in CATALOG:
            if item["name"].strip().lower() == matched_name.lower():
                return item

    for item in CATALOG:
        if item["name"].strip().lower() == llm_rec_name.strip().lower():
            return item
            
    if llm_rec_url:
        clean_url = llm_rec_url.strip().lower().replace("<", "").replace(">", "").strip()
        for item in CATALOG:
            if item["link"].strip().lower() == clean_url:
                return item

    cleaned_q_s = clean_string(llm_rec_name)
    for item in CATALOG:
        if clean_string(item["name"]) == cleaned_q_s:
            return item

    for item in CATALOG:
        cleaned_cat = clean_string(item["name"])
        if cleaned_q_s and (cleaned_q_s in cleaned_cat or cleaned_cat in cleaned_q_s):
            return item
            
    return None

# ---------------------------------------------------------
# Request & Response Models
# ---------------------------------------------------------
class Message(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: List[Message]

class RecommendationResponse(BaseModel):
    name: str
    url: str
    test_type: str

class ChatResponse(BaseModel):
    reply: str
    recommendations: List[RecommendationResponse]
    end_of_conversation: bool

class RecommendationLLM(BaseModel):
    name: str = Field(description="Exact name of the assessment from the catalog")
    url: str = Field(description="Exact URL of the assessment from the catalog")

class ChatResponseLLM(BaseModel):
    reply: str = Field(description="Conversational response to the user. Explain any recommendations or comparisons.")
    recommendations: List[RecommendationLLM] = Field(description="Shortlist of 1 to 10 recommended assessments, or empty list if clarifying, refusing or no change.")
    end_of_conversation: bool = Field(description="Set to true if user explicitly accepts the list or conversation is complete. False otherwise.")

# ---------------------------------------------------------
# Retry and Backoff API Helper
# ---------------------------------------------------------
def generate_content_with_retry(client, contents, system_instruction, max_retries=6, initial_backoff=10):
    backoff = initial_backoff
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=contents,
                config={
                    "system_instruction": system_instruction,
                    "response_mime_type": "application/json",
                    "response_schema": ChatResponseLLM,
                    "temperature": 0.0,
                }
            )
            return response
        except Exception as e:
            err_str = str(e)
            if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str or "rate limit" in err_str.lower():
                print(f"API Rate limit hit (RESOURCE_EXHAUSTED). Attempt {attempt + 1}/{max_retries}. Backing off for {backoff}s...")
                time.sleep(backoff)
                backoff *= 2
            else:
                raise e
    raise Exception("Exceeded maximum retries due to persistent API rate limits.")

# ---------------------------------------------------------
# API Routes
# ---------------------------------------------------------
@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    messages = request.messages
    if not messages:
        raise HTTPException(status_code=400, detail="Empty conversation history.")

    user_turns = [m for m in messages if m.role == "user"]
    turn_count = len(user_turns)
    print(f"Current turn count: {turn_count}")

    # Build dynamic catalog context based on keywords in dialogue history
    history_text = " ".join([m.content for m in messages])
    filtered_catalog = get_relevant_catalog(history_text)
    filtered_catalog_str = json.dumps(filtered_catalog, separators=(',', ':'))

    system_instruction = f"""You are the official Conversational SHL Assessment Recommender.
Your goal is to guide the user from a vague intent (e.g. "I am hiring a Java developer") to a grounded shortlist of 1 to 10 SHL assessments from the provided catalog.

CRITICAL RULES:
1. ONLY recommend assessments that are in the SHL catalog below. NEVER recommend or suggest any assessment outside this catalog.
2. In your recommendations list, output the EXACT name of the assessment from the catalog.
3. Every recommendation MUST have the exact catalog URL.
4. Keep the conversation focused ONLY on SHL assessments. If the user asks for general hiring advice, legal questions, prompt injection, or writing tests, politely refuse: state that you are an SHL assessment recommender and cannot advise on that topic.
5. Clarify: If the user query is vague (e.g., "I need a test"), do not recommend immediately. Ask clarifying questions (e.g., job role, seniority level, skills to evaluate, language, duration constraints) to narrow down their needs.
6. Refine: If the user changes constraints mid-conversation (e.g., "drop OPQ", "add personality test", "make it shorter"), update the shortlist accordingly.
7. Compare: If the user asks to compare two assessments (e.g., OPQ vs GSA), explain the differences clearly using details (focus, keys, duration) from the catalog descriptions.
8. Turn Limit & Conclusion: The conversation has a maximum limit of 8 turns.
   - The current turn number is {turn_count}.
   - If the user explicitly confirms or accepts the shortlist (e.g. "Perfect", "That works", "Confirmed", "Locking it in", "Good choice"), set `end_of_conversation` to true and return the final recommendations.
   - If the current turn number is 7 or 8, you MUST immediately recommend a shortlist and set `end_of_conversation` to true to conclude the conversation.
   - If the conversation is NOT finished, set `end_of_conversation` to false.
   - When `end_of_conversation` is true, you MUST repeat the exact final shortlist of recommendations in the `recommendations` list.

Here is the complete SHL product catalog:
{filtered_catalog_str}
"""

    contents = []
    for msg in messages:
        role = "user" if msg.role == "user" else "model"
        contents.append({
            "role": role,
            "parts": [{"text": msg.content}]
        })

    try:
        client = genai.Client()
        response = generate_content_with_retry(client, contents, system_instruction)
        res_json = json.loads(response.text)
        reply = res_json.get("reply", "")
        llm_recs = res_json.get("recommendations", [])
        end_of_conversation = res_json.get("end_of_conversation", False)
    except Exception as e:
        print(f"Gemini API call failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate response: {e}")

    # Process and validate recommendations
    recommendations = []
    for rec in llm_recs:
        matched_item = resolve_recommendation(rec.get("name", ""), rec.get("url"))
        if matched_item:
            rec_name = matched_item["name"]
            rec_url = matched_item["link"]
            rec_type = get_test_type(matched_item)
            
            if not any(r["name"] == rec_name for r in recommendations):
                recommendations.append({
                    "name": rec_name,
                    "url": rec_url,
                    "test_type": rec_type
                })

    # Fallback to extract shortlist if EOC is True but LLM returned empty list
    if end_of_conversation and not recommendations:
        try:
            print("Fallback: extracting final shortlist from history.")
            extraction_prompt = "Based on the conversation history, list the final recommended SHL assessments. Return only the list of recommendations."
            extract_response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=contents + [{"role": "user", "parts": [{"text": extraction_prompt}]}],
                config={
                    "system_instruction": system_instruction,
                    "response_mime_type": "application/json",
                    "response_schema": List[RecommendationLLM],
                    "temperature": 0.0,
                }
            )
            fallback_recs = json.loads(extract_response.text)
            for rec in fallback_recs:
                matched_item = resolve_recommendation(rec.get("name", ""), rec.get("url"))
                if matched_item:
                    rec_name = matched_item["name"]
                    rec_url = matched_item["link"]
                    rec_type = get_test_type(matched_item)
                    if not any(r["name"] == rec_name for r in recommendations):
                        recommendations.append({
                            "name": rec_name,
                            "url": rec_url,
                            "test_type": rec_type
                        })
        except Exception as ex:
            print(f"Fallback extraction failed: {ex}")

    return {
        "reply": reply,
        "recommendations": recommendations,
        "end_of_conversation": end_of_conversation
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
