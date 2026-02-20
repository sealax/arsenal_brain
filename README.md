# Arsenal Brain API

Arsenal Brain is a Retrieval-Augmented Generation (RAG) API built with FastAPI, PostgreSQL (pgvector), and OpenAI.

It allows you to:

- Store and embed Arsenal-related documents
- Perform semantic search over document chunks
- Ask natural language questions grounded in stored context
- Return answers with source attribution

---

## Architecture

- FastAPI – API layer
- PostgreSQL + pgvector – Vector storage and similarity search
- OpenAI – Embeddings + Chat completion
- python-dotenv – Environment variable management

---

## Setup

### 1. Clone the repo

```bash
git clone <your-repo-url>
cd arsenal_brain_project/api
```

### 2. Create virtual environment

```bash
python -m venv .venv
.venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

Create a `.env` file in the `api` directory:

```
OPENAI_API_KEY=your_key_here
OPENAI_EMBED_MODEL=text-embedding-3-small
OPENAI_CHAT_MODEL=gpt-4o-mini
```

---

## Run the API

```bash
uvicorn app.main:app --reload
```

Then open:

```
http://127.0.0.1:8000/docs
```

---

## Endpoints

### GET /health

Health check endpoint.

Response:

```json
{
  "status": "ok"
}
```

---

### GET /documents/{document_id}/chunks

Returns all stored chunks for a given document.

---

### GET /documents/{document_id}/search?q=your_query&k=5

Performs semantic similarity search using vector embeddings.

Query Parameters:
- `q` – search query
- `k` – number of results to return

---

### POST /ask

Retrieval-Augmented Generation endpoint.

Request:

```json
{
  "document_id": 1,
  "question": "What league does Arsenal compete in?",
  "k": 5
}
```

Response:

```json
{
  "document_id": 1,
  "question": "What league does Arsenal compete in?",
  "answer": "Arsenal competes in the Premier League...",
  "sources": [
    {
      "id": 1,
      "content": "...",
      "distance": 0.81
    }
  ]
}
```

The answer is generated using only retrieved context from the database.

---

## Current Capabilities

- Embedding ingestion
- Vector similarity search
- Retrieval-Augmented Generation
- Source attribution
- Basic hallucination guardrail

---

## Future Improvements

- Document ingestion endpoint
- Streaming responses
- Evaluation metrics
- Caching layer
- Authentication
- Docker containerisation