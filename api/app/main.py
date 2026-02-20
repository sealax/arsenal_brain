from dotenv import load_dotenv
import os

load_dotenv()

from fastapi import FastAPI, HTTPException
from app.db import get_conn
from openai import OpenAI

app = FastAPI(title="Arsenal Brain API")

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/documents/{document_id}/chunks")
def get_chunks(document_id: int, q: str | None = None):
    with get_conn() as conn:
        with conn.cursor() as cur:
            if q:
                cur.execute(
                    """
                    SELECT id, content
                    FROM chunks
                    WHERE document_id = %s AND content ILIKE %s
                    ORDER BY id
                    """,
                    (document_id, f"%{q}%"),
                )
            else:
                cur.execute(
                    """
                    SELECT id, content
                    FROM chunks
                    WHERE document_id = %s
                    ORDER BY id
                    """,
                    (document_id,),
                )
            rows = cur.fetchall()

    # return a friendlier shape than raw tuples
    return {
        "document_id": document_id,
        "q": q,
        "count": len(rows),
        "chunks": [{"id": r[0], "content": r[1]} for r in rows],
    }

@app.get("/documents/{document_id}/search")
def search(document_id: int, q: str, k: int = 5):
    if not client.api_key:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY not set")

    emb = client.embeddings.create(
        model="text-embedding-3-small",
        input=q,
    ).data[0].embedding

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, content, (embedding <-> %s::vector) AS distance
                FROM chunks
                WHERE document_id = %s AND embedding IS NOT NULL
                ORDER BY embedding <-> %s::vector
                LIMIT %s
                """,
                (emb, document_id, emb, k),
            )
            rows = cur.fetchall()

    return {
        "document_id": document_id,
        "q": q,
        "k": k,
        "results": [
            {"id": r[0], "content": r[1], "distance": float(r[2])}
            for r in rows
        ],
    }

from pydantic import BaseModel
from typing import List, Dict, Any

class AskRequest(BaseModel):
    document_id: int
    question: str
    k: int = 5

class AskResponse(BaseModel):
    document_id: int
    question: str
    answer: str
    sources: List[Dict[str, Any]]

@app.post("/ask", response_model=AskResponse)
def ask(req: AskRequest):
    # 1) embed the question
    emb_model = os.environ.get("OPENAI_EMBED_MODEL", "text-embedding-3-small")
    q_emb = client.embeddings.create(model=emb_model, input=req.question).data[0].embedding

    # 2) vector search in DB (ASSUMES table `chunks` with columns: id, document_id, content, embedding (pgvector))
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, content, (embedding <-> %s::vector) AS distance
                FROM chunks
                WHERE document_id = %s
                ORDER BY embedding <-> %s::vector
                LIMIT %s
                """,
                (q_emb, req.document_id, q_emb, req.k),
            )
            rows = cur.fetchall()

    sources = [{"id": r[0], "content": r[1], "distance": float(r[2])} for r in rows]
    context = "\n\n---\n\n".join([s["content"] for s in sources])

    # 3) ask the chat model using retrieved context
    chat_model = os.environ.get("OPENAI_CHAT_MODEL", "gpt-4o-mini")
    msg = [
        {"role": "system", "content": "You are Arsenal Brain. Answer using ONLY the provided context. If the answer isn't in the context, say you don't know."},
        {"role": "user", "content": f"QUESTION:\n{req.question}\n\nCONTEXT:\n{context}"},
    ]
    completion = client.chat.completions.create(model=chat_model, messages=msg)
    answer = completion.choices[0].message.content.strip()

    return AskResponse(
        document_id=req.document_id,
        question=req.question,
        answer=answer,
        sources=sources,
    )