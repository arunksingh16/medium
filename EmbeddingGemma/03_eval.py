"""Step 4: score keyword search vs embeddings on 15 questions, then cut the vectors (Matryoshka).

Usage: python 03_eval.py [v2|v1]
Metrics: Hit@1 = right function is first. Hit@5 = right function is in the top 5.
"""
import json
import sys
import numpy as np
from common import BM25, QUERY_PROMPT, doc_text, load_chunks, load_model

# WORKFLOW
# 1. Load saved code chunks, their vectors, and a list of example questions.
# 2. For each question, check where the expected function appears in the results.
# 3. Compare keyword search with the full-size embedding vectors.
# 4. Repeat with shorter vectors to see whether fewer numbers still work well.

# Choose which model's saved vectors to evaluate; v2 is used if none is specified.
version = sys.argv[1] if len(sys.argv) > 1 else "v2"
chunks = load_chunks()
# Keep the code names for checking whether each expected answer was retrieved.
names = [c["name"] for c in chunks]
vectors = np.load(f"vectors_{version}.npy")
# Each evaluation entry provides a question ("q") and expected function names ("want").
evals = json.load(open("eval_queries.json"))

# Turn all test questions into vectors at once and prepare the keyword-search index.
model = load_model(version)
Q = model.encode([e["q"] for e in evals], prompt=QUERY_PROMPT, normalize_embeddings=True)
bm25 = BM25([doc_text(c) for c in chunks])


def first_hit(scores, want):
    """Return the expected function's position in the top five, or None if absent."""
    # A class method may be named ClassName.function, so also match the part after the dot.
    for rank, i in enumerate(np.argsort(-scores)[:5], 1):
        if any(names[i] == w or names[i].endswith("." + w) for w in want):
            return rank
    return None


def report(label, score_fn):
    """Measure how often the expected function ranks first or within the top five."""
    ranks = [first_hit(score_fn(i, e), e["want"]) for i, e in enumerate(evals)]
    # Hit@1 is the share of questions with the right answer ranked first.
    h1 = sum(r == 1 for r in ranks) / len(ranks)
    # Hit@5 is the share where the answer appears anywhere among the top five.
    h5 = sum(r is not None for r in ranks) / len(ranks)
    print(f"{label:<28} Hit@1 {h1:5.0%}   Hit@5 {h5:5.0%}")
    return ranks


def cut(m, d):
    """Keep only the first d vector values, then normalize the shorter vector."""
    m = m[:, :d] if m.ndim == 2 else m[:d]
    # Cutting changes the vector's length, so normalize again for fair comparison.
    return m / np.linalg.norm(m, axis=-1, keepdims=True)


# Compare ordinary keyword search with the complete embedding vectors (768 values).
print(f"\n{len(evals)} questions, {len(chunks)} functions in the index\n")
kw = report("Keyword search (BM25)", lambda i, e: np.array(bm25.scores(e["q"])))
em = report(f"EmbeddingGemma {version} (768d)", lambda i, e: vectors @ Q[i])

# Matryoshka vectors can still be useful after keeping only their first values.
# This checks the search quality at progressively smaller vector sizes.
print("\nMatryoshka: keep only the first N numbers of every vector")
for d in (512, 256, 128):
    V, Qd = cut(vectors, d), cut(Q, d)
    report(f"EmbeddingGemma {version} ({d}d)", lambda i, e: V @ Qd[i])

# Show each question's rank under the two full-size search methods.
# A dash means that the expected function did not appear in the top five.
print("\nPer question (rank of the right function, '-' = not in top 5):")
for e, a, b in zip(evals, kw, em):
    print(f"  keyword {a or '-':>2} | embedding {b or '-':>2} | {e['q']}")
