from fastapi import FastAPI, HTTPException
from app.db import get_conn
import os
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