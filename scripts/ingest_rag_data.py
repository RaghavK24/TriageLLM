import sys
import os
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.rag import get_store

def main():
    store = get_store()
    if store.count() > 100:
        print("Collection already populated. Skipping.")
        sys.exit(0)

    texts = []
    metadatas = []

    print("Fetching arXiv abstracts...")
    categories = ["cs.AI", "cs.CL", "cs.LG"]
    for cat in categories:
        url = f"http://export.arxiv.org/api/query?search_query=cat:{cat}&max_results=300&sortBy=submittedDate&sortOrder=descending"
        try:
            response = urllib.request.urlopen(url, timeout=30)
            xml_data = response.read()
            root = ET.fromstring(xml_data)
            ns = "{http://www.w3.org/2005/Atom}"
            for entry in root.findall(f"{ns}entry"):
                title_el = entry.find(f"{ns}title")
                abstract_el = entry.find(f"{ns}summary")
                id_el = entry.find(f"{ns}id")
                
                if title_el is not None and abstract_el is not None and id_el is not None:
                    title = title_el.text.strip()
                    abstract = abstract_el.text.strip()
                    arxiv_id = id_el.text.strip()
                    text = f"Title: {title}\n\nAbstract: {abstract}"
                    texts.append(text)
                    metadatas.append({"source": "arxiv", "category": cat, "id": arxiv_id})
        except Exception as e:
            print(f"Failed to fetch arXiv category {cat}: {e}")

    try:
        from datasets import load_dataset
        print("Fetching HuggingFace dataset...")
        ds = load_dataset("rag-datasets/rag-mini-wikipedia", "text-corpus", split="passages")
        for row in ds.select(range(2000)):
            texts.append(row["passage"])
            metadatas.append({"source": "wikipedia", "id": str(row.get("id", ""))})
    except Exception as e:
        print(f"HuggingFace dataset unavailable: {e}. Continuing with arXiv only.")

    if not texts:
        print("No texts fetched to ingest. Exiting.")
        sys.exit(0)

    BATCH_SIZE = 100
    print(f"Ingesting {len(texts)} documents in batches of {BATCH_SIZE}...")
    for i in range(0, len(texts), BATCH_SIZE):
        batch_texts = texts[i:i+BATCH_SIZE]
        batch_metas = metadatas[i:i+BATCH_SIZE]
        store.ingest_texts(batch_texts, batch_metas)
        print(f"Ingested {min(i+BATCH_SIZE, len(texts))}/{len(texts)} documents")

    print(f"Done. Collection now has {store.count()} documents.")

if __name__ == "__main__":
    main()

