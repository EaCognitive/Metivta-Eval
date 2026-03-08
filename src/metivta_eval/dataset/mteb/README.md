# MTEB Dataset Format Guide

This directory contains template files showing the required format for MTEB-style retrieval evaluation.

## Overview

The MTEB evaluation system uses the BEIR (Benchmarking IR) standard format, consisting of three files:

1. **corpus.jsonl** - Your 20k Torah passages
2. **queries.jsonl** - Questions for retrieval
3. **qrels.tsv** - Query-passage relevance annotations (ground truth)

## File Formats

### 1. corpus.jsonl (Corpus/Passages)

**Format:** JSON Lines (one JSON object per line)

**Required Fields:**
- `_id` (string): Unique passage identifier
- `text` (string): The passage content

**Optional Fields:**
- `title` (string): Passage title or source citation

**Example:**
```json
{"_id": "passage_001", "title": "Divrei Yoel, Parshas Bereishis", "text": "הרבי מסאטמאר זצ\"ל מבאר..."}
{"_id": "passage_002", "title": "Rambam, Hilchos Teshuvah", "text": "כתב הרמב\"ם..."}
```

**How to Create Your 20k Corpus:**

```python
import json

# Example: Converting your passages to BEIR format
passages = [
    {
        "_id": "passage_001",
        "title": "Source Title",
        "text": "The full text of the passage..."
    },
    # ... 20,000 entries
]

# Write to corpus.jsonl
with open('corpus.jsonl', 'w', encoding='utf-8') as f:
    for passage in passages:
        f.write(json.dumps(passage, ensure_ascii=False) + '\n')
```

**Important Notes:**
- Each line must be valid JSON
- Use UTF-8 encoding (critical for Hebrew text)
- `_id` must be unique across all passages
- Don't include URLs in `text` field (use metadata if needed)

---

### 2. queries.jsonl (Questions)

**Format:** JSON Lines

**Required Fields:**
- `_id` (string): Unique query identifier
- `text` (string): The question text

**Example:**
```json
{"_id": "query_001", "text": "What does the Divrei Yoel say about Bereishis?"}
{"_id": "query_002", "text": "According to the Rambam, what is the power of teshuvah?"}
```

**How to Create Your Queries:**

```python
queries = [
    {
        "_id": "query_001",
        "text": "Your question here?"
    },
    # ... all your questions
]

with open('queries.jsonl', 'w', encoding='utf-8') as f:
    for query in queries:
        f.write(json.dumps(query, ensure_ascii=False) + '\n')
```

**Query Guidelines:**
- Clear, specific questions
- Can be in English or Hebrew
- Represent real information needs
- Avoid overly broad queries

---

### 3. qrels.tsv (Relevance Annotations)

**Format:** Tab-Separated Values (TSV)

**Required Columns:**
1. `query-id` - Query identifier (matches `_id` in queries.jsonl)
2. `corpus-id` - Passage identifier (matches `_id` in corpus.jsonl)
3. `score` - Relevance score (0-3)

**Relevance Scale (TREC-DL Standard):**

| Score | Label | Description | Example |
|-------|-------|-------------|---------|
| **0** | Irrelevant | Passage doesn't address the query | Query about Rambam, passage about Chassidus |
| **1** | Relevant Topic | Related topic but no direct answer | Query about Rambam on teshuvah, passage mentions Rambam but different topic |
| **2** | Highly Relevant | Partial or unclear answer | Query about specific teaching, passage contains it but mixed with other content |
| **3** | Perfectly Relevant | Direct, complete answer | Query asks for Divrei Yoel on Bereishis, passage is exactly that |

**Example qrels.tsv:**
```tsv
query-id	corpus-id	score
query_001	passage_001	3
query_001	passage_003	1
query_002	passage_002	3
query_002	passage_004	1
```

**How to Create Your Qrels:**

```python
# Method 1: Direct TSV writing
with open('qrels.tsv', 'w', encoding='utf-8') as f:
    f.write('query-id\tcorpus-id\tscore\n')  # Header
    f.write('query_001\tpassage_001\t3\n')
    f.write('query_001\tpassage_003\t1\n')
    # ... more annotations

# Method 2: From Python dictionary
import csv

qrels = {
    'query_001': {
        'passage_001': 3,
        'passage_003': 1
    },
    'query_002': {
        'passage_002': 3,
        'passage_004': 1
    }
}

with open('qrels.tsv', 'w', encoding='utf-8', newline='') as f:
    writer = csv.writer(f, delimiter='\t')
    writer.writerow(['query-id', 'corpus-id', 'score'])

    for query_id, passages in qrels.items():
        for passage_id, score in passages.items():
            writer.writerow([query_id, passage_id, score])
```

---

## Annotation Guidelines

### How to Annotate Query-Passage Relevance

For each query, you need to identify and score relevant passages from your 20k corpus.

#### Step 1: Understand the Query
- Read the question carefully
- Identify the key information need
- Note important keywords and concepts

#### Step 2: Evaluate Each Candidate Passage
Ask yourself:
1. Does this passage address the query?
2. Does it contain the answer?
3. How complete/clear is the answer?

#### Step 3: Assign Relevance Score

**Score 3 (Perfect) - Use when:**
- Passage directly answers the question
- Information is complete and clear
- No additional passages needed
- Example: Query asks for "Rambam on teshuvah", passage is exactly Rambam's laws of teshuvah

**Score 2 (Highly Relevant) - Use when:**
- Passage addresses query but answer is partial
- Information is relevant but lacks detail
- Contains the answer mixed with other content
- Example: Query asks for specific Divrei Yoel teaching, passage mentions it among other topics

**Score 1 (Relevant Topic) - Use when:**
- Passage is on the same general topic
- Contains related information but not the answer
- Provides useful context but doesn't directly answer
- Example: Query about prayer, passage discusses mitzvot generally

**Score 0 (Irrelevant) - Use when:**
- Passage doesn't address the query at all
- Topic is different or only tangentially related
- Would not be helpful to the user
- Example: Query about Shabbos, passage about kashrut

### Annotation Coverage

**Important:** You don't need to annotate all 20k passages for each query!

**Recommended approach:**
- Annotate 100-200 passages per query
- Focus on passages most likely to be relevant
- Include "hard negatives" (similar but not relevant)

**Hard Negatives:** Passages that are semantically similar but not actually relevant. These help create a more challenging benchmark.

Example:
- Query: "What does Rambam say about teshuvah?"
- Hard Negative: Passage about Ramban on teshuvah (similar topic, wrong source)

### Annotation Workflow

#### Method 1: Retrieval-Based Annotation
1. Use a retrieval system to get top 100 candidates per query
2. Manually review and score each candidate
3. This is efficient and follows BEIR best practices

#### Method 2: Random Sampling + Retrieval
1. Get top 50 from retrieval system
2. Add 25 random passages from corpus
3. Add 25 passages from related topics (hard negatives)
4. Annotate all 100

#### Quality Control
- Have 2-3 annotators score the same passages
- Measure inter-annotator agreement (Cohen's Kappa)
- Target: Kappa > 0.6 (substantial agreement)
- Resolve disagreements through discussion

---

## Validation

Before using your dataset for evaluation, validate it using the provided script:

```bash
python src/metivta_eval/scripts/validate_mteb_dataset.py \
    --corpus src/metivta_eval/dataset/mteb/corpus.jsonl \
    --queries src/metivta_eval/dataset/mteb/queries.jsonl \
    --qrels src/metivta_eval/dataset/mteb/qrels.tsv
```

The validator checks:
- ✅ File formats are correct
- ✅ All IDs in qrels exist in corpus and queries
- ✅ No duplicate IDs
- ✅ Relevance scores are in valid range (0-3)
- ✅ UTF-8 encoding is correct
- ✅ JSON syntax is valid

---

## Loading Your Dataset

Once you've created your dataset files, the evaluation system will load them using:

```python
from beir.datasets.data_loader import GenericDataLoader

corpus, queries, qrels = GenericDataLoader(
    corpus_file="src/metivta_eval/dataset/mteb/corpus.jsonl",
    query_file="src/metivta_eval/dataset/mteb/queries.jsonl",
    qrels_file="src/metivta_eval/dataset/mteb/qrels.tsv"
).load_custom()

# corpus: {passage_id: {"title": str, "text": str}}
# queries: {query_id: query_text}
# qrels: {query_id: {passage_id: relevance_score}}
```

---

## Expected Dataset Statistics

For a well-constructed benchmark with 20k passages:

| Metric | Recommended Value |
|--------|------------------|
| Total Passages | 20,000 |
| Total Queries | 100-500 |
| Avg Annotations per Query | 100-200 |
| Total Annotations | 10,000-100,000 |
| Avg Relevant per Query | 5-20 |
| Hard Negatives per Query | 10-30 |
| Annotation Coverage | 5-10% of all query-passage pairs |

---

## Common Issues & Solutions

### Issue 1: JSON Parse Errors
**Problem:** `json.decoder.JSONDecodeError`

**Solution:**
- Ensure each line is valid JSON
- Don't include trailing commas
- Escape special characters properly
- Use `json.dumps()` to ensure valid JSON

### Issue 2: Hebrew Text Not Displaying
**Problem:** Hebrew appears as `\u05d0\u05d1\u05d2`

**Solution:**
```python
# Use ensure_ascii=False
json.dumps(obj, ensure_ascii=False)

# Use UTF-8 encoding
with open('file.jsonl', 'w', encoding='utf-8') as f:
    ...
```

### Issue 3: Missing IDs in Qrels
**Problem:** Qrels references passage IDs not in corpus

**Solution:**
- Run validation script to identify missing IDs
- Remove invalid qrels entries or add missing passages

### Issue 4: Inconsistent Relevance Scores
**Problem:** Same query-passage pair has different scores

**Solution:**
- Check for duplicate entries in qrels.tsv
- Establish clear annotation guidelines
- Use inter-annotator agreement to validate

---

## Example: Converting Existing Dataset

If you have an existing Q&A dataset, here's how to convert it:

```python
import json

# Your existing dataset (example format)
existing_data = [
    {
        "question": "What does Rambam say about teshuvah?",
        "answer": "The Rambam writes in Hilchos Teshuvah...",
        "source_passage": "כתב הרמב\"ם בהלכות תשובה..."
    },
    # ... more entries
]

# Convert to BEIR format
corpus = []
queries = []
qrels = {}

for i, item in enumerate(existing_data):
    passage_id = f"passage_{i:06d}"
    query_id = f"query_{i:06d}"

    # Add to corpus
    corpus.append({
        "_id": passage_id,
        "title": "",  # Extract if available
        "text": item["source_passage"]
    })

    # Add to queries
    queries.append({
        "_id": query_id,
        "text": item["question"]
    })

    # Add to qrels (perfect match = score 3)
    qrels[query_id] = {passage_id: 3}

# Write files
with open('corpus.jsonl', 'w', encoding='utf-8') as f:
    for p in corpus:
        f.write(json.dumps(p, ensure_ascii=False) + '\n')

with open('queries.jsonl', 'w', encoding='utf-8') as f:
    for q in queries:
        f.write(json.dumps(q, ensure_ascii=False) + '\n')

with open('qrels.tsv', 'w', encoding='utf-8') as f:
    f.write('query-id\tcorpus-id\tscore\n')
    for query_id, passages in qrels.items():
        for passage_id, score in passages.items():
            f.write(f'{query_id}\t{passage_id}\t{score}\n')
```

---

## Next Steps

1. **Create your corpus.jsonl** with 20k Torah passages
2. **Create your queries.jsonl** with your test questions
3. **Annotate relevance** to create qrels.tsv
4. **Validate your dataset** using the validation script
5. **Test with evaluation system** using the reference implementation

For questions or issues, refer to the API specification document or create an issue in the repository.

---

## References

- BEIR Benchmark: https://github.com/beir-cellar/beir
- MTEB: https://github.com/embeddings-benchmark/mteb
- TREC-DL Relevance Guidelines: https://microsoft.github.io/msmarco/TREC-Deep-Learning
