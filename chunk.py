# chunk.py
import json
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma

# Load data
with open("bg3_wiki_data.jsonl", "r", encoding="utf-8") as f:
    data = [json.loads(line) for line in f if "text" in line]

# Improved chunking
splitter = RecursiveCharacterTextSplitter(chunk_size=1500, chunk_overlap=300)
texts, metadatas = [], []

for item in data:
    chunks = splitter.split_text(item["text"])
    texts.extend(chunks)
    metadatas.extend([{ "url": item["url"], "title": item["title"] }] * len(chunks))

# Embeddings + Save
embedding = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
vectorstore = Chroma.from_texts(texts=texts, embedding=embedding, metadatas=metadatas, persist_directory="honormind_chroma")
print("✅ Chroma vectorstore saved.")
