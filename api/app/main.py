from fastapi import FastAPI
from app.db import get_conn

app = FastAPI(title="Arsenal Brain API")


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
                    WHERE document_id = %s
                      AND content ILIKE %s
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

    return {
        "document_id": document_id,
        "q": q,
        "count": len(rows),
        "chunks": [{"id": r[0], "content": r[1]} for r in rows],
    }
