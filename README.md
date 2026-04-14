# AuditTrace — Autonomous Compliance Auditing with Multi-Agent AI

> **CMPE 258 Deep Learning — Final Project**
> San Jose State University · Spring 2026

---

## Team

| Name | GitHub |
|------|--------|
| Parth Gala | [@ParthGala2k](https://github.com/ParthGala2k) |
| *(add teammates)* | *(add handles)* |

**Team ID:** *(add your team ID)*

---

## Project Overview

AuditTrace is a full-stack, multi-agent AI system that automates the entire compliance audit lifecycle:

1. **Upload** a compliance PDF (e.g. SOC 2, NIST 800-53, internal security policy).
2. **Connect** a GitHub repository that contains infrastructure-as-code (Terraform, CloudFormation, Kubernetes).
3. **Planner Agent** decomposes the PDF into structured technical requirements using an LLM.
4. **Executor Agent** clones the repo and runs [Checkov](https://www.checkov.io/) + Terraform Plan to scan the live infrastructure.
5. **Critic Agent** generates a **Compliance Trace** — a directed graph showing exactly which line of code violates which policy clause — and drafts a **Fix-PR** patch for each violation.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Frontend (React)                      │
│   PDF Upload  ──►  GitHub URL  ──►  Trace Graph  ──►  Fixes │
└────────────────────────────┬────────────────────────────────┘
                             │ REST (FastAPI)
┌────────────────────────────▼────────────────────────────────┐
│                    LangGraph Pipeline                        │
│                                                              │
│  [Planner Agent]──►[Executor Agent]──►[Critic Agent]         │
│   PDF→Requirements   Checkov scan      Trace + Fix-PR        │
└─────────────────────────────────────────────────────────────┘
```

### Agent Roles

| Agent | Input | Output |
|-------|-------|--------|
| **Planner** | PDF text chunks | `List[ComplianceRequirement]` |
| **Executor** | Requirements + GitHub repo | `Dict[clause_id → List[Finding]]` |
| **Critic** | Findings map | Compliance trace graph + Fix-PR diffs |

---

## Dataset / Inputs

- **Compliance PDFs:** SOC 2 Type II, NIST SP 800-53, CIS Benchmarks, custom internal policies.
- **Infrastructure repos:** Public Terraform / CloudFormation / Kubernetes repos for testing.
- **Reference benchmarks:** [ComplianceAsCode/content](https://github.com/ComplianceAsCode/content) for ground-truth policy mappings.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Agent orchestration | [LangGraph](https://github.com/langchain-ai/langgraph) |
| LLM | OpenAI GPT-4o / GPT-4o-mini |
| PDF parsing | PyMuPDF |
| Infrastructure scanning | [Checkov](https://www.checkov.io/) |
| GitHub integration | PyGithub |
| Backend API | FastAPI |
| Frontend | React + Tailwind CSS |
| Graph visualization | vis-network / D3.js |

---

## Current Progress

- [x] Repository scaffolding and project structure
- [x] PDF text extraction and section chunking (`backend/tools/pdf_parser.py`)
- [x] Checkov runner with repo cloning (`backend/tools/checkov_runner.py`)
- [x] Planner Agent stub with LangChain prompt (`backend/agents/planner.py`)
- [x] Executor Agent — Checkov integration + requirement mapping (`backend/agents/executor.py`)
- [x] Critic Agent — compliance trace graph (NetworkX) + fix generation (`backend/agents/critic.py`)
- [x] LangGraph pipeline wiring Planner → Executor → Critic (`backend/main.py`)
- [x] FastAPI `/audit` endpoint
- [x] React frontend skeleton with upload panel and violations table
- [ ] Structured JSON output from Planner (parser integration)
- [ ] Semantic similarity matching for findings → requirements
- [ ] vis-network graph rendering in the frontend
- [ ] GitHub PR creation via API
- [ ] End-to-end demo with real compliance PDF

---

## Next Steps

1. **Week 1:** Wire LangChain `JsonOutputParser` into the Planner; test against a SOC 2 PDF.
2. **Week 2:** Implement embedding-based semantic matching in the Executor; integrate vis-network graph in the frontend.
3. **Week 3:** Build the GitHub Fix-PR creation flow; polish the UI; run end-to-end demo.
4. **Week 4:** Evaluation — measure precision/recall of requirement extraction vs. human-annotated ground truth.

---

## Running Locally

```bash
# Backend
pip install -r requirements.txt
cp .env.example .env   # fill in OPENAI_API_KEY and GITHUB_TOKEN
cd backend
uvicorn main:app --reload

# Frontend
cd frontend
npm install
npm run dev
```

---

## References

1. RepoAudit: An Autonomous LLM-Agent for Repository-Level Code Auditing — arXiv:2501.18160
2. GraphRAG for Legal Norms: A Hierarchical Approach — arXiv:2505.00039
3. [ComplianceAsCode/content](https://github.com/ComplianceAsCode/content)
4. [Bridgecrew Checkov](https://www.checkov.io/)
5. [LangGraph Framework](https://github.com/langchain-ai/langgraph)
