# AuditTrace — Claude Context

## Project
CMPE 258 Deep Learning Final Project, SJSU Spring 2026.
Multi-agent compliance auditing tool: scans GitHub repos with IaC against CIS AWS Benchmark.

**GitHub:** https://github.com/ParthGala2k/AuditTrace
**Student:** Parth Gala | Group 4
**Stack:** FastAPI + LangGraph backend, React + Vite frontend, OpenRouter LLMs, Checkov, SQLite

---

## How to Run

```bash
# Backend (Terminal 1)
cd backend
venv\Scripts\activate
uvicorn main:app --reload

# Frontend (Terminal 2)
cd frontend
npm run dev
# Opens at http://localhost:5173

# Distill policy PDF (one-time, already done)
cd backend
python scripts/distill_policy.py "path/to/CIS_AWS.pdf" --name cis_aws_v7

# Run demo audit (root dir, venv active)
python demo.py --policy cis_aws_v7 --repo https://github.com/bridgecrewio/terragoat
```

---

## Architecture

### Two-Phase Design

**Phase 1 — Offline (one-time)**
`backend/scripts/distill_policy.py` reads the CIS PDF, detects numbered controls via regex,
calls GPT-4o mini once per control, saves 89 structured requirements to `policies/cis_aws_v7.json`.

**Phase 2 — Runtime (per audit)**
1. Clone repo → run Checkov → raw findings (deterministic detection)
2. For each finding, extract the full enclosing Terraform resource block
3. Each of 3 LLMs independently judges every finding as GENUINE / FALSE_POSITIVE / UNCERTAIN
   given the surrounding HCL context (the **real LLM value-add** — Checkov has no context)
4. Aggregate: consensus_score = count of GENUINE votes
   - 3/3 GENUINE → HIGH (prioritise fix)
   - 2/3 GENUINE → LIKELY (schedule fix)
   - 1/3 GENUINE → UNCERTAIN (human review)
   - 3/3 FALSE_POSITIVE → SUPPRESSED (auto-removed from violations list)
5. Save versioned result to SQLite, return to frontend

### File Map

```
backend/
  main.py                  FastAPI app + LangGraph pipeline (scan_node -> consensus_node)
  db.py                    SQLite: projects, audits tables; compliance score calculation
  agents/
    llm.py                 get_llm() factory -> OpenRouter (all agents use this)
    planner.py             PlannerAgent: PDF chunks -> ComplianceRequirement objects
    executor.py            ExecutorAgent: keyword matching of findings to requirements
    critic.py              CriticAgent: builds NetworkX compliance trace graph
    consensus.py           run_consensus(): 3-model FP-filter judgement + voting
  tools/
    pdf_parser.py          PyMuPDF text extraction + section chunking (MAX_PAGES=30)
    checkov_runner.py      Checkov subprocess + repo cloning + extract_resource_block (full HCL block per finding)
    policy_store.py        (unused) early draft of caching; superseded by mapping_cache/
  scripts/
    distill_policy.py      One-time CIS PDF -> policies/cis_aws_v7.json

frontend/
  src/
    App.jsx                Main app: state, audit flow, sticky header, metrics panel
    api.js                 fetchPolicies, runAudit, runEvaluate, fetchFix
    tokens.js              Design tokens (WF color system) + model labels
    components/
      IssueCard.jsx        Expandable violation card; calls /fix on expand
      DiffBlock.jsx        Git-style red/green diff view
      SevChip.jsx          Severity badge (red/amber/green)
      ScanProgress.jsx     Progress bar with pulsing dot

evaluation/
  test_cases.json          55 annotated test cases for planner benchmark
  fp_annotations.json      30 hand-labeled (HCL + verdict) pairs for FP-filter eval (15 GENUINE + 15 FP)
  run_eval.py              Multi-model planner benchmark; outputs comparison_summary.json
  eval_e2e.py              FP-filter eval against fp_annotations.json — produces eval_e2e_results.json
  compute_metrics.py       Library: P/R/F1 helpers used by /evaluate endpoint
  results_*.json           Per-model planner eval per-case output + summary
  eval_e2e_results.json    Latest FP-filter eval output

policies/
  cis_aws_v7.json          89 distilled CIS AWS requirements (committed, never regenerate)

backend/mapping_cache/     SHA-256 keyed JSON cache of LLM clause mappings (gitignored)
demo.py                    CLI demo script: calls /audit, pretty-prints results
make_ppt.py               Generates AuditTrace_Presentation.pptx via python-pptx
```

---

## Key API Endpoints

| Method | Path | What it does |
|--------|------|--------------|
| POST | `/audit` | Full audit: clone + Checkov + consensus. Body: `repo_url`, `policy`, `models` |
| POST | `/evaluate` | Metrics only (no re-audit). Body: `repo_url`, `violations` (JSON), `models` |
| POST | `/fix` | Generate Terraform diff for one violation. Body: `clause_text`, `check_id`, `resource`, `file_path` |
| GET | `/policies` | List available distilled policy specs from `policies/` |
| GET | `/history` | All audit versions for a repo. Query: `repo_url` |
| GET | `/history/report` | Full report for a version. Query: `repo_url`, `version` |
| GET | `/health` | `{"status": "ok"}` |

---

## Models (via OpenRouter)

| Model | ID | Role |
|-------|----|------|
| GPT-4o mini | `openai/gpt-4o-mini` | Default; fastest (~1.85s) |
| DeepSeek V3 | `deepseek/deepseek-chat` | Cheapest ($0.0018/run); best Type/Targets |
| Llama 3.1 70B | `meta-llama/llama-3.1-70b-instruct` | Best severity accuracy |

All three run in parallel for consensus. Configured in `backend/agents/consensus.py` MODELS list.

---

## Environment Variables (.env in backend/)

```
OPENROUTER_API_KEY=...
GITHUB_TOKEN=...          # needed for private repos; optional for public
LLM_MODEL=openai/gpt-4o-mini   # default model override
```

---

## Demo Repos for Testing

| Repo | Why |
|------|-----|
| `https://github.com/bridgecrewio/terragoat` | Primary: intentionally vulnerable Terraform, 500+ violations |
| `https://github.com/nccgroup/sadcloud` | Secondary: 216 Checkov findings |
| `https://github.com/bridgecrewio/cfngoat` | CloudFormation variety |
| `https://github.com/hashicorp/learn-terraform-provision-eks-cluster` | Real-world EKS |

---

## Evaluation Results (actual numbers, latest run)

### Planner Eval — 55 test cases (`comparison_summary.json`)
| Model | Sev Acc | Type Acc | Targets F1 | Avg Latency | Est. Cost |
|-------|---------|----------|------------|-------------|-----------|
| GPT-4o mini | 41.8% | 85.5% | 70.8% | **1.85s** | $0.0023 |
| DeepSeek V3 | 40.0% | **90.9%** | **82.4%** | 12.89s | **$0.0018** |
| Llama 3.1 70B | **45.5%** | 89.1% | 78.6% | 3.15s | $0.0058 |

Interpretation: GPT is fastest, DeepSeek best on type/targets but slow, Llama best on severity.
Severity accuracy is suspiciously low across the board — likely the hand-annotated severity ground
truth in `test_cases.json` is subjective (e.g. tc-001 IAM key rotation: annotated "access_control",
all models predict "secrets_management" — models may actually be right).

### End-to-End Eval — 30 hand-labeled findings (`eval_e2e_results.json`)

The end-to-end eval uses the FP-filter dataset (15 GENUINE + 15 FALSE_POSITIVE) in
`evaluation/fp_annotations.json`. Each annotation is a realistic check_id + resource +
file path + HCL block + correct verdict.

**Per-model GENUINE classification (positive class = GENUINE)**
| Model | Precision | Recall | F1 | TP | FP | FN | TN |
|-------|-----------|--------|----|----|----|----|----|
| GPT-4o mini | 93.8% | 100.0% | **96.8%** | 15 | 1 | 0 | 14 |
| DeepSeek V3 | 100.0% | 100.0% | **100.0%** | 15 | 0 | 0 | 15 |
| Llama 3.1 70B | 100.0% | 73.3% | **84.6%** | 11 | 0 | 4 | 15 |

**Inter-model agreement (Cohen's kappa on 3-way verdicts)**
| Pair | Kappa |
|------|-------|
| GPT vs DeepSeek | 0.93 (very high) |
| DeepSeek vs Llama | 0.73 (moderate) |
| GPT vs Llama | 0.67 (moderate) |

**Per-tier precision** (does HIGH consensus tier actually correspond to GENUINE?)
| Tier | Count | Truly GENUINE | Truly FP | % GENUINE |
|------|-------|---------------|----------|-----------|
| HIGH (3/3 GENUINE) | 11 | 11 | 0 | 100.0% |
| LIKELY (2/3 GENUINE) | 4 | 4 | 0 | 100.0% |
| LIKELY_FP | 1 | 0 | 1 | 0.0% |
| SUPPRESSED (3/3 FP) | 14 | 0 | 14 | 0.0% |

**Headline numbers**
- FP reduction rate: **100%** (15/15 true FPs correctly suppressed by consensus)
- TP retention rate: **100%** (15/15 true violations retained)
- Overall consensus accuracy: **100%** (30/30)

**Key narrative for the slides**: Llama alone scores 84.6% F1, missing 4 violations.
Consensus voting *rescues* those — GPT and DeepSeek catch them, so the joint vote labels
them LIKELY → still correct. **This is the multi-model value-add**: each model fails on
a different subset, consensus catches them all.

**Caveat**: dataset is small (n=30) and hand-crafted with strong contextual signals
(file paths, comments, sibling resources). The per-model differentiation (84-100% F1
range) and Cohen's kappa numbers (0.67-0.93) are the most defensible findings, since
they show real variance across models even on a curated set.

---

## Known Issues / Gotchas

1. **Windows file lock**: Close PowerPoint before running `python make_ppt.py`
2. **Checkov exe path**: `checkov_runner.py` uses `shutil.which()` + `sys.executable` fallback to find venv exe
3. **LLM non-determinism**: Fixed by SHA-256 mapping cache in `backend/mapping_cache/`
4. **Vite proxy**: `/evaluate` must be listed in `frontend/vite.config.js` proxy or 404 occurs
5. **Compliance score**: Was 100% bug — fixed in `db.py` to use unique failing clauses / total requirements
6. **Sadcloud timing**: Checkov scan takes ~26s on sadcloud; consensus LLM calls add ~60-90s more
7. **HCL extraction fallback**: `extract_resource_block` walks back to find `resource/module/data/provider/variable`. If no enclosing block is detected (rare — JSON/CloudFormation files), it falls back to a windowed snippet. Verdict quality degrades gracefully.
8. **Cache versioning**: `TASK_VERSION = "v3-fpfilter"` in `consensus.py`. Bump this any time the prompt or output schema changes so old cache entries are invalidated.

---

## What Is Still Left to Implement

### Done — FP-Filter Architecture Pivot

- ✅ `extract_resource_block()` in `checkov_runner.py` (walks back to `resource ... {`, balances braces)
- ✅ `scan_node` in `main.py` attaches `hcl_block` to each finding before cleanup
- ✅ `consensus.py` rewritten: GENUINE / FALSE_POSITIVE / UNCERTAIN classification with per-model
  verdict + clause + 1-line justification; cache invalidated via `TASK_VERSION = "v3-fpfilter"`
- ✅ `fp_annotations.json` — 30 hand-labeled (HCL + verdict) pairs across 13 distinct check_ids
- ✅ `eval_e2e.py` rewritten: per-model P/R/F1, Cohen's kappa, per-tier precision, FP reduction
  rate, TP retention rate, confusion matrices

### Critical Path Remaining

1. **Frontend tier surfacing**
   - `IssueCard.jsx` currently shows `models_agreed`/`models_disagreed` from old schema —
     adapt to display per-model verdicts (GENUINE / FP / UNCERTAIN) + 1-line `r` reason
   - Add a collapsed "N findings suppressed by consensus" section showing all-FP findings
   - HIGH = red, LIKELY = amber, UNCERTAIN = grey, SUPPRESSED = struck-through grey

2. **Frontend eval panel**
   - Surface latest `eval_e2e_results.json` numbers somewhere in the UI ("How is the
     model performing?" tab) — per-model F1, kappa, headline numbers

3. **Run on a real repo (terragoat / sadcloud) and inspect**
   - The fp_annotations eval is hand-curated. Need a sanity run against terragoat to see
     what `summary.suppressed` count looks like in practice; expect ~10-30% suppression on
     a real noisy scanner output

### Demo Polish

4. **Vis-network graph rendering**
   - `frontend/src/components/TraceGraph.jsx` imports `vis-network` but renders placeholder
   - Wire `new Network(containerRef.current, {nodes, edges}, options)`

5. **Fix-PR GitHub integration**
   - `IssueCard.jsx` has `alert('PR creation coming soon')` — needs `POST /pr` endpoint
     using PyGithub

6. **SSE streaming endpoint**
   - `/audit` is synchronous; frontend progress bar is fake
   - Add `GET /audit/stream` with SSE so verdicts appear per model in real time

7. **README update**
   - Still describes old Planner/Executor/Critic architecture
   - Should describe: distill_policy → Checkov detection → LLM FP-filter consensus

### Stretch

8. **Larger annotation set** — current n=30 is small for academic eval; aim for 80-100 pairs
   with more adversarial cases where context-reasoning is harder
9. **Multi-framework support** — run `distill_policy.py` on NIST SP 800-53 PDF
10. **History / version comparison view** — frontend UI for `/history` endpoint
11. **FAISS / vector search** — needed when policies grow beyond ~100 clauses
12. **`terraform validate` on generated fixes** — sandbox-verify the `/fix` diffs
13. **CI/CD webhook** — block PRs that introduce new HIGH violations
