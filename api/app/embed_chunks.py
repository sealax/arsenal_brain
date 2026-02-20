import os
from dotenv import load_dotenv
from openai import OpenAI

from app.db import get_conn

load_dotenv()

client = OpenAI()


def embed_text(text: str):
    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=text,
    )
    return response.data[0].embedding


def main():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, content
                FROM chunks
                WHERE embedding IS NULL
                """
            )
            rows = cur.fetchall()

            for chunk_id, content in rows:
                print(f"Embedding chunk {chunk_id}...")
                embedding = embed_text(content)

                cur.execute(
                    """
                    UPDATE chunks
                    SET embedding = %s
                    WHERE id = %s
                    """,
                    (embedding, chunk_id),
                )

        conn.commit()

    print("Done.")


if __name__ == "__main__":
    main()