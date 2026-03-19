# Multi-Agent Content Pipeline

> **4 AI agents. One pipeline. Professional content — completely free.**

**[Live Demo](https://haidaralishaik-multi-agent-content-pipeline-app-1eu8vl.streamlit.app/)**

Turn any topic into polished, fact-checked content — blog posts, LinkedIn articles, or Twitter threads — powered by **Groq (LLaMA 3.3 70B)** (free tier) and orchestrated with LangGraph.

---

## How It Works

```
Topic ──→ Researcher ──→ Writer ──→ Editor ──→ Fact-Checker ──→ Published Content
            │                │          │            │
        Gathers info    Crafts draft  Polishes    Verifies claims
        from web        with tone &   clarity,    & corrects
        (DuckDuckGo)    format        flow        inaccuracies
```

Each agent is backed by **Groq (LLaMA 3.3 70B)** (free tier), with its behavior defined entirely in **Markdown instruction files** — not hardcoded prompts.

---

## Key Features

| Feature | What It Does |
|---------|-------------|
| **Instruction-Based Agents** | Agent behavior lives in `.md` files — edit text, not code |
| **3 Content Formats** | Blog post, LinkedIn, Twitter/X threads |
| **4 Tone Options** | Professional, casual, technical, storytelling |
| **Smart Caching** | 24h content-addressed cache with cost savings tracking |
| **Input/Output Guardrails** | PII detection, prompt injection blocking, auto-redaction |
| **Quality Scoring** | LLM-as-judge evaluation with A-F grading |
| **Human-in-the-Loop** | Interactive mode — review and edit between stages |
| **Resilience** | Retry with exponential backoff + circuit breaker pattern |
| **Full Observability** | Trace IDs, event timeline, millisecond-level timing |
| **Streamlit UI** | 9-tab dashboard with real-time pipeline visualization |

---

## Quick Start

### Prerequisites

- Python 3.10+
- [Groq API key](https://console.groq.com/keys) (free, no credit card needed)

### Setup

```bash
# Clone the repo
git clone https://github.com/haidaralishaik/Multi-Agent-Content-Pipeline.git
cd Multi-Agent-Content-Pipeline

# Create and activate virtual environment
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS/Linux

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env and add your GROQ_API_KEY
```

### Run

**Web UI (recommended):**
```bash
.venv/Scripts/streamlit run app.py
# Opens at http://localhost:8501
```

**Command line:**
```python
from dotenv import load_dotenv; load_dotenv()
from src.pipeline import ContentPipeline

pipeline = ContentPipeline()
result = pipeline.run(
    topic="Recent advances in RAG systems",
    content_format="blog_post",
    tone="professional"
)
print(result['final'])
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│              STREAMLIT UI  (app.py)                      │
│     Automatic + Interactive modes │ 9 output tabs        │
└──────────────────────┬──────────────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────────────┐
│          PIPELINE ORCHESTRATION  (LangGraph)             │
│                                                          │
│  Input Guardrails ──→ Agent Chain ──→ Output Guardrails  │
│       (PII, injection)    │          (PII redaction)     │
│                           ▼                              │
│   ┌──────────┐  ┌──────────┐  ┌────────┐  ┌──────────┐ │
│   │Researcher│→ │  Writer  │→ │ Editor │→ │Fact-Check│ │
│   └──────────┘  └──────────┘  └────────┘  └──────────┘ │
│         │                                                │
│   Quality Evaluator  │  Cost Tracker  │  Pipeline Cache  │
└──────────────────────┬──────────────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────────────┐
│    INSTRUCTION LAYER  (Markdown files define behavior)   │
│    base_instructions.md + {role}_instructions.md         │
└──────────────────────┬──────────────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────────────┐
│    GROQ  (llama-3.3-70b-versatile, free tier)  │
│    Retry handler │ Circuit breaker │ Token tracking       │
└─────────────────────────────────────────────────────────┘
```

---

## Project Structure

```
multi-agent-content-pipeline/
│
├── instructions/                  # Agent behavior (the real "code")
│   ├── base_instructions.md
│   ├── researcher_instructions.md
│   ├── writer_instructions.md
│   ├── editor_instructions.md
│   └── fact_checker_instructions.md
│
├── src/                           # Core framework
│   ├── agent_core.py              #   Instruction-based agent engine
│   ├── bedrock_client.py          #   Groq LLM wrapper
│   ├── pipeline.py                #   4-agent LangGraph orchestration
│   ├── pipeline_interactive.py    #   Human-in-the-loop variant
│   ├── cache.py                   #   Content-addressed caching (24h TTL)
│   ├── guardrails.py              #   Input/output safety validation
│   ├── evaluator.py               #   LLM-as-judge quality scoring
│   ├── resilience.py              #   Retry handler & circuit breaker
│   └── tracing.py                 #   Pipeline observability & timing
│
├── tools/
│   ├── web_search.py              #   DuckDuckGo web search (free)
│   └── document_search.py
│
├── app.py                         # Streamlit web UI
├── requirements.txt
└── .env.example                   # Environment config template
```

---

## Configuration

```bash
# .env — only one key needed
GROQ_API_KEY=your_key_here
```

Get a free key at [console.groq.com/keys](https://console.groq.com/keys) — no credit card required.

---

## Content Formats & Tones

| Format | Length |
|--------|--------|
| Blog Post | 800-1500 words |
| LinkedIn | 300-500 words |
| Twitter/X Thread | 5-7 tweets |

| Tone | Style |
|------|-------|
| Professional | Authoritative, data-driven |
| Casual | Conversational, relatable |
| Technical | Deep-dive, precise |
| Storytelling | Narrative arc, analogies |

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **LLM** | Groq — LLaMA 3.3 70B (free tier) |
| **Orchestration** | LangGraph + LangChain |
| **Web Search** | DuckDuckGo (free, no API key) |
| **UI** | Streamlit |
| **Validation** | Pydantic |

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `GROQ_API_KEY not set` | Add your key to `.env` |
| `429 RESOURCE_EXHAUSTED` | Free tier rate limit — wait a minute and retry |
| `Model not found` | Check that `GROQ_MODEL` in `.env` matches a valid Groq model name |

---

## License

MIT License — use and modify freely.

---

**Built with Groq + LLaMA 3.3 70B + LangGraph + Streamlit**
