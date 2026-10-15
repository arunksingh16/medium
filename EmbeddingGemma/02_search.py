"""Step 3: search the code by meaning, next to classic keyword search (BM25).

Usage: python 02_search.py "your question" [v2|v1]
"""
import sys
import numpy as np
from common import BM25, QUERY_PROMPT, doc_text, load_chunks, load_model

# WORKFLOW
# 1. Read the saved code descriptions and vectors created by 01_index_repo.py.
# 2. Turn the search question into a vector.
# 3. Rank the saved code two ways: by matching words and by matching meaning.
# 4. Print the five highest-ranked code locations for each method.

# Accept a question and optional model version from the command line.
# Defaults make the script runnable without extra arguments.
query = sys.argv[1] if len(sys.argv) > 1 else "do not send login credentials when a redirect goes to a different website"
version = sys.argv[2] if len(sys.argv) > 2 else "v2"

# Load the saved code chunks and the matching vectors. These files are produced
# by 01_index_repo.py and must come from the same indexing run.
chunks = load_chunks()
vectors = np.load(f"vectors_{version}.npy")

# Represent the question as a vector, then compare it to every code vector.
# Because the vectors were normalized during indexing, dot product gives a
# similarity score: larger values indicate closer matches.
model = load_model(version)
q = model.encode(query, prompt=QUERY_PROMPT, normalize_embeddings=True)
semantic = vectors @ q

# Also calculate a classic search-engine score based on shared words. This gives
# us a keyword-search result to compare with the meaning-based result.
keyword = np.array(BM25([doc_text(c) for c in chunks]).scores(query))


def show(title, scores):
    """Print the five best matches and where each one appears in the repository."""
    print(title)
    # argsort gives positions from low to high; negate scores to put the largest first.
    for rank, i in enumerate(np.argsort(-scores)[:5], 1):
        c = chunks[i]
        print(f"  {rank}. {scores[i]:6.3f}  {c['path']}:{c['line']}  {c['name']}")
    print()


# Show the two rankings separately so you can see where meaning-based search
# finds a match even when the question and code use different words.
print(f'\nQuery: "{query}"\n')
show("Keyword search (BM25):", keyword)
show(f"EmbeddingGemma {version} (meaning):", semantic)
