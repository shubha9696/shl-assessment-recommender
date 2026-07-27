# Conversational SHL Assessment Recommender

A lightweight, stateless FastAPI backend designed to recommend SHL assessments based on candidate roles, seniorities, tech stacks, and language preferences. It utilizes the Gemini API with dynamic context filtering and structured outputs to ensure highly accurate recommendations.

## ✨ Core Features
- **Stateless FastAPI Service:** Built to accept full chat history on every request, allowing easy scaling and elimination of session persistence overhead.
- **Dynamic Context Filtering:** Compresses a large 377-item product catalog from ~73,000 tokens to under 7,000 tokens (a 90% reduction) using keyword scoring and relevance boosts before querying the LLM.
- **Strict Schema Enforcement:** Leverages Gemini Structured Outputs via Pydantic model (`ChatResponseLLM`) to guarantee reliable and structured JSON payloads.
- **Python Matching & Resolution Layer:** Converts LLM-selected candidate names into correct product catalog URLs and shorthand test types programmatically to avoid AI hallucinations.
- **Prompt Guardrails:** Restricts the conversation scope to SHL assessments, rejects prompt injections, and handles conversational timeout warnings on late turns.

## 🛠️ Tech Stack
- **Framework:** FastAPI / Python 3.10+
- **LLM SDK:** `google-genai` (Google Gemini API)
- **Data Index:** `data/shl_product_catalog.json`

## 📦 Getting Started

### Prerequisites
- Python 3.10 or higher
- A Gemini API key (set as environment variable `GEMINI_API_KEY`)

### Installation & Run
1. Clone the repository:
   ```bash
   git clone https://github.com/shubha9696/shl-assessment-recommender.git
   cd shl-assessment-recommender
   ```
2. Create a virtual environment and install dependencies:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: .\venv\Scripts\activate
   pip install -r requirements.txt
   ```
3. Run the development server:
   ```bash
   uvicorn app:app --reload
   ```
4. Open your browser and navigate to `http://127.0.0.1:8000/docs` to view the API documentation.
