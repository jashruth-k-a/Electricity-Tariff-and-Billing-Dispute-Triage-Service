import hashlib
import json
import math
import re
import time
from collections import Counter
from functools import lru_cache
from pathlib import Path

import chromadb
from langchain_core.embeddings import Embeddings
from langchain_core.runnables import RunnableLambda
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pypdf import PdfReader

from triage.config import settings
from triage.storage import redis_client


def words(text):
    return re.findall(r"[a-z0-9]+", text.lower())


class HashEmbeddings(Embeddings):
    """Offline, deterministic lexical vectors. Only for synthetic smoke tests."""
    def embed_documents(self, texts):
        vectors = []
        for text in texts:
            vector = [0.] * 384
            for token, count in Counter(words(text)).items():
                digest = hashlib.sha256(token.encode()).digest()
                vector[int.from_bytes(digest[:4], "big") % 384] += count
            norm = math.sqrt(sum(v * v for v in vector)) or 1
            vectors.append([v / norm for v in vector])
        return vectors

    def embed_query(self, text):
        return self.embed_documents([text])[0]


class LocalEmbeddings(Embeddings):
    def __init__(self):
        from sentence_transformers import SentenceTransformer
        cfg = settings()
        self.model = SentenceTransformer(cfg.embedding_model, revision=cfg.embedding_revision or None)

    def embed_documents(self, texts):
        return self.model.encode(texts, normalize_embeddings=True).tolist()

    def embed_query(self, text):
        return self.embed_documents([text])[0]


class OllamaEmbeddings(Embeddings):
    """Semantic embeddings from the local container; no paid embedding API."""
    def _embed(self, texts, prefix):
        import httpx
        cfg = settings()
        response = httpx.post(cfg.embedding_base_url.rstrip("/") + "/embeddings",
                              json={"model": cfg.embedding_model,
                                    "input": [(prefix.strip() + " " if prefix.strip() else "") + text for text in texts]},
                              timeout=cfg.call_timeout_seconds)
        response.raise_for_status()
        data = response.json()["data"]
        return [row["embedding"] for row in sorted(data, key=lambda row: row["index"])]

    def embed_documents(self, texts):
        return self._embed(texts, settings().embedding_document_prefix)

    def embed_query(self, text):
        return self._embed([text], settings().embedding_query_prefix)[0]


@lru_cache
def embedder():
    backend = settings().embedding_backend
    if backend == "sentence-transformers":
        return LocalEmbeddings()
    if backend == "ollama":
        return OllamaEmbeddings()
    if backend != "hash":
        raise ValueError("Unknown embedding backend")
    return HashEmbeddings()


@lru_cache
def chroma():
    from triage.chroma_http import install_timeout
    install_timeout()
    cfg = settings()
    return chromadb.HttpClient(host=cfg.chroma_host, port=cfg.chroma_port,
                              settings=chromadb.Settings(anonymized_telemetry=False))


def manifest():
    return json.loads(Path(settings().corpus_manifest).read_text(encoding="utf-8"))


def fingerprint(info):
    cfg = settings()
    content_hashes = []
    for doc in info["documents"]:
        path = Path(doc["path"])
        stat = path.stat()
        content_hashes.append(file_digest(str(path), stat.st_size, stat.st_mtime_ns))
        if doc.get("annotations_path"):
            annotations = Path(doc["annotations_path"])
            stat = annotations.stat()
            content_hashes.append(file_digest(str(annotations), stat.st_size, stat.st_mtime_ns))
    payload = [info, content_hashes, cfg.embedding_backend, cfg.embedding_model, cfg.embedding_revision,
               cfg.embedding_document_prefix, cfg.embedding_query_prefix, "page-clause-1100-150-v1"]
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


@lru_cache(maxsize=64)
def file_digest(path, size, mtime):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def index_info():
    raw = redis_client().get("corpus:active")
    return json.loads(raw) if raw else None


def collection():
    info = index_info()
    if not info:
        raise RuntimeError("corpus-not-indexed")
    if fingerprint(manifest()) != info["fingerprint"]:
        raise RuntimeError("corpus-configuration-changed-reindex-required")
    return chroma().get_collection(info["collection"])


def ingest(force=False):
    cfg = settings()
    info = manifest()
    if cfg.app_mode == "production":
        if info.get("status") != "approved" or not info.get("reviewed_by") or not info.get("reviewed_on"):
            raise ValueError("Official corpus must be reviewed and approved before production indexing")
        if not {"tariff", "supply"} <= {d["kind"] for d in info["documents"]}:
            raise ValueError("Both tariff and supply documents are required")
    start = time.monotonic()
    fp = fingerprint(info)
    name = "corpus-" + fp[:24]
    coll = chroma().get_or_create_collection(name, metadata={"hnsw:space": "cosine"})
    previous = set(coll.get()["ids"])
    current = set()
    chunk_count = 0
    splitter = RecursiveCharacterTextSplitter(chunk_size=1100, chunk_overlap=150,
                                               separators=["\n\n", "\n", ". ", " ", ""])
    for doc in info["documents"]:
        path = Path(doc["path"])
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if cfg.app_mode == "production":
            if not doc.get("source_url", "").startswith("https://") or not doc.get("version"):
                raise ValueError("Official source URL and document version required")
            if doc.get("sha256") != digest:
                raise ValueError(f"Document hash mismatch: {doc['id']}")
        if path.suffix == ".json":
            pages = json.loads(path.read_text(encoding="utf-8"))
        else:
            pages = []
            reader = PdfReader(path)
            if doc.get("annotations_path"):
                annotations = json.loads(Path(doc["annotations_path"]).read_text(encoding="utf-8"))
                for annotation in annotations:
                    text = " ".join(reader.pages[annotation["page"] - 1].extract_text().split())
                    excerpt = " ".join(annotation["text"].split())
                    if excerpt not in text:
                        raise ValueError(f"Annotation is not an exact source-page passage: {doc['id']}/{annotation['clause']}")
                    pages.append({**annotation, "text": excerpt})
            for page_number, page in enumerate(reader.pages, 1):
                if doc.get("annotations_path"):
                    break
                if doc.get("pages") and page_number not in doc["pages"]:
                    continue
                text = page.extract_text() or ""
                if len(text.strip()) < 40:
                    raise ValueError(f"OCR/text-layer review required: {path}, page {page_number}")
                # Split at numbered clause boundaries, retaining page-level provenance.
                for part in re.split(r"\n(?=\s*\d{1,2}\.\d{1,3}\s)", text):
                    match = re.search(r"\b(\d{1,2}\.\d{1,3})\b", part)
                    pages.append({"text": part, "page": page_number,
                                  "clause": doc.get("clause_overrides", {}).get(str(page_number),
                                      match.group(1) if match else f"page-{page_number}"),
                                  "topic": "official"})
        for page in pages:
            for part in splitter.split_text(page["text"]):
                chunk_id = doc["id"] + "-" + hashlib.sha256(
                    f"{doc['version']}:{page['page']}:{page['clause']}:{part}".encode()).hexdigest()[:20]
                current.add(chunk_id)
                chunk_count += 1
                if chunk_id in previous and not force:
                    continue
                meta = {"document": doc["id"], "title": doc["title"], "clause": page["clause"],
                        "page": page["page"], "topic": page["topic"], "source_url": doc["source_url"],
                        "version": doc["version"], "document_sha256": digest,
                        "effective_from": doc["effective_from"], "effective_to": doc["effective_to"],
                        "kind": doc["kind"], "corpus_status": info["status"]}
                vector = embedder().embed_documents([part])[0]
                coll.upsert(ids=[chunk_id], documents=[part], metadatas=[meta], embeddings=[vector])
    stale = previous - current
    if stale:
        coll.delete(ids=list(stale))
    elapsed = time.monotonic() - start
    result = {"collection": name, "fingerprint": fp, "version": info["version"], "status": info["status"],
              "state": info["state"], "built_at": time.time(), "chunks": chunk_count,
              "ingestion_seconds": elapsed, "chunks_per_second": chunk_count / max(elapsed, .001),
              "documents": info["documents"], "embedding_backend": cfg.embedding_backend}
    redis_client().set("corpus:active", json.dumps(result))
    return result


def row(chunk_id, text, metadata):
    return {"chunk_id": chunk_id, "text": text, **metadata}


def _search(payload):
    query, strategy = payload["query"], payload.get("strategy", "hybrid")
    coll = collection()
    if not coll.count():
        return []
    vector_hits = coll.query(query_embeddings=[embedder().embed_query(query)], n_results=min(8, coll.count()))
    ranked = [row(i, t, m) for i, t, m in zip(vector_hits["ids"][0], vector_hits["documents"][0],
                                              vector_hits["metadatas"][0])]
    if strategy != "vector":
        # Lexical complement is important for clause identifiers and modifier vocabulary.
        all_rows = coll.get(include=["documents", "metadatas"])
        lexical = [row(i, t, m) for i, t, m in zip(all_rows["ids"], all_rows["documents"], all_rows["metadatas"])]
        terms = set(words(query))
        lexical.sort(key=lambda p: len(terms & set(words(p["text"]))), reverse=True)
        scores = {}
        records = {}
        for result_list in [ranked, lexical[:8]]:
            for rank, item in enumerate(result_list):
                cid = item["chunk_id"]
                records[cid] = item
                scores[cid] = scores.get(cid, 0) + 1 / (60 + rank)
        ranked = [records[i] for i in sorted(scores, key=scores.get, reverse=True)]
    return ranked[:payload.get("limit", 4)]


# LangChain Runnable owns retrieval orchestration; invocation occurs only after an agent tool decision.
retrieval_chain = RunnableLambda(_search)


def search(query, strategy="hybrid", limit=4):
    return retrieval_chain.invoke({"query": query, "strategy": strategy, "limit": limit})


def lookup(identifier):
    coll = collection()
    values = coll.get(where={"clause": identifier}, include=["documents", "metadatas"])
    if not values["ids"]:
        values = coll.get(ids=[identifier], include=["documents", "metadatas"])
    return [row(i, t, m) for i, t, m in zip(values["ids"], values["documents"], values["metadatas"])]
