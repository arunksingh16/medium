"""Shared helpers for the EmbeddingGemma 2 code-search demo."""
import ast
import json
import math
import re
from collections import Counter
from pathlib import Path

MODELS = {
    "v2": "google/embeddinggemma-2",      # Apache 2.0, Oct 2026
    "v1": "google/embeddinggemma-300m",   # first EmbeddingGemma (gated: accept the Gemma terms on Hugging Face)
}

# Task prefixes from the model card. Both v1 and v2 understand this format.
QUERY_PROMPT = "task: code retrieval | query: "


def doc_text(chunk):
    """Document format from the model card: title: <filename> | text: <code>."""
    return f"title: {chunk['path']} {chunk['name']} | text: {chunk['code']}"


def load_model(version="v2"):
    import torch
    from sentence_transformers import SentenceTransformer

    kwargs = {"model_kwargs": {"torch_dtype": torch.float32}}  # never float16 with this model
    if version == "v2":
        # Text + code only: drop the vision and audio encoders (740M -> 270M params).
        kwargs["config_kwargs"] = {"vision_config": None, "audio_config": None}
    return SentenceTransformer(MODELS[version], **kwargs)


# ---------- Chunking: one chunk per function or method ----------

CODE_EXTS = {".py", ".go", ".js", ".ts", ".java", ".rb", ".rs", ".sh", ".tf", ".yaml", ".yml"}
SKIP_DIRS = {".git", "node_modules", "venv", ".venv", "__pycache__", "dist", "build", "tests", "test", "docs"}


def chunk_python(path, source, rel):
    tree = ast.parse(source)
    lines = source.splitlines()
    chunks = []

    def add(node, name):
        start = (node.decorator_list[0].lineno if node.decorator_list else node.lineno)
        code = "\n".join(lines[start - 1:node.end_lineno])
        chunks.append({"path": rel, "name": name, "line": start, "code": code})

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            add(node, node.name)
        elif isinstance(node, ast.ClassDef):
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    add(item, f"{node.name}.{item.name}")
    return chunks


def chunk_lines(source, rel, size=60, overlap=10):
    """Fallback for non-Python files: fixed windows of lines."""
    lines = source.splitlines()
    return [{"path": rel, "name": f"lines {i + 1}-{min(i + size, len(lines))}", "line": i + 1,
             "code": "\n".join(lines[i:i + size])}
            for i in range(0, max(len(lines), 1), size - overlap) if lines[i:i + size]]


def chunk_repo(repo):
    repo = Path(repo)
    chunks = []
    for path in sorted(repo.rglob("*")):
        if path.suffix not in CODE_EXTS or not path.is_file():
            continue
        if any(part in SKIP_DIRS or part.startswith(".") for part in path.relative_to(repo).parts):
            continue
        rel = str(path.relative_to(repo))
        source = path.read_text(errors="ignore")
        try:
            chunks += chunk_python(path, source, rel) if path.suffix == ".py" else chunk_lines(source, rel)
        except SyntaxError:
            chunks += chunk_lines(source, rel)
    return chunks


# ---------- Keyword baseline: BM25, the classic search-engine ranking ----------

def tokenize(text):
    words = re.findall(r"[a-zA-Z]+", text)
    out = []
    for w in words:  # split snake_case and camelCase so "get_environ_proxies" -> get, environ, proxies
        out += [p.lower() for p in re.findall(r"[A-Z]?[a-z]+|[A-Z]+(?![a-z])", w)]
    return [w for w in out if len(w) > 2]


class BM25:
    def __init__(self, docs, k1=1.5, b=0.75):
        self.docs = [Counter(tokenize(d)) for d in docs]
        self.lens = [sum(d.values()) for d in self.docs]
        self.avg = sum(self.lens) / len(self.lens)
        df = Counter(w for d in self.docs for w in d)
        n = len(self.docs)
        self.idf = {w: math.log(1 + (n - c + 0.5) / (c + 0.5)) for w, c in df.items()}
        self.k1, self.b = k1, b

    def scores(self, query):
        q = tokenize(query)
        out = []
        for d, ln in zip(self.docs, self.lens):
            s = 0.0
            for w in q:
                if w in d:
                    tf = d[w]
                    s += self.idf[w] * tf * (self.k1 + 1) / (tf + self.k1 * (1 - self.b + self.b * ln / self.avg))
            out.append(s)
        return out


def load_chunks():
    return json.loads(Path("chunks.json").read_text())
