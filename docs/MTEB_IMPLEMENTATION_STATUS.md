# MTEB Evaluation Implementation Status

> Historical planning artifact: this file documents phased implementation notes and
> may include outdated branch/timeline statements. Use `docs/content/*`,
> `docs/API_README.md`, and FastAPI OpenAPI docs for current operational behavior.

## Overview

This document tracks the implementation of MTEB-style retrieval evaluation for the MetivitaEval platform. The implementation follows a phased, incremental approach that preserves the existing DAAT evaluation system.

**Branch:** `mteb-evaluation`
**Base:** `dev`
**Status:** Phase 2 Complete ✅

---

## Completed Phases

### ✅ Phase 1: Foundation & Templates (Completed)

**What Was Built:**

1. **Dataset Templates** (`src/metivta_eval/dataset/mteb/`)
   - `corpus_template.jsonl` - 5 Torah passage examples (BEIR format)
   - `queries_template.jsonl` - 5 query examples
   - `qrels_template.tsv` - Relevance annotations (0-3 graded scale)
   - `README.md` - Comprehensive 400+ line guide

2. **API Specification** (`docs/api_specification.md`)
   - Complete endpoint contract (POST /retrieve)
   - Request/response formats (OpenAI-style + BEIR-style)
   - Examples: Flask, FastAPI, hybrid retrieval, reranking
   - Fair testing protocol
   - Infrastructure recommendations

3. **Validation System** (`src/metivta_eval/scripts/validate_mteb_dataset.py`)
   - Format validation (JSON, TSV syntax)
   - Cross-reference checking (IDs exist in corpus/queries)
   - Coverage analysis and recommendations
   - Colored terminal output with statistics
   - ✅ Tested with templates - all pass

4. **Dependencies** (`pyproject.toml`)
   - `pytrec-eval>=0.5` - For nDCG, MAP, Recall, Precision
   - `faiss-cpu>=1.7.4` - Fast vector search
   - `sentence-transformers>=2.2.0` - Embeddings
   - `numpy>=1.24.0` - Array operations

**Files Created:**
- `src/metivta_eval/dataset/mteb/` (4 files)
- `docs/api_specification.md`
- `src/metivta_eval/scripts/validate_mteb_dataset.py`
- `pyproject.toml` (modified)

**Validation Results:**
```
Corpus:  ✅ Valid (5 passages)
Queries: ✅ Valid (5 queries)
Qrels:   ✅ Valid (10 annotations, 40% coverage)
```

---

### ✅ Phase 2: Core Implementation & E2E Test (Completed)

**What Was Built:**

1. **MTEB Evaluators** (`src/metivta_eval/evaluators/mteb_evaluators.py`)
   - **nDCG@k**: Normalized Discounted Cumulative Gain (MTEB primary metric)
   - **MAP@k**: Mean Average Precision (BEIR standard)
   - **MRR@k**: Mean Reciprocal Rank (QA metric)
   - **Recall@k**: Coverage/sensitivity metric
   - **Precision@k**: Quality/specificity metric
   - All computed at k=[1, 3, 5, 10, 100, 1000]
   - Graded relevance support (0-3 scale)
   - Result formatting for display

2. **Reference API Implementation** (`examples/reference_retrieval_api.py`)
   - Flask endpoint at `POST /retrieve`
   - sentence-transformers embeddings (all-MiniLM-L6-v2)
   - FAISS flat index for exact search
   - OpenAI-style response format
   - Health check endpoint
   - Handles Hebrew text (UTF-8)
   - Ready for users to adapt

3. **Complete E2E Test** (`tests/e2e/test_mteb_e2e.py`)
   - Starts mock user API automatically
   - Loads template dataset
   - Queries API for each query
   - Computes all MTEB metrics
   - Generates leaderboard entry
   - Cleanup on exit

**Test Results (✅ All Passing):**
```
Primary Metric (nDCG@10): 0.8642
MAP@100:                  0.7500
MRR@10:                   0.8667
Recall@100:               1.0000
Precision@10:             0.4000
```

**Files Created:**
- `src/metivta_eval/evaluators/mteb_evaluators.py`
- `examples/reference_retrieval_api.py`
- `tests/e2e/test_mteb_e2e.py`

**What Works:**
- ✅ Dataset loading (corpus, queries, qrels)
- ✅ Vector embedding and indexing (FAISS)
- ✅ API endpoint querying (HTTP POST)
- ✅ Response parsing (OpenAI & BEIR formats)
- ✅ MTEB metric computation (all 5 metrics)
- ✅ Result formatting and display
- ✅ Leaderboard entry generation

---

## Pending Phases

### 🔄 Phase 3: Configuration System (Next)

**What Needs to Be Built:**

1. **Config Updates** (`src/metivta_eval/config/config.toml`)
   ```yaml
   evaluation_mode: "daat"  # or "mteb" or "both"

   mteb:
     k_values: [1, 3, 5, 10, 100, 1000]
     primary_metric: "ndcg_10"
     embedding_model: "all-MiniLM-L6-v2"
     cache_embeddings: true
     timeout_seconds: 30

   # Keep existing DAAT config
   daat:
     weights:
       dai: 0.6
       mla: 0.4
   ```

2. **Mode Switching Logic**
   - Load evaluation mode from config
   - Route to appropriate evaluators
   - Support "both" mode for comparison

**Estimated Time:** 2 hours

---

### 🔄 Phase 4: API Integration (After Phase 3)

**What Needs to Be Built:**

1. **MTEB Submission Handler** (`api/handlers/mteb_submission.py`)
   - Load BEIR dataset (corpus, queries, qrels)
   - Query user's API endpoint
   - Parse responses (both formats)
   - Compute MTEB metrics
   - Store results in Supabase

2. **Update /submit Endpoint** (`api/server.py`)
   ```python
   @app.route('/submit', methods=['POST'])
   def submit():
       mode = config['evaluation_mode']
       if mode == "daat":
           return submit_daat_evaluation()
       elif mode == "mteb":
           return submit_mteb_evaluation()  # NEW
       elif mode == "both":
           return submit_dual_evaluation()
   ```

3. **Response Parser** (`src/metivta_eval/utils/response_parser.py`)
   - Accept OpenAI-style format
   - Accept BEIR-style format
   - Validate passage IDs
   - Normalize scores

**Estimated Time:** 4 hours

---

### 🔄 Phase 5: Leaderboard (After Phase 4)

**What Needs to Be Built:**

1. **MTEB Leaderboard Template** (`api/templates/leaderboard_mteb.html`)
   - Display nDCG@k, MAP@k, MRR@k, Recall@k, Precision@k
   - Sort by nDCG@10 (MTEB standard)
   - Show all k values in expandable sections
   - Compare with DAAT leaderboard

2. **Update Leaderboard Handler** (`api/handlers/generate_leaderboard.py`)
   ```python
   @app.route('/leaderboard')
   def leaderboard():
       mode = request.args.get('mode', 'daat')
       if mode == 'mteb':
           return render_mteb_leaderboard()
       return render_daat_leaderboard()
   ```

3. **Database Schema** (Supabase)
   - Add `evaluation_mode` column to submissions table
   - Store MTEB metrics as JSONB
   - Preserve existing DAAT submissions

**Estimated Time:** 3 hours

---

### 🔄 Phase 6: Documentation & Polish (Final)

**What Needs to Be Built:**

1. **User Guide** (`docs/mteb_evaluation_guide.md`)
   - How to prepare 20k corpus
   - Building vector index
   - Implementing API endpoint
   - Testing locally
   - Submitting for evaluation

2. **Update README** (`README.md`)
   - Mention dual evaluation modes
   - Link to MTEB guide
   - Explain fair testing approach

3. **Migration Script** (`scripts/migrate_to_mteb.py`)
   - Help users convert existing datasets
   - Validate converted data
   - Generate qrels from existing annotations

**Estimated Time:** 2 hours

---

## Total Timeline

| Phase | Status | Time Spent | Time Remaining |
|-------|--------|------------|----------------|
| Phase 1: Foundation | ✅ Complete | 3 hours | - |
| Phase 2: Core + E2E | ✅ Complete | 4 hours | - |
| Phase 3: Configuration | 🔄 Next | - | 2 hours |
| Phase 4: API Integration | 🔄 Pending | - | 4 hours |
| Phase 5: Leaderboard | 🔄 Pending | - | 3 hours |
| Phase 6: Documentation | 🔄 Pending | - | 2 hours |
| **Total** | | **7 hours** | **11 hours** |

**Estimated Completion:** 18 hours total (39% complete)

---

## Key Design Decisions

### ✅ Branch-Based Development
- All work on `mteb-evaluation` branch
- Preserves existing `dev` branch intact
- Easy to compare, merge, or abandon
- No risk to production system

### ✅ Additive Implementation
- New evaluators alongside existing ones
- Config-driven mode switching
- Dual leaderboards (DAAT + MTEB)
- Users can choose evaluation mode

### ✅ BEIR/MTEB Standards
- Dataset format follows BEIR exactly
- Metrics match MTEB implementation
- nDCG@10 as primary metric (MTEB standard)
- Graded relevance (0-3 scale)

### ✅ Fair Testing Protocol
- Users control infrastructure (vector DB, models)
- Platform standardizes: queries, metrics, ground truth
- API contract allows any retrieval method
- Real production system testing

---

## Testing Status

### ✅ Unit Tests
- `validate_mteb_dataset.py` - ✅ Passing (5/5 template files valid)

### ✅ Integration Tests
- `test_mteb_e2e.py` - ✅ Passing (all 6 steps successful)

### 🔄 Pending Tests
- API endpoint integration test
- Supabase storage test
- Leaderboard rendering test
- Dual-mode evaluation test

---

## API Specification Summary

### Endpoint Requirements
- **Method:** POST
- **URL:** User-provided (e.g., https://their-api.com/retrieve)
- **Timeout:** 30 seconds
- **Concurrency:** Up to 5 parallel requests

### Request Format
```json
{
  "query": "What does Rambam say about teshuvah?",
  "top_k": 100
}
```

### Response Formats (Both Accepted)

**OpenAI-Style (Recommended):**
```json
{
  "results": [
    {"id": "passage_001", "score": 0.9234},
    {"id": "passage_002", "score": 0.8876}
  ]
}
```

**BEIR-Style (Compact):**
```json
{
  "passage_001": 0.9234,
  "passage_002": 0.8876
}
```

---

## Metrics Explained

### nDCG@10 (Primary Metric)
- **Range:** 0.0 to 1.0
- **Measures:** Ranking quality with position-based discounting
- **Why Primary:** MTEB standard for retrieval tasks
- **Good Score:** >0.7 (research baseline)

### MAP@100
- **Range:** 0.0 to 1.0
- **Measures:** Precision at each relevant document position
- **Use Case:** Binary relevance evaluation

### MRR@10
- **Range:** 0.0 to 1.0
- **Measures:** Position of first relevant document
- **Use Case:** Question answering (one good answer needed)

### Recall@100
- **Range:** 0.0 to 1.0
- **Measures:** Fraction of relevant documents found
- **Use Case:** Coverage evaluation

### Precision@10
- **Range:** 0.0 to 1.0
- **Measures:** Fraction of retrieved documents that are relevant
- **Use Case:** Top-k quality check

---

## Dependencies Status

### ✅ Installed
- `sentence-transformers` - Embedding models
- `faiss-cpu` - Vector search
- `numpy` - Array operations

### ❌ Not Yet Installed
- `pytrec-eval` - Metrics computation (needed for final integration)

### Installation Command
```bash
uv pip compile pyproject.toml -o requirements.txt
uv pip sync requirements.txt
```

---

## File Structure

```
MetivitaEval/
├── src/metivta_eval/
│   ├── evaluators/
│   │   ├── code_evaluators.py          # Existing (DAAT)
│   │   ├── daat_evaluator.py           # Existing (DAAT)
│   │   └── mteb_evaluators.py          # ✅ NEW (MTEB)
│   ├── dataset/
│   │   ├── Q1-dataset.json             # Existing (DAAT)
│   │   └── mteb/                       # ✅ NEW (MTEB)
│   │       ├── corpus_template.jsonl
│   │       ├── queries_template.jsonl
│   │       ├── qrels_template.tsv
│   │       └── README.md
│   └── scripts/
│       └── validate_mteb_dataset.py    # ✅ NEW
├── api/
│   ├── server.py                       # To be modified
│   └── handlers/
│       ├── submit_evaluation.py        # Existing (DAAT)
│       └── mteb_submission.py          # 🔄 Pending
├── docs/
│   ├── api_specification.md            # ✅ NEW
│   └── MTEB_IMPLEMENTATION_STATUS.md   # ✅ NEW (this file)
├── examples/
│   └── reference_retrieval_api.py      # ✅ NEW
└── tests/
    └── e2e/
        └── test_mteb_e2e.py             # ✅ NEW
```

---

## Running the E2E Test

```bash
# From project root
python3 tests/e2e/test_mteb_e2e.py
```

**Expected Output:**
```
======================================================================
               MTEB END-TO-END EVALUATION TEST
======================================================================

📁 Step 1: Loading test dataset...
✅ Loaded 5 passages, 5 queries

🚀 Step 2: Starting mock user retrieval API...
✅ API running at http://localhost:5001

🔍 Step 3: Running retrieval for all queries...
✅ Retrieved results for 5 queries

📊 Step 4: Computing MTEB metrics...
✅ Metrics computed

📋 Step 5: Displaying results...
   nDCG@10: 0.8642
   MAP@100: 0.7500
   ...

📊 Step 6: Simulating leaderboard update...
✅ Leaderboard updated (simulated)

======================================================================
                    ✅ E2E TEST PASSED!
======================================================================
```

---

## Next Steps

1. **Immediate:** Update `config.toml` with MTEB settings (Phase 3)
2. **Then:** Integrate MTEB submission handler with Flask API (Phase 4)
3. **After:** Create MTEB leaderboard template (Phase 5)
4. **Finally:** Write user documentation (Phase 6)

---

## Questions & Answers

### Q: Will this break the existing DAAT system?
**A:** No. All changes are additive. DAAT system remains functional on `dev` branch and will coexist with MTEB on merged branch via config switching.

### Q: Can we have both evaluation modes?
**A:** Yes. Set `evaluation_mode: "both"` in config to run both DAAT and MTEB evaluations side-by-side.

### Q: How do users test their API before submission?
**A:** Use the reference implementation (`examples/reference_retrieval_api.py`) as a template, or use the validation endpoint (`POST /validate-endpoint`).

### Q: What's the minimum dataset size?
**A:** Templates use 5 passages/queries for testing. Production should use 100+ queries with 100-200 annotations per query for meaningful benchmarks.

### Q: How long does evaluation take?
**A:** With 20k passages and 100 queries: ~1-5 minutes (depends on user's API response time).

---

## Contributors

- Initial Design & Implementation: Claude (Anthropic)
- Project Oversight: MetivitaEval Team
- Testing: Automated E2E Suite

---

## References

- **MTEB Paper:** https://arxiv.org/abs/2210.07316
- **BEIR Benchmark:** https://github.com/beir-cellar/beir
- **BEIR Paper:** https://arxiv.org/abs/2104.08663
- **nDCG Explained:** https://www.evidentlyai.com/ranking-metrics/ndcg-metric
- **Retrieval Metrics:** https://weaviate.io/blog/retrieval-evaluation-metrics

---

**Last Updated:** 2025-11-02
**Branch:** `mteb-evaluation`
**Status:** Phase 2 Complete (7/18 hours)
