"""Step 2: prepare a repository so its code can be searched by meaning.

Usage: python 01_index_repo.py <path-to-repo> [v2|v1]
"""
import json
import sys
import time
import numpy as np
from common import chunk_repo, doc_text, load_model

# WORKFLOW
# 1. Choose the folder containing the code to search.
# 2. Split its source files into smaller pieces and save those pieces.
# 3. Turn each piece into a vector (a list of numbers representing its meaning).
# 4. Save the vectors so 02_search.py can find relevant code later.

# Use command-line values when provided; otherwise index the bundled requests
# example and use model version v2.
repo = sys.argv[1] if len(sys.argv) > 1 else "requests"
version = sys.argv[2] if len(sys.argv) > 2 else "v2"

# Break the repository into code chunks. For Python, a chunk is usually a
# function or class method; other supported files are divided into line ranges.
chunks = chunk_repo(repo)
# Save the code and its labels/locations separately from the number vectors.
# Search needs both: vectors for matching and chunks for showing the result.
with open("chunks.json", "w") as f:
    json.dump(chunks, f)
files = len({c["path"] for c in chunks})
print(f"Found {len(chunks)} functions/methods in {files} files")

# Load the model and convert each labeled code chunk into a meaning vector.
model = load_model(version)
t0 = time.time()
vectors = model.encode([doc_text(c) for c in chunks], prompt="", batch_size=16,
                       normalize_embeddings=True, show_progress_bar=True)
# Store vectors as compact, standard-precision numbers for use by the search step.
np.save(f"vectors_{version}.npy", vectors.astype(np.float32))
print(f"Embedded with {version} in {time.time() - t0:.1f}s -> vectors_{version}.npy, shape {vectors.shape}")
