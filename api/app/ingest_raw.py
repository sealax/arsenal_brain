from pathlib import Path
from app.db import get_conn

RAW_DIR = Path("../data/raw")


def split_text(text: str, max_chars: int = 800):
    return [text[i:i + max_chars] for i in range(0, len(text), max_chars)]


def ingest_file(path: Path):
    text = path.read_text(encoding="utf-8")

    with get_conn() as conn:
        with conn.cursor() as cur:
            # insert document
            cur.execute(
                """
                INSERT INTO documents (source, title)
                VALUES (%s, %s)
                RETURNING id
                """,
                ("local", path.name),
            )
            document_id = cur.fetchone()[0]

            # split + insert chunks
            chunks = split_text(text)

            for chunk in chunks:
                cur.execute(
                    """
                    INSERT INTO chunks (document_id, content)
                    VALUES (%s, %s)
                    """,
                    (document_id, chunk),
                )

        conn.commit()

    print(f"Ingested {path.name} with {len(chunks)} chunks")


def main():
    for path in RAW_DIR.glob("*.txt"):
        ingest_file(path)


if __name__ == "__main__":
    main()
