# AuditTrace — Project Specs & Status Tracker

> Internal reference doc. Captures the CMPE 258 final project requirements verbatim
> alongside the current state of our deliverables, so we can see at a glance how we
> are doing against the rubric and what gaps still need to be closed before submission.

**Course:** CMPE 258 Deep Learning — SJSU Spring 2026
**Team:** Group 4
**Student of record:** Parth Gala (parth.gala@sjsu.edu)
**Repo:** https://github.com/ParthGala2k/AuditTrace
**Project Title:** AuditTrace — Multi-Agent LLM Consensus for IaC Compliance Auditing
**Project Track:** Application (system built on top of pre-trained LLMs + deterministic scanner)
**Focused Areas:** Multi-agent LLM systems · LLM-as-judge evaluation · Compliance/security tooling · Hybrid symbolic + neural architectures

---

## 1. Deliverables Required

| # | Deliverable | Format | Where it goes |
|---|---|---|---|
| 1 | Project Report | PDF | Uploaded directly to Canvas (Turnitin) |
| 2 | Software (code + supporting files) | GitHub link OR Google Drive folder | Link in Canvas |
| 3 | Video Demo | mp4 / Google Drive / unlisted YouTube | Link in Canvas |

All three must be coherent — the report describes what the code does, the code matches the
tables in the report, and the video demos the same system end-to-end. The rubric explicitly
states: *"A claimed feature counts as finished only if it is present in code, described in
the document, demonstrated in the video, and evaluated with clear evidence."*

---

## 2. Report Structure (required sections)

| § | Section | Required content | Status |
|---|---|---|---|
| 1 | Cover info | Team ID, title, members (name/SJSU ID/email), track, focused areas | ⏳ Need team ID + member roster |
| 2 | Abstract | 5–10 lines: problem, approach, key results | ⏳ Draft pending |
| 3 | Introduction & Problem | What we are solving, why it matters, target users | ⏳ Draft pending — strong story exists (Checkov firehose, FP triage) |
| 4 | Background / Related Work | Key refs: Checkov, CIS, OpenRouter, multi-agent LLM papers, LLM-as-judge lit | ⏳ Need bibliography |
| 5 | System / Model / Algorithm Design | Architecture diagram, components, techniques | ⚠️ Have prose; need a clean architecture figure |
| 6 | Implementation Details | Languages, frameworks, env, decisions, code link | ✅ Captured in `CLAUDE.md`; needs lift into report prose |
| 7 | Task Distribution & Contributions | Who did what, per section/feature | ⏳ Need to fill from team |
| 8 | Evaluation & Testing Results | Metrics, tables, plots, screenshots, reproducibility | ⚠️ Numbers exist (`eval_e2e_results.json`, `comparison_summary.json`); needs plots + screenshots |
| 9 | References | Papers, libs, models, tutorials, online materials | ⏳ Bibliography pending |

---

## 3. Rubric Breakdown (100 pts)

### 3.1 Project Document — 20 pts
> "Clearly document the selected application/algorithm/model/dataset, the overall
> architecture, key techniques, task distribution, key references, evaluation, and
> comparison results."

| Required item | Where we have it | Gap |
|---|---|---|
| Application/algorithm/model description | `CLAUDE.md` "Architecture" section | Lift into formal report prose |
| Dataset description | `evaluation/fp_annotations.json` (30 hand-labeled), `evaluation/test_cases.json` (55 planner cases), `policies/cis_aws_v7.json` (89 CIS controls) | Need a "Datasets" table in report |
| Overall architecture | Two-phase design (offline distill + runtime scan + consensus) in CLAUDE.md | Architecture diagram (draw.io / mermaid) |
| Key techniques | LangGraph orchestration, structured output, SHA-256 cache, brace-balanced HCL extraction, 3-way verdict consensus, Cohen's kappa | Document in §5 |
| Task distribution | None yet | Required — fill from team |
| Key references | OpenRouter, LangChain, LangGraph, Checkov, CIS Benchmark, Cohen 1960, LLM-as-judge papers | Bibliography |
| Evaluation & comparison results | Two eval suites already produce JSON: planner eval (3 models × 55 cases) and FP-filter eval (3 models × 30 cases) | Render as tables/plots in report |

### 3.2 Software Program & Implementation — 60 pts (HEAVIEST)
> "Clearly list the referenced solution/code, the identified solution is state-of-the-art
> not trivial implementations, demonstrated area of improvements, code structure/readme
> is easy to follow."

| Sub-requirement | Status | Evidence |
|---|---|---|
| Not a trivial implementation | ✅ | LangGraph 2-node pipeline, 3-model parallel consensus, FP-filter task is novel framing, brace-balanced HCL extraction, distilled policy spec, versioned audit storage |
| State-of-the-art ingredients | ✅ | GPT-4o-mini, DeepSeek V3, Llama 3.1 70B via OpenRouter; LangGraph; structured output; FAISS-ready (planned) |
| Demonstrated improvements | ✅ | The architecture pivot (clause-mapping → FP-filter) is documented with measured before/after rationale: precision was mathematically pinned at 100% before; now genuinely varies 84–100% F1 across models |
| Code structure | ✅ | Clear backend/agents, backend/tools, evaluation/, policies/, frontend/src layout |
| README | ⚠️ | Exists but describes OLD architecture (planner/executor/critic); must rewrite for FP-filter pipeline before submission |
| Runnable | ✅ | `uvicorn main:app --reload` + `npm run dev`; eval commands documented |
| Eval scripts/notebooks | ✅ | `evaluation/run_eval.py` and `evaluation/eval_e2e.py` produce reproducible JSON |
| Matches report tables | ⚠️ | Numbers exist; the report must cite the exact JSON outputs |

### 3.3 Video Demo — 20 pts
> "Clear description of the application/algorithm, all your members (show faces and
> voices), your project overview, and the functional flow of your project demo.
> Should not be just portrait views or screenshots of PPTs."

| Required item | Status |
|---|---|
| Landscape orientation | ⏳ TBD |
| Project intro (title, members, track) | ⏳ Script pending |
| Code & system overview (modules, file structure, how to run) | ⏳ Need to record screen walk-through |
| Final demo with representative inputs/outputs | ⏳ Plan: `terragoat` repo → live audit → show HIGH/LIKELY/SUPPRESSED tiers + per-model verdicts |
| Key results highlighted | ⏳ Show the eval panel numbers live |
| All members on camera + voice | ⏳ Group coordination |

---

## 4. What Counts as "Finished" (rubric verbatim)

A feature is **finished** only if it is:

1. ✅ Present in submitted code
2. ✅ Described in the written document
3. ✅ Demonstrated in the video
4. ✅ Evaluated with clear evidence

> *"If something appears in the code but is not demonstrated and evaluated, it will not
> be counted as a finished implementation."*

This is the bar we filter every feature against below.

---

## 5. Feature-by-Feature Finished-ness Audit

Mapping every implemented capability against the 4-criterion "finished" bar:

| Feature | In Code | In Report | In Video | Evaluated |
|---|---|---|---|---|
| CIS PDF distillation → 89 structured clauses | ✅ `backend/scripts/distill_policy.py` + `policies/cis_aws_v7.json` | ⏳ | ⏳ | ⚠️ Implicit (clauses load cleanly); could add a coverage table |
| Repo cloning + Checkov scan | ✅ `backend/tools/checkov_runner.py` | ⏳ | ⏳ | ✅ Latency timed in eval scripts |
| HCL block extraction (brace-balanced) | ✅ `extract_resource_block()` | ⏳ | ⏳ | ⚠️ Indirectly via FP-filter eval; could add ablation (with vs without context) |
| LangGraph 2-node pipeline | ✅ `backend/main.py` `build_graph()` | ⏳ | ⏳ | n/a (orchestration plumbing) |
| 3-model consensus (FP-filter) | ✅ `backend/agents/consensus.py` | ⏳ | ⏳ | ✅ `eval_e2e_results.json` (per-model P/R/F1, kappa, per-tier precision) |
| Planner benchmark (3 models × 55 cases) | ✅ `evaluation/run_eval.py` | ⏳ | ⏳ | ✅ `comparison_summary.json` (sev acc, type acc, F1, latency, cost) |
| SQLite versioned audits | ✅ `backend/db.py` | ⏳ | ⏳ | ⚠️ No formal eval; could time a 10-audit round trip |
| `/audit`, `/policies`, `/history`, `/fix` endpoints | ✅ `backend/main.py` | ⏳ | ⏳ | ✅ Latency captured in eval; functional smoke via `demo.py` |
| `/evaluate` endpoint | ⚠️ Exists but uses OLD schema — must be updated or deprecated for FP-filter | ⏳ | ⏳ | — |
| `/eval/fp-filter` + `/eval/planner` read endpoints | ❌ Not implemented yet (proposed) | ⏳ | ⏳ | — |
| Frontend audit UI (upload → run → results) | ✅ `frontend/src/App.jsx` + `components/` | ⏳ | ⏳ | n/a |
| Frontend per-model verdict surfacing | ⚠️ `IssueCard.jsx` still uses old `models_agreed` schema | ⏳ | ⏳ | — |
| Frontend eval panel | ❌ Not implemented yet | ⏳ | ⏳ | — |
| TraceGraph (vis-network) | ⚠️ Placeholder only | ⏳ | ⏳ | — |
| Fix generation `/fix` endpoint | ✅ Implemented | ⏳ | ⏳ | ⚠️ No formal eval of fix quality |
| Fix → PR GitHub integration | ❌ Stub `alert("coming soon")` | — | — | — |
| SSE streaming for live progress | ❌ Not implemented | — | — | — |
| Inter-model agreement (Cohen's kappa) | ✅ in eval | ⏳ | ⏳ | ✅ 0.67–0.93 across pairs |
| Per-tier precision (does HIGH = GENUINE?) | ✅ in eval | ⏳ | ⏳ | ✅ HIGH=100%, SUPPRESSED=0% genuine |
| FP reduction rate / TP retention rate | ✅ in eval | ⏳ | ⏳ | ✅ Both 100% on n=30 |

---

## 6. Pre-Submission Checklist (ordered by effort vs rubric weight)

### Must-do for full credit
1. **README rewrite** — describe FP-filter architecture, not old planner/executor/critic flow.
2. **Architecture diagram** — one figure showing CIS PDF → distill → policy JSON → repo → Checkov → per-finding HCL → 3 LLMs → verdict aggregation → tiered output. Embed in report and slide deck.
3. **Report draft** — populate all 9 required sections; lift numbers verbatim from `eval_e2e_results.json` and `comparison_summary.json`.
4. **Plots** — render at minimum: (a) per-model F1 bar chart, (b) Cohen's kappa heatmap, (c) per-tier precision bar chart, (d) latency vs cost scatter from planner eval. matplotlib script can live in `evaluation/plot_results.py`.
5. **Task-distribution table** — required by rubric; fill from team.
6. **Frontend tier surfacing** — adapt `IssueCard.jsx` to display per-model verdicts + reasons so the video demo *shows* multi-model consensus instead of just claiming it.
7. **Frontend eval panel** — fetch `/eval/fp-filter` + `/eval/planner` and render. Lets the video show the metrics live, satisfying "demonstrated and evaluated".
8. **Backend `/eval/*` read endpoints** — trivial 5-line additions, unblock #7.
9. **Video script + record** — landscape, all members on camera, walk through file structure, run an audit on terragoat, show suppressed findings, switch to eval panel, show the per-model numbers.
10. **Reproducibility commands** — concrete `cd / activate / run` lines for every result in the report. Currently captured in `CLAUDE.md` "How to Run"; lift verbatim into report §6.

### Nice-to-have (rubric mentions "demonstrated area of improvements")
11. **Ablation**: run FP-filter eval with HCL context stripped → show per-model F1 drops → proves HCL extraction matters.
12. **Larger annotation set** — extend `fp_annotations.json` from 30 → 60+ with harder adversarial cases. Strengthens the n in the report.
13. **Live audit screenshot** — terragoat → screenshot of tiered violations panel in the report.
14. **Cost/latency table** — already produced by planner eval; format cleanly in report.

### Explicitly out-of-scope for this submission (document as future work)
- TraceGraph vis-network rendering (placeholder only)
- Fix-PR GitHub integration
- SSE streaming endpoint
- NIST SP 800-53 multi-framework support
- FAISS vector search
- `terraform validate` on generated fixes
- CI/CD webhook
- History/version-diff view in UI

Listing these in the report's "Future Work" section is itself a deliverable item and shows scope awareness.

---

## 7. Reproducibility Quick-Reference

For the report's §8 "How to reproduce the results":

```powershell
# 1. Setup
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
# add OPENROUTER_API_KEY to backend/.env

# 2. Reproduce planner eval (3 models × 55 cases → comparison_summary.json)
python ..\evaluation\run_eval.py

# 3. Reproduce FP-filter eval (3 models × 30 cases → eval_e2e_results.json)
python ..\evaluation\eval_e2e.py

# 4. Run the live system
uvicorn main:app --reload
# in another shell:
cd ..\frontend && npm run dev

# 5. End-to-end demo (CLI)
cd ..
python demo.py --policy cis_aws_v7 --repo https://github.com/bridgecrewio/terragoat
```

Every number in the report must trace back to one of these commands.

---

## 8. Honest-Effort Posture

The rubric warns: *"Simply uploading AI-generated or unverified code without detailed
evaluation, testing results, and correctness verification will be ignored and may receive
very low or zero credit for the implementation portion."*

Our defenses:

- **Two independent eval suites** with hand-labeled ground truth (`fp_annotations.json`,
  `test_cases.json`) — not synthetic, not AI-generated.
- **Architectural pivot documented** — we identified that the original clause-mapping
  task produced mathematically forced 100% precision, diagnosed the cause, and rebuilt
  around the FP-filter framing. This is the kind of "demonstrated area of improvement"
  the rubric asks for.
- **Per-model variance is real** — F1 ranges 84.6% → 100%, kappa ranges 0.67 → 0.93,
  showing the three models actually disagree. Consensus is a real mechanism, not theater.
- **Reproducible** — every JSON in `evaluation/` is regenerable with one command, and
  the SHA-256 cache makes the numbers stable across reruns.
- **Honest caveats** — n=30 is small, annotations are hand-crafted with strong context
  signals, and we'll declare this openly in the report's limitations section.
