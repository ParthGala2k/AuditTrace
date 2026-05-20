# AuditTrace

**Multi-Agent LLM Consensus for Infrastructure-as-Code Compliance Auditing**

> CMPE 258 Deep Learning — Final Project · SJSU Spring 2026

---

## Team

| Name | SJSU Email | GitHub |
|------|-----------|--------|
| Parth Gala | parth.gala@sjsu.edu | [@ParthGala2k](https://github.com/ParthGala2k) |

**Team ID:** Group 4
**Project Track:** Application
**Focused Areas:** Multi-agent LLM systems · LLM-as-judge evaluation · Compliance/security tooling · Hybrid symbolic + neural architectures

---

## TL;DR

AuditTrace combines a deterministic infrastructure-as-code scanner (Checkov) with a 3-LLM consensus filter that triages false positives using the surrounding Terraform context. On a hand-labeled set of 30 findings spanning 13 distinct Checkov rules:

| Metric | Value |
|---|---|
| Overall consensus accuracy | **100% (30/30)** |
| False-positive reduction | **100% (15/15)** |
| True-positive retention | **100% (15/15)** |
| Per-model F1 range | **84.6% → 100%** |
| Inter-model agreement (Cohen's κ) | **0.67 – 0.93** |
| Tier separation (HIGH = genuine, SUPPRESSED = FP) | **Perfect** |

Across a separate 55-case planner benchmark:

| Model | Type Acc. | Targets F1 | Latency | Cost/run |
|---|---|---|---|---|
| GPT-4o mini | 85.5% | 70.5% | **1.34 s** | $0.0022 |
| DeepSeek V3 | **90.9%** | **80.9%** | 7.15 s | **$0.0018** |
| Llama 3.1 70B | 90.9% | 79.2% | 3.04 s | $0.0057 |

All numbers are reproducible from one command (see [Reproducing the evaluations](#reproducing-the-evaluations)).

---

## Table of Contents

- [Problem & Approach](#problem--approach)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Quick Start](#quick-start)
- [Reproducing the evaluations](#reproducing-the-evaluations)
- [Running a live audit](#running-a-live-audit)
- [Interpreting the results](#interpreting-the-results)
- [API endpoints](#api-endpoints)
- [Models used](#models-used)
- [Evaluation methodology](#evaluation-methodology)
- [Demo deck & video](#demo-deck--video)
- [Task distribution & contributions](#task-distribution--contributions)
- [Limitations](#limitations)
- [Future work](#future-work)
- [References](#references)

---

## Problem & Approach

Static infrastructure-as-code scanners like Checkov produce a firehose of alerts. On `bridgecrewio/terragoat` (a deliberately vulnerable demo repo), Checkov fires **385 findings** — 211 high, 174 medium. None of those alerts have context: a public S3 bucket in a production module looks identical to a public bucket in a marketing static-site module.

**Key insight:** the LLM's job is not to detect violations — Checkov already does that perfectly. The LLM's job is to **judge** each finding given the surrounding code. We send each finding plus its enclosing Terraform block to three models running in parallel, and each model independently labels it `GENUINE`, `FALSE_POSITIVE`, or `UNCERTAIN`. We then take a consensus vote:

| Votes | Tier | Action |
|---|---|---|
| 3/3 GENUINE | HIGH | Prioritize fix |
| 2/3 GENUINE | LIKELY | Schedule fix |
| 1/3 GENUINE | UNCERTAIN | Manual review |
| 2/3 FALSE_POSITIVE | LIKELY_FP | Probably safe to dismiss |
| 3/3 FALSE_POSITIVE | SUPPRESSED | Auto-removed from violations list |

Because each model has a different blind spot, **the union of all three is significantly more accurate than any individual model**. On our test set, Llama alone scores 84.6% F1, but consensus voting reaches 100% accuracy.

---

## Architecture

```
                              ┌───────────────────────┐
                              │     CIS AWS PDF       │
                              │   (offline, once)     │
                              └───────────┬───────────┘
                                          │  GPT-4o-mini (per control)
                                          ▼
                              ┌───────────────────────┐
                              │  policies/cis_aws_v7  │
                              │   89 structured       │
                              │  ComplianceRequirements│
                              └───────────────────────┘

                          ─────────── per audit ───────────

  GitHub URL ─┬─► clone repo ─► Checkov ─► raw findings
              │
              │                              │
              │                              ▼
              │             ┌──────────────────────────────┐
              │             │ extract_resource_block()     │
              │             │ walks back to "resource ... {│
              │             │ balances braces, attaches    │
              │             │ HCL context to each finding  │
              │             └──────────────┬───────────────┘
              │                            │
              │           ┌────────────────┼────────────────┐
              │           ▼                ▼                ▼
              │   ┌─────────────┐  ┌─────────────┐  ┌──────────────┐
              │   │ GPT-4o mini │  │ DeepSeek V3 │  │ Llama 3.1 70B│
              │   └──────┬──────┘  └──────┬──────┘  └──────┬───────┘
              │          └────────────────┼────────────────┘
              │                           ▼
              │              consensus voting + tier assignment
              │                           │
              ▼                           ▼
       clone deleted              SQLite versioning ──► React UI
```

Two FastAPI nodes orchestrated by LangGraph:

- `scan_node` → clones repo, runs Checkov, attaches full Terraform block per finding, deletes the clone
- `consensus_node` → runs the 3-model FP-filter, aggregates verdicts, returns tiered output

Every model response is keyed by a SHA-256 hash of `(model · check_ids · clause_ids · HCL digest)` and cached on disk. Re-running an identical audit is instantaneous; only changed inputs trigger LLM calls.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Agent orchestration | [LangGraph](https://github.com/langchain-ai/langgraph) — 2-node StateGraph |
| LLM provider | [OpenRouter](https://openrouter.ai/) — unified OpenAI-compatible endpoint for GPT, DeepSeek, Llama |
| IaC scanner | [Checkov 3.x](https://www.checkov.io/) |
| PDF parsing | PyMuPDF |
| Backend | FastAPI + Uvicorn (Python 3.13) |
| Persistence | SQLite (audits + versions) |
| LLM determinism | SHA-256 prompt cache (`backend/mapping_cache/`) + temperature = 0 |
| Frontend | React 18 + Vite |
| Inter-model agreement | Cohen's κ (custom impl) |

No model is trained or fine-tuned. All three LLMs are off-the-shelf, accessed through a single OpenRouter API key.

---

## Project Structure

```
AuditTrace/
├── README.md                        ← you are here
├── PROJECT_SPECS.md                 ← rubric tracker (internal)
├── CLAUDE.md                        ← project context (internal)
├── AuditTrace_Presentation.pptx     ← demo deck
├── make_ppt.py                      ← regenerates the demo deck from eval JSONs
├── demo.py                          ← CLI: runs an audit end-to-end, pretty-prints results
│
├── backend/
│   ├── main.py                      ← FastAPI app + LangGraph pipeline
│   ├── db.py                        ← SQLite versioned-audit storage + compliance score
│   ├── agents/
│   │   ├── llm.py                   ← get_llm() factory → OpenRouter
│   │   ├── planner.py               ← (legacy) PDF → ComplianceRequirement
│   │   ├── consensus.py             ← FP-filter task: GENUINE / FALSE_POSITIVE / UNCERTAIN
│   │   └── executor.py              ← Finding dataclass
│   ├── tools/
│   │   ├── checkov_runner.py        ← Checkov subprocess + extract_resource_block()
│   │   └── pdf_parser.py            ← PyMuPDF chunking
│   ├── scripts/
│   │   └── distill_policy.py        ← one-time: CIS PDF → policies/*.json
│   └── requirements.txt
│
├── frontend/
│   ├── src/
│   │   ├── App.jsx                  ← main app + sticky header
│   │   ├── api.js                   ← fetch helpers
│   │   ├── tokens.js                ← design tokens + model labels
│   │   └── components/
│   │       ├── IssueCard.jsx        ← expandable violation card
│   │       ├── DiffBlock.jsx        ← git-style diff view
│   │       ├── SevChip.jsx          ← severity badge
│   │       ├── ScanProgress.jsx     ← progress bar
│   │       └── EvalPanel.jsx        ← live eval metrics panel
│   ├── vite.config.js               ← dev proxy (/audit, /eval, etc.)
│   └── package.json
│
├── policies/
│   └── cis_aws_v7.json              ← 89 distilled CIS AWS controls (committed; never regenerate)
│
└── evaluation/
    ├── fp_annotations.json          ← 30 hand-labeled GENUINE/FP pairs
    ├── test_cases.json              ← 55 planner test cases (CIS AWS)
    ├── eval_e2e.py                  ← FP-filter benchmark runner
    ├── run_eval.py                  ← planner benchmark runner
    ├── compute_metrics.py           ← shared P/R/F1 helpers
    ├── eval_e2e_results.json        ← latest FP-filter output
    ├── comparison_summary.json      ← latest planner comparison
    └── results_<model>.json         ← per-model planner detail
```

---

## Quick Start

### Prerequisites

- **Python 3.10+** (3.13 used for development)
- **Node.js 18+** and **npm**
- **Git**
- An **OpenRouter API key** — sign up free at https://openrouter.ai/

### One-time setup

```bash
git clone https://github.com/ParthGala2k/AuditTrace.git
cd AuditTrace
```

#### Backend

```bash
cd backend
python -m venv venv

# Windows PowerShell
.\venv\Scripts\Activate.ps1
# macOS / Linux
source venv/bin/activate

pip install -r requirements.txt

# Create .env in backend/ with the following lines:
#   OPENROUTER_API_KEY=sk-or-...
#   GITHUB_TOKEN=ghp_...    (optional; only needed for private repos)
#   LLM_MODEL=openai/gpt-4o-mini
```

#### Frontend

```bash
cd ../frontend
npm install
```

### Run the app

Open two terminals:

```bash
# Terminal 1 — backend
cd backend
.\venv\Scripts\Activate.ps1    # or `source venv/bin/activate`
uvicorn main:app --reload

# Terminal 2 — frontend
cd frontend
npm run dev
```

Open http://localhost:5173 in a browser. Paste a GitHub URL (try `https://github.com/bridgecrewio/terragoat`), select a policy, click **▶ run scan**.

---

## Reproducing the evaluations

Both eval suites are runnable in one command. They write deterministic JSON outputs that are committed to the repo, so you can diff against them after a re-run.

### FP-filter evaluation (30 hand-labeled cases)

```bash
cd backend
.\venv\Scripts\Activate.ps1
python ../evaluation/eval_e2e.py
```

Time: ~30–60 s cold cache, < 1 s warm cache.

Output:
- Console: per-model P/R/F1, Cohen's κ, per-tier precision, headline numbers
- File: `evaluation/eval_e2e_results.json`

Key sections of the JSON:

| Key | What it contains |
|---|---|
| `by_model_genuine_cls.<model>` | Per-model precision/recall/F1 with TP/FP/TN/FN counts (positive class = GENUINE) |
| `by_model_fp_cls.<model>` | Same but for the FALSE_POSITIVE class |
| `kappa.<pair>` | Cohen's κ for every pair of models on 3-way verdicts |
| `consensus_tiers.<tier>` | How many findings landed in each tier (HIGH / LIKELY / UNCERTAIN / LIKELY_FP / SUPPRESSED) |
| `by_tier.<tier>` | Per-tier ground-truth breakdown — how many are *actually* genuine vs FP |
| `fp_reduction_rate` | Fraction of true FPs that consensus correctly suppressed |
| `tp_retention_rate` | Fraction of true GENUINEs that consensus correctly retained |
| `overall_accuracy` | 30/30 = 1.0 means every case is in the correct tier |
| `errors` | Per-finding error list (id, truth, consensus, per-model verdicts) |

### Planner evaluation (55 CIS test cases × 3 models)

```bash
cd backend
.\venv\Scripts\Activate.ps1
python ../evaluation/run_eval.py
```

Time: ~3–7 min cold cache (165 LLM calls total). Cached re-runs are seconds.

Output:
- `evaluation/comparison_summary.json` — one row per model with the headline metrics
- `evaluation/results_<model>.json` — per-case detail including predicted vs expected fields, latency, token estimates

Headline metrics per model:

| Field | Meaning |
|---|---|
| `severity_accuracy` | Exact-match accuracy on the severity field (subjective; expected to vary) |
| `req_type_accuracy` | Exact-match on the requirement type label (access_control / encryption / etc.) |
| `avg_targets_f1` | Mean F1 across cases on the set of predicted Terraform target resources |
| `avg_latency_s` | Mean wall-clock latency per call |
| `total_tokens_est` | Total tokens consumed across all 55 cases |
| `estimated_cost_usd` | Total dollar cost using OpenRouter list prices |

### Cache management

LLM responses are cached on disk at `backend/mapping_cache/`. To force a fresh run:

```bash
# Windows
Remove-Item backend\mapping_cache\*.json
# macOS / Linux
rm backend/mapping_cache/*.json
```

The cache key includes a `TASK_VERSION` constant in `backend/agents/consensus.py` — bump it any time you change the prompt or schema so older entries are auto-invalidated.

---

## Running a live audit

Two paths.

### From the browser

1. Start backend + frontend (see [Quick Start](#quick-start))
2. Open http://localhost:5173
3. Paste a GitHub URL — for example `https://github.com/bridgecrewio/terragoat`
4. Select **cis_aws_v7** from the policy dropdown
5. Click **▶ run scan**

The first run on a repo takes 20–40 minutes (Checkov scan + ~50 LLM calls). The cache makes subsequent runs of the same repo seconds.

When the scan finishes:
- Each finding is an **IssueCard** showing the violated clause, severity chip, and per-model verdicts
- Click a card to expand and view an LLM-generated Terraform fix diff
- Click **📊 show eval** in the header to overlay the live evaluation panel

### From the CLI

```bash
python demo.py --policy cis_aws_v7 --repo https://github.com/bridgecrewio/terragoat
```

Pretty-prints tier counts, top violations, and the compliance score.

---

## Interpreting the results

### A finding object

```json
{
  "clause_id":      "CIS-2.1.1",
  "clause_text":    "Ensure all S3 buckets prohibit public read access",
  "check_id":       "CKV_AWS_20",
  "file":           "terragoat/aws/s3.tf",
  "line":           [12, 22],
  "resource":       "aws_s3_bucket.public",
  "severity":       "high",
  "confidence":     "HIGH",
  "consensus_score": 3,
  "per_model": {
    "openai/gpt-4o-mini":              {"v": "GENUINE", "c": "CIS-2.1.1", "r": "ACL is public-read in prod"},
    "deepseek/deepseek-chat":          {"v": "GENUINE", "c": "CIS-2.1.1", "r": "S3 bucket exposed publicly"},
    "meta-llama/llama-3.1-70b-instruct":{"v": "GENUINE", "c": "CIS-2.1.1", "r": "Public-read ACL on bucket"}
  }
}
```

| Field | Meaning |
|---|---|
| `confidence` | One of **HIGH / LIKELY / UNCERTAIN / LIKELY_FP / SUPPRESSED** |
| `consensus_score` | Number of models that voted GENUINE (0–3) |
| `per_model[m].v` | The model's verdict — `GENUINE`, `FALSE_POSITIVE`, or `UNCERTAIN` |
| `per_model[m].c` | The CIS clause the model thought the finding violated (secondary signal) |
| `per_model[m].r` | The model's 1-line reason (free text) |

Items where all three models said FALSE_POSITIVE are placed under `summary.suppressed` and not shown in the main violations list — the user can expand them if curious.

### A consensus tier breakdown

```
HIGH        — 3/3 GENUINE       — high signal, fix first
LIKELY      — 2/3 GENUINE       — likely real, review
UNCERTAIN   — 1/3 GENUINE       — split decision, manual triage
LIKELY_FP   — 2/3 FALSE_POSITIVE — probably noise, but keep visible
SUPPRESSED  — 3/3 FALSE_POSITIVE — auto-removed from violations
```

On our evaluation set, every HIGH item was actually genuine and every SUPPRESSED item was actually a false positive — the tier name is predictive of ground truth.

### Reading the eval panel

The frontend **EvalPanel** (top-right `📊 show eval` button) loads the latest `eval_e2e_results.json` and `comparison_summary.json` from disk and renders:

- **Three headline tiles** — per-model F1 range, Cohen's κ range, joint consensus accuracy
- **Per-model GENUINE-class table** — P, R, F1, plus TP/FP/TN/FN counts
- **Per-model FALSE_POSITIVE-class table** — same metrics with FP as the positive class
- **Cohen's κ bars** — pairwise agreement with Landis & Koch interpretation legend
- **Per-tier precision bars** — does the HIGH tier actually mean genuine?
- **Planner benchmark table** — type accuracy, targets F1, severity accuracy, latency, cost per model

The panel is read-only — to refresh after a new eval run, click the **↻ refresh** button (no audit re-run required).

---

## API endpoints

| Method | Path | Purpose |
|---|---|---|
| POST | `/audit` | Full audit pipeline. Form fields: `repo_url`, `policy`, `models` |
| POST | `/fix` | LLM-generated Terraform diff for one violation |
| POST | `/evaluate` | Legacy metrics against Checkov ground truth (deprecated by the eval panel) |
| GET | `/policies` | List distilled policy specs from `policies/` |
| GET | `/history?repo_url=…` | Versioned audit history for a repo |
| GET | `/history/report?repo_url=…&version=N` | Full report for a specific audit version |
| GET | `/eval/fp-filter` | Latest FP-filter eval JSON (powers the EvalPanel) |
| GET | `/eval/planner` | Latest planner benchmark JSON (powers the EvalPanel) |
| GET | `/health` | `{"status": "ok"}` |

Interactive Swagger docs: http://localhost:8000/docs when the backend is running.

---

## Models used

All three LLMs are accessed through OpenRouter — one API key, three different providers.

| Model | OpenRouter ID | Open-source | Role in consensus |
|---|---|---|---|
| GPT-4o mini | `openai/gpt-4o-mini` | Closed | Default; fastest |
| DeepSeek V3 | `deepseek/deepseek-chat` | **Open** | Cheapest; best on type/targets |
| Llama 3.1 70B Instruct | `meta-llama/llama-3.1-70b-instruct` | **Open** | Best on severity; under-flags genuine violations |

Two of the three are open-source, satisfying the rubric requirement that at least one model be open-source.

All three are off-the-shelf — no fine-tuning, no training, no RLHF on top.

---

## Evaluation methodology

Two independent benchmark suites with hand-labeled ground truth, no synthetic data:

### Suite 1 — FP-Filter (`evaluation/fp_annotations.json`)

- **n = 30** hand-curated findings
- **15 GENUINE + 15 FALSE_POSITIVE**, balanced
- **13 distinct Checkov check IDs** spanning S3, IAM, RDS, EBS, VPC, ELB, CloudTrail
- Each entry: `check_id` + `resource` + `file_path` + real HCL block + correct verdict + rationale
- Adversarial design: pairs that share the same `check_id` but differ in context (e.g. public bucket in prod vs marketing static site)

Metrics computed:
- Per-model **precision / recall / F1** on the `GENUINE` class
- Per-model **precision / recall / F1** on the `FALSE_POSITIVE` class
- **Cohen's κ** between every pair of models on 3-way verdicts
- **Per-tier precision** — for each consensus tier, what fraction are actually genuine
- **FP reduction rate** — fraction of true FPs that consensus correctly suppressed
- **TP retention rate** — fraction of true GENUINEs that consensus correctly kept

### Suite 2 — Planner benchmark (`evaluation/test_cases.json`)

- **n = 55** test cases derived from the CIS AWS Foundations Benchmark
- Input: a policy clause text
- Expected output: `{severity, requirement_type, check_targets}` triple

Metrics computed:
- **Severity accuracy** — exact match
- **Requirement-type accuracy** — exact match on category label
- **Targets F1** — set overlap on Terraform resource types
- **Latency, tokens, cost** — wall-clock + token estimate × OpenRouter list price

### Why these are defensible

- Annotations are **real Terraform from open-source repos**, not synthetic
- Each item is **deliberately context-dependent** — designed to require reasoning Checkov cannot do
- **SHA-256 cache** makes every number deterministic and reproducible
- **Versioned `TASK_VERSION` constant** ensures the cache is invalidated whenever prompt or schema changes

### Honest caveats

- **n = 30 is small** for the FP-filter set. The per-model F1 spread (84.6% → 100%) and κ range (0.67 → 0.93) are the load-bearing findings; the 100% consensus accuracy is partly an artifact of dataset size and quality.
- Severity accuracy in the planner benchmark looks low across the board (38–51%) — this is because severity is the most subjective field in the ground truth. Type accuracy and Targets F1 are the more objective signals.
- The eval set is hand-curated by one annotator. Scaling to 80–100 adversarial pairs with multi-annotator agreement is in the future-work list.

---

## Demo deck & video

- **Demo video:** https://youtu.be/3yNg2zou0WI
- **`AuditTrace_Presentation.pptx`** — 12-slide deck, all numbers pulled directly from the eval JSONs. Regenerable with `python make_ppt.py`.
- **`make_ppt.py`** — reads `eval_e2e_results.json` and `comparison_summary.json`, produces the deck programmatically.

Slide outline:

1. Title
2. The Problem (Checkov firehose, 385 findings on terragoat, no context)
3. Our Approach (Detect → Judge → Vote)
4. System Architecture
5. How We Evaluated (two test suites)
6. FP-Filter Results — three contrasting numbers (per-model F1 range, κ range, joint accuracy)
7. The Multi-Model Rescue (each model's distinct failure mode)
8. Disagreement + Tier Separation (κ table + tier counts)
9. Planner Benchmark (accuracy vs latency vs cost tradeoff)
10. Live System (terragoat run results)
11. Limitations & Future Work
12. Summary

---

## Task distribution & contributions

| Component | Contributor |
|---|---|
| Backend pipeline (`main.py`, `consensus.py`, `checkov_runner.py`, `db.py`) | Parth Gala |
| Frontend (`App.jsx`, components, `EvalPanel.jsx`, design system) | Parth Gala |
| Evaluation suite (`eval_e2e.py`, `run_eval.py`, `compute_metrics.py`) | Parth Gala |
| Hand-labeled annotation set (`fp_annotations.json`) — 30 entries across 13 check IDs | Parth Gala |
| CIS AWS policy distillation | Parth Gala (via `distill_policy.py`) |
| Demo deck (`make_ppt.py`) | Parth Gala |

Single-author project (Group 4).

---

## Limitations

- **Single framework** — only CIS AWS today. NIST SP 800-53, SOC 2, PCI-DSS are not yet wired in.
- **Single IaC dialect** — HCL/Terraform only. CloudFormation and Kubernetes manifests are detected by Checkov but the HCL-extraction fallback degrades for them.
- **No fix verification** — `/fix` returns an LLM-generated diff; we do not run `terraform validate` on it.
- **Cold-start latency** — first audit of a new repo with N findings is roughly `N / 25 × 30s × 3` models. ~20–40 minutes for terragoat. Cached re-runs are instant.
- **Annotation set size** — n = 30 is small; the headline 100% accuracy depends on dataset size, not just model quality.
- **No fine-tuning** — we use off-the-shelf LLMs. A fine-tuned classifier might outperform any single model in the consensus, but would lose the multi-model rescue property.

---

## Future work

- Expand `fp_annotations.json` to 80–100 adversarial pairs with multi-annotator agreement
- Distill NIST SP 800-53, SOC 2, PCI-DSS PDFs alongside CIS
- CloudFormation + Kubernetes support — generalize `extract_resource_block` beyond HCL
- Validate generated fix diffs with sandboxed `terraform validate` / `terraform plan`
- FAISS vector search over policy clauses (currently fits in context; needed once policies grow > 100)
- SSE streaming endpoint so the frontend progress bar reflects real per-model state
- GitHub Fix-PR creation via PyGithub (button currently shows "coming soon")
- CI/CD webhook: block PRs that introduce new HIGH-tier violations
- Larger-scale eval against a real engineering team's triage decisions (out-of-domain)

---

## References

1. **Checkov** — Bridgecrew / Prisma Cloud. https://www.checkov.io/
2. **CIS AWS Foundations Benchmark v3.0** — Center for Internet Security. https://www.cisecurity.org/benchmark/amazon_web_services
3. **LangGraph** — LangChain Inc. https://github.com/langchain-ai/langgraph
4. **OpenRouter** — unified LLM API gateway. https://openrouter.ai/docs
5. Cohen, J. (1960). *A coefficient of agreement for nominal scales*. Educational and Psychological Measurement, 20(1), 37–46.
6. Landis, J. R., & Koch, G. G. (1977). *The measurement of observer agreement for categorical data*. Biometrics, 33(1), 159–174.
7. **PyMuPDF** — Artifex. https://pymupdf.readthedocs.io/
8. **FastAPI** — Sebastián Ramírez. https://fastapi.tiangolo.com/
9. Llama 3.1 model card — Meta AI, July 2024.
10. DeepSeek V3 — DeepSeek AI, 2024.
11. GPT-4o mini — OpenAI, July 2024.
12. **bridgecrewio/terragoat** — deliberately vulnerable Terraform demo repo. https://github.com/bridgecrewio/terragoat

---

## License

Academic project — distributed for educational purposes. See repository for any updates.
