import os
import shutil
from pathlib import Path

from dotenv import load_dotenv
from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma

load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env")

TXT_DIR = "rag_docs"
CHROMA_DIR = "chroma_db"


def main():
    if os.path.exists(CHROMA_DIR):
        shutil.rmtree(CHROMA_DIR)
        print(f"Removed existing {CHROMA_DIR}/")

    loader = DirectoryLoader(TXT_DIR, glob="*.txt", loader_cls=TextLoader)
    docs = loader.load()
    print(f"Loaded {len(docs)} document(s) from {TXT_DIR}/")

    splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    chunks = splitter.split_documents(docs)
    print(f"Created {len(chunks)} chunk(s)")

    embeddings = OpenAIEmbeddings(model="text-embedding-ada-002")

    Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory=CHROMA_DIR,
    )

    print("RAG DATABASE READY")


if __name__ == "__main__":
    main()
