from pathlib import Path

from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma

load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env")

CHROMA_DIR = "chroma_db"

QUERIES = [
    "What documents do I need for a Germany work visa",
    "UK skilled worker visa requirements passport",
    "Best neighbourhoods for expat families in Berlin",
]


def main():
    embeddings = OpenAIEmbeddings(model="text-embedding-ada-002")
    db = Chroma(persist_directory=CHROMA_DIR, embedding_function=embeddings)

    for query in QUERIES:
        print(f"Query: {query}")
        results = db.similarity_search(query, k=2)
        for i, doc in enumerate(results, 1):
            print(f"  Result {i}: {doc.page_content}")
            print("  ---")
        print()

    print("RAG TEST COMPLETE")


if __name__ == "__main__":
    main()
