# Conversational SHL Assessment Recommender: Approach Document

## 1. Design Choices & Architecture
The system is built as a stateless, lightweight FastAPI service. It exposes two core endpoints: `/health` for system readiness and `/chat` for managing conversation history and recommendations. 

Key design choices include:
- **Statelessness**: Every request to `/chat` carries the complete message history. This allows horizontal scaling and eliminates session-persistence overhead.
- **Strict Schema Enforcement**: Utilizing Gemini’s **Structured Outputs** via Pydantic (`ChatResponseLLM`) ensures that the service's raw output strictly adheres to the requested JSON response format, avoiding any parser failures.
- **Python Matching & Resolution Layer**: Instead of relying solely on the LLM to format catalog URLs and test type strings (which is prone to slight variations and hallucinations), the LLM outputs only the catalog item name. A Python backend then resolves this name against the original catalog database using an alias mapping and fuzzy string search. It then constructs the final recommendation with the exact catalog URL and computes the `test_type` programmatically.

## 2. Retrieval Setup & Token Compression (Dynamic Context Filtering)
The full SHL product catalog contains 377 items. Including all items with full descriptions in the system prompt would result in ~73,000 input tokens per call. On free LLM tiers, this quickly triggers rate limits (e.g., TPM/RPM exhaustions) and increases response latency.

To address this, we implemented a **Dynamic Context Filtering** retrieval mechanism:
1. **Keyword Scoring**: When a `/chat` request is received, the Python service combines the conversation history text, tokenizes it, filters out stopwords, and scores the catalog items.
2. **Relevance Boosts**: Items matching search terms in their name get a high score boost (+10), key category match (+5), and description match (+2).
3. **Shortlist Injection**: The system prompt is dynamically populated with *only* the top 45 matching catalog items with their full details.
4. **Core Fallback**: A static set of core SHL assessments (e.g., *OPQ32r*, *Verify Interactive G+*, *Graduate Scenarios*, etc.) is always appended to ensure standard cognitive, personality, and simulation tests are available even if keyword match scores are low.
5. **Result**: This retrieval strategy compresses the input catalog context from ~73,000 tokens to under **7,000 tokens**, achieving a **90% reduction in token usage** while preserving recommendation accuracy.

## 3. Prompt Design & Guardrails
The system prompt enforces strict rules to govern the agent's behavior:
- **Scope Limits**: The agent is restricted to SHL assessment recommendations. Any queries requesting general hiring advice, legal compliance (e.g., NYC Law 144), or prompt injections are explicitly refused with a standard polite refusal template.
- **Turn-Limit Awareness**: The prompt detects the current turn count (calculated from history). If the conversation is on turn 7 or 8, the model is instructed to immediately propose a final shortlist and set `end_of_conversation` to `true` to conclude before the evaluator turn cap.
- **Resolution Safety**: A python-based fallback is implemented to extract the shortlist from the dialogue history if `end_of_conversation` is marked true but the model returned an empty recommendation block.

## 4. What Didn't Work (Lessons Learned)
- **Full Catalog Context**: Initially, passing all 377 catalog items directly in the system prompt worked for individual queries but hit severe `RESOURCE_EXHAUSTED` errors during rapid replay testing. This was resolved by implementing the Dynamic Context Filtering retrieval setup.
- **Raw LLM String Matches**: Letting the LLM output the exact URL and `test_type` resulted in minor string formatting errors (e.g., missing trailing slashes in URLs, or returning `"Ability & Aptitude"` instead of code `"A"`). Programmatic matching and key mapping in the Python layer completely resolved this.

## 5. Evaluation & Verification
An automated test suite (`test_app.py`) was created to replay the 10 public conversation traces against the local FastAPI endpoints. 
- **Rate-Limit Safeguards**: The test suite sleeps for `4.5` seconds between turns and `5.0` seconds between traces to remain strictly within the free tier rate limits (5 RPM / 15 RPM).
- **Recall Metric**: Evaluates system quality by comparing the final recommended list with the expected trace list using Recall@10, achieving high alignment across various candidate personas.
