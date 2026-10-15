"""Step 1: find which code example best matches a question's meaning."""
import time
from common import load_model, QUERY_PROMPT

# WORKFLOW
# 1. Write a question in everyday language.
# 2. Prepare a few code examples, each with a short name.
# 3. Ask the embedding model to turn the question and examples into number patterns.
# 4. Compare those patterns and print the examples from best match to weakest match.
#
# The model is not running the examples or answering the question. It is only
# measuring which example seems closest in meaning to the question.

# Load the embedding model. Think of it as a meaning-comparison tool, not a chatbot.
# Timing this step is useful because the first load can take a while.
t0 = time.time()
model = load_model("v2")
print(f"Model loaded in {time.time() - t0:.1f}s on device: {model.device}")

# 1. A person describes what they want in their own words.
question = "wait longer and longer between attempts when a network call fails"

# 2. These are three possible pieces of code to search through.
# The text in quotation marks is only shown to the model; it is not executed.
snippets = {
    # Calls a function again if the network fails, waiting longer each time.
    "retry_with_backoff": """def call(fn, attempts=5):
    for i in range(attempts):
        try:
            return fn()
        except ConnectionError:
            time.sleep(2 ** i)
    raise RuntimeError("gave up")""",
    # Opens a file and reads settings written in YAML format.
    "parse_config": """def load(path):
    with open(path) as f:
        return yaml.safe_load(f)""",
    # Looks for a value in a temporary in-memory store and returns it if found.
    "cache_lookup": """def get(key):
    if key in _cache:
        return _cache[key]
    return None""",
}

# 3. Convert the question into a list of numbers (called an embedding) that
# represents its meaning. The prompt tells the model this is a code-search question.
q = model.encode(question, prompt=QUERY_PROMPT, normalize_embeddings=True)
# Convert every example into the same kind of number pattern. Adding its name
# gives the model a useful label as well as the code itself.
snippet_texts = [f"title: {name} | text: {code}" for name, code in snippets.items()]
docs = model.encode(snippet_texts, prompt="", normalize_embeddings=True)

# This just displays a few of the question's numbers as a peek behind the scenes.
# The full list is much longer; these six numbers are not meaningful on their own.
print(f"\nEach input became a vector of {q.shape[0]} numbers. First 6 of the question: {q[:6].round(3)}")

# 4. Compare the question's number pattern with each example's pattern.
# The result is one similarity score per example. A higher score means a closer
# match among these examples; it is not a percentage or a guarantee of correctness.
scores = model.similarity(q, docs)[0].tolist()
matches = sorted(zip(snippets.keys(), scores), key=lambda match: match[1], reverse=True)

# Show the question, then list each example from highest score to lowest.
print(f'\nQuestion: "{question}"\n')
for name, score in matches:
    print(f"  {score:.3f}  {name}")

# The first result should be retry_with_backoff, even though the question
# doesn't use words such as "retry", "sleep", or "backoff".
print("\nNote: the question never says 'retry', 'sleep' or 'backoff'.")
