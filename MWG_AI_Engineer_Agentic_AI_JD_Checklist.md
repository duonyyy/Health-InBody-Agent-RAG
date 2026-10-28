# MWG — AI Engineer (Agentic AI)
## Job Description + Project Readiness Checklist for AI Agent Review

> **Company:** Mobile World Investment Corporation (MWG / Thế Giới Di Động)  
> **Role:** AI Engineer – Agentic AI  
> **Location:** Ho Chi Minh City, Vietnam  
> **Employment:** Full-time  
> **Reference date:** 2026-09-29  
> **Primary job page:** https://vieclam.thegioididong.com/tuyen-dung/ai-data-engineer-5000682  
> **Public mirror used for verification:** https://www.linkedin.com/jobs/view/ai-engineer-ai-data-engineer-at-mobile-world-investment-corporation-mwg-4469424324

---

# 1. Role Summary

MWG is looking for an **AI Engineer – Agentic AI** who can design, build, integrate, evaluate, deploy, and operate production-oriented AI Agent and LLM applications.

The role focuses heavily on:

- Agentic AI
- LLM applications
- RAG
- AI Search
- Tool / Function Calling
- Agent Workflow
- Agent State
- Memory
- Context Engineering
- MCP
- AI Evaluation
- Guardrails
- Observability
- Production AI systems

This is primarily an **Applied AI / LLM Engineering / Agent Engineering** role rather than a model-training-only research role.

---

# 2. Main Responsibilities

Use the IDs below when auditing a project.

## R1 — AI Agent & Agentic Workflow

The project should demonstrate the ability to design and implement AI Agents for real business tasks.

Possible evidence:

- Agent loop
- Graph/workflow
- Conditional routing
- Tool selection
- Multi-step execution
- Failure handling
- Human approval step

---

## R2 — Single-Agent & Multi-Agent Patterns

Relevant architectural patterns include:

- ReAct
- Router
- Planner–Executor
- Supervisor
- Human-in-the-Loop
- Single-Agent
- Multi-Agent

### Evidence to look for

- State graph
- Router node
- Planner
- Worker/Executor
- Supervisor
- Agent handoff
- Human approval node

---

## R3 — RAG / AI Search

The project should demonstrate practical experience with retrieval systems.

Expected concepts:

- Document ingestion
- Parsing
- Chunking
- Embedding
- Retrieval
- Semantic Search
- Reranking
- Hybrid Search
- Context Construction
- Retrieval filtering
- Top-K selection

### Strong evidence

```text
Document
   ↓
Parsing
   ↓
Chunking
   ↓
Embedding
   ↓
Vector Database

User Query
   ↓
Retriever
   ↓
Hybrid Search
   ↓
Reranker
   ↓
Context Construction
   ↓
LLM
```

---

## R4 — Integration with Enterprise Systems

Agents should be able to interact with systems outside the LLM.

Look for integration with:

- Internal APIs
- REST APIs
- Databases
- Search engines
- Business systems
- External services

### Evidence

- API clients
- Database repositories
- Service layer
- Authentication
- Tool adapters
- Integration tests

---

## R5 — Tool Calling / Function Calling / Structured Output

Expected capabilities:

- Tool Calling
- Function Calling
- JSON Schema
- Structured Output
- Input validation
- Output validation

### Strong evidence

Examples:

```python
class SearchInput(BaseModel):
    query: str
    top_k: int
```

or schemas/tool registries that allow an LLM to safely select and invoke tools.

---

## R6 — MCP Integration

Experience with **Model Context Protocol (MCP)** is preferred.

Possible evidence:

- MCP Server
- MCP Client
- Tools
- Resources
- Prompts
- stdio transport
- HTTP/SSE/streamable transport
- MCP-compatible internal service

---

## R7 — Agent State, Context & Memory

Expected knowledge:

- Agent State
- Conversation Context
- Short-term Memory
- Long-term Memory
- Context Engineering

### The project should distinguish

```text
Context = what the LLM sees now
State   = where the workflow currently is
Memory  = information retained for later use
```

### Evidence

- State object
- State persistence
- Conversation ID
- Checkpointing
- Redis/session store
- Memory retrieval
- Context builder

---

## R8 — AI Service / API Engineering

Expected stack:

- Python
- FastAPI
- REST
- gRPC

### Evidence

Look for:

```text
api/
routes/
schemas/
services/
middleware/
```

and production API concerns such as:

- request validation
- exception handling
- authentication
- timeout
- retry
- rate limiting
- async I/O

---

## R9 — AI Evaluation

The role explicitly values systematic AI evaluation.

Expected evaluation dimensions:

- Answer Quality
- Retrieval Quality
- Tool-call Accuracy
- Hallucination
- Task Completion
- Latency
- Cost

### Strong evidence

- Evaluation dataset
- Golden Dataset
- Automated evaluation script
- Retrieval metrics
- Task success metrics
- Tool-call tests
- LLM-as-a-Judge
- Regression testing
- Evaluation reports

---

## R10 — Guardrails & Security

Expected concepts:

- Guardrails
- Permission Control
- Validation
- Safe tool execution
- Human approval for risky actions

### Useful evidence

- PII filtering
- Prompt injection defenses
- Tool allowlist
- Role-based access
- Schema validation
- Output filter
- Human-in-the-loop confirmation
- Secret management

---

## R11 — Logging, Tracing & Observability

The project should ideally make LLM/Agent execution observable.

Look for:

- Logging
- Tracing
- Monitoring
- Token usage
- Latency metrics
- Tool traces
- Retrieval traces
- Error traces

Possible technologies:

- Langfuse
- LangSmith
- OpenTelemetry
- Custom tracing

---

## R12 — Production Optimization

The engineer should understand trade-offs among:

- Quality
- Latency
- Scalability
- Reliability
- Cost

Possible evidence:

- Caching
- Async execution
- Retry/backoff
- Timeout
- Rate limiting
- Fallback model
- Batch processing
- Connection pooling
- Load testing
- Performance benchmark
- Cost tracking

---

# 3. Required Qualifications

These should be treated as the **highest-priority audit criteria**.

## Q1 — Python

Expected:

- Strong Python fundamentals
- Clean code
- OOP where appropriate
- Type hints
- Error handling
- Async/await
- Package/module organization

---

## Q2 — Software Engineering

Look for:

- Clear architecture
- Separation of concerns
- Modular design
- Dependency management
- Configuration management
- Testing
- Logging
- Error handling

---

## Q3 — API Design

Expected familiarity with:

- REST API
- API schemas
- Authentication
- Validation
- Error responses
- Versioning
- Timeout/retry strategy

---

## Q4 — Distributed Systems Fundamentals

The project does not need to be a massive distributed platform, but evidence of understanding is useful.

Look for:

- Idempotency
- Retry
- Timeout
- Queue/event concepts
- Stateless services
- Cache
- Concurrency
- Failure handling

---

## Q5 — Practical LLM Application Experience

The project should use an LLM for more than a trivial one-prompt chatbot.

Strong examples:

- RAG
- Agent
- Tool Calling
- Workflow orchestration
- Evaluation
- Memory
- Structured Output

---

## Q6 — RAG / Embedding / Semantic Search / Vector Database

At least one meaningful implementation should exist.

Possible technologies:

- Qdrant
- Milvus
- pgvector
- Elasticsearch/OpenSearch
- FAISS
- Chroma

---

## Q7 — Agent / LLM Framework

Experience with at least one framework or SDK is useful.

Examples mentioned by the employer:

- LangGraph
- LangChain
- LlamaIndex
- OpenAI Agents SDK
- Semantic Kernel
- AutoGen
- CrewAI

The project does **not** need to use every framework.

---

## Q8 — Tool Calling + Structured Output

Must show practical use of:

- Tool definitions
- Function Calling
- JSON schema / typed schema
- Validation

---

## Q9 — State Management + Context Engineering + Memory

The Agent should not rely only on a giant raw chat history.

Look for deliberate management of:

- state
- conversation
- context
- retrieval context
- memory

---

## Q10 — REST API + SQL + Git + Docker

Expected baseline:

- REST API
- SQL database
- Git
- Docker

Check whether the repository includes:

```text
Dockerfile
docker-compose.yml / compose.yml
.gitignore
README.md
requirements.txt / pyproject.toml
```

---

## Q11 — Multi-step Agent Debugging

Project should make failures diagnosable.

Look for:

- trace IDs
- node logs
- exception handling
- tool errors
- retry policy
- workflow state visibility
- tests for failure cases

---

# 4. Preferred / Bonus Qualifications

These are useful differentiators but should **not automatically fail a project** if absent.

## P1 — MCP & Agent-to-Agent Communication

- MCP Server
- MCP Client
- Agent-to-Agent protocol
- Agent handoff

---

## P2 — Search / Vector Infrastructure

Employer-mentioned examples:

- Elasticsearch
- Milvus
- Qdrant
- pgvector

Equivalent systems are acceptable if they solve the same problem.

---

## P3 — Data / Infrastructure Components

Possible technologies:

- PostgreSQL
- Redis
- Kafka
- ClickHouse

---

## P4 — Self-hosted LLM Serving

Examples:

- vLLM
- SGLang

Evidence can include:

- local/self-hosted inference
- model server
- OpenAI-compatible endpoint
- batching/configuration

---

## P5 — Open-source Models

Examples mentioned:

- Qwen
- DeepSeek
- Llama

---

## P6 — LLM Observability

Examples:

- Langfuse
- LangSmith
- OpenTelemetry

---

## P7 — Kubernetes

Bonus if the project demonstrates:

- Deployment
- Service
- ConfigMap
- Secret
- Horizontal scaling
- Production container orchestration

Do not mark the whole project as unqualified only because Kubernetes is missing.

---

## P8 — AI Evaluation

Strong bonus:

- LLM-as-a-Judge
- Golden Dataset
- Regression Testing

---

## P9 — Real-user / Production Deployment

Strongest practical evidence includes:

- Deployed application
- Real users
- Production logs
- Metrics
- Monitoring
- CI/CD
- Real API / real database
- Failure handling
- Usage or evaluation report

---

# 5. Normalized Technology Checklist

An Agent auditing the project should search for these concepts.

## Core Language / Backend

- [ ] Python
- [ ] FastAPI
- [ ] REST
- [ ] gRPC
- [ ] Pydantic / schema validation
- [ ] Async programming
- [ ] SQL
- [ ] Git
- [ ] Docker

## LLM

- [ ] LLM API
- [ ] Prompt management
- [ ] Structured Output
- [ ] Function Calling
- [ ] Tool Calling

## RAG

- [ ] Document ingestion
- [ ] Parsing
- [ ] Chunking
- [ ] Embedding
- [ ] Retriever
- [ ] Semantic Search
- [ ] Vector Database
- [ ] Metadata filtering
- [ ] Hybrid Search
- [ ] Reranking
- [ ] Context Construction

## Agentic AI

- [ ] Agent loop
- [ ] ReAct
- [ ] Router
- [ ] Planner–Executor
- [ ] Supervisor
- [ ] Human-in-the-Loop
- [ ] Single-Agent
- [ ] Multi-Agent
- [ ] Agent State
- [ ] Memory
- [ ] Context Engineering

## MCP

- [ ] MCP Server
- [ ] MCP Client
- [ ] MCP Tools
- [ ] MCP Resources
- [ ] Agent-to-Agent communication

## Evaluation

- [ ] Golden Dataset
- [ ] Answer Quality
- [ ] Retrieval Quality
- [ ] Tool-call Accuracy
- [ ] Hallucination evaluation
- [ ] Task Completion
- [ ] Latency measurement
- [ ] Cost measurement
- [ ] LLM-as-a-Judge
- [ ] Regression Test

## Guardrails

- [ ] Input validation
- [ ] Output validation
- [ ] Permission control
- [ ] Safe tool execution
- [ ] Human approval
- [ ] PII protection
- [ ] Prompt injection defense

## Observability

- [ ] Logging
- [ ] Tracing
- [ ] Monitoring
- [ ] Langfuse
- [ ] LangSmith
- [ ] OpenTelemetry
- [ ] Token usage
- [ ] Latency tracking
- [ ] Error tracking

## Infrastructure

- [ ] PostgreSQL
- [ ] Redis
- [ ] Elasticsearch / OpenSearch
- [ ] Qdrant / Milvus / pgvector
- [ ] Kafka
- [ ] ClickHouse
- [ ] vLLM / SGLang
- [ ] Kubernetes

---

# 6. How an AI Agent Should Audit My Project

The auditing Agent must inspect the **actual repository**, not only README claims.

For every requirement, classify it as exactly one of:

```text
✅ MET
🟡 PARTIAL
❌ NOT MET
❓ NOT ENOUGH EVIDENCE
```

## Definitions

### ✅ MET

There is concrete implementation evidence in the repository.

Example:

```text
✅ RAG
Evidence:
- src/rag/retriever.py
- src/rag/reranker.py
- src/vector/qdrant_store.py
```

---

### 🟡 PARTIAL

The concept exists but is incomplete, trivial, or not production-ready.

Example:

```text
🟡 Evaluation

Current:
- manually tests 5 questions

Missing:
- golden dataset
- automated metrics
- regression tests
```

---

### ❌ NOT MET

No implementation exists after searching the repository.

---

### ❓ NOT ENOUGH EVIDENCE

It may exist externally, but the repository does not provide enough proof.

Example:

```text
❓ Production deployment

README says the app was deployed,
but no deployment config, URL, CI/CD,
logs, or infrastructure files were found.
```

---

# 7. Evidence Rules for the Auditing Agent

The Agent must **not hallucinate project capabilities**.

Every positive claim should contain evidence such as:

```text
file path
class name
function name
configuration
test
API route
Docker file
deployment manifest
evaluation result
```

Preferred evidence format:

```text
Requirement: Tool Calling
Status: ✅ MET

Evidence:
- src/agent/tools.py
- function `register_tools()`
- function `execute_tool_call()`
- schemas/tool_schema.py

Explanation:
The project exposes typed tools to the LLM and validates
arguments before executing them.
```

Do not give credit just because a dependency appears in:

```text
requirements.txt
package.json
pyproject.toml
```

A library should count only if it is meaningfully used.

---

# 8. Priority Levels

Use these priorities when proposing improvements.

## P0 — Must Have

These gaps can strongly affect readiness for this role.

- Python
- Software Engineering
- LLM application
- RAG / Retrieval
- Agent workflow
- Tool Calling
- Structured Output
- State / Context
- REST API
- SQL
- Git
- Docker

---

## P1 — Strongly Recommended

- Memory
- Hybrid Search
- Reranking
- Evaluation
- Guardrails
- Logging / Tracing
- Failure handling
- Redis
- Vector DB
- MCP

---

## P2 — Bonus

- Multi-Agent
- Agent-to-Agent
- Kafka
- ClickHouse
- vLLM
- SGLang
- Kubernetes
- Advanced distributed infrastructure

---

# 9. Suggested Audit Score

Use the score only as an internal readiness estimate.

```text
Core Required Skills      60 points
Production Engineering    20 points
Evaluation & Safety       10 points
Preferred Technologies    10 points
-------------------------------
Total                    100 points
```

Suggested interpretation:

```text
85–100  Strong project alignment
70–84   Good alignment; fix important gaps
55–69   Partial alignment; substantial work remains
<55     Project currently demonstrates only part of the role
```

A high score must not be given without implementation evidence.

---

# 10. Required Final Audit Output

The Agent should return the following structure.

## A. Executive Summary

```text
Overall readiness: XX/100

Strongest areas:
1.
2.
3.

Largest gaps:
1.
2.
3.
```

---

## B. Requirement Matrix

| ID | Requirement | Status | Evidence | Gap | Priority |
|---|---|---|---|---|---|
| Q1 | Python | | | | P0 |
| Q2 | Software Engineering | | | | P0 |
| Q3 | API Design | | | | P0 |
| Q4 | Distributed Systems | | | | P1 |
| Q5 | LLM Applications | | | | P0 |
| Q6 | RAG / Vector Search | | | | P0 |
| Q7 | Agent Framework | | | | P0 |
| Q8 | Tool Calling | | | | P0 |
| Q9 | State / Memory / Context | | | | P0 |
| Q10 | REST / SQL / Git / Docker | | | | P0 |
| Q11 | Workflow Debugging | | | | P1 |
| P1 | MCP / A2A | | | | P1 |
| P2 | Vector/Search infra | | | | P1 |
| P3 | Redis/Kafka/etc. | | | | P2 |
| P4 | Self-host LLM | | | | P2 |
| P6 | Observability | | | | P1 |
| P7 | Kubernetes | | | | P2 |
| P8 | AI Evaluation | | | | P1 |
| P9 | Production usage | | | | P1 |

---

## C. Architecture Assessment

Explain the current architecture using a compact diagram.

Example:

```text
Client
  ↓
FastAPI
  ↓
Agent
 ├── RAG
 ├── Tools
 ├── Memory
 └── LLM
  ↓
Response
```

Then identify architectural weaknesses.

---

## D. Missing Features to Implement

For every missing P0/P1 feature:

```text
Feature:
Why MWG cares:
Current project state:
Recommended implementation:
Files/modules to add or modify:
Estimated complexity: Low / Medium / High
```

---

## E. Top 5 Improvements Before Applying

Rank only the five changes with the highest impact.

Example:

```text
1. Add an automated evaluation pipeline
2. Add Langfuse tracing
3. Implement reranking
4. Add MCP integration
5. Add Docker Compose + Redis
```

The recommendations must be based on the actual repository.

---

## F. Interview Risk Areas

List concepts that are present in code but that the candidate may be asked to explain deeply.

Example:

```text
- Why Qdrant instead of pgvector?
- Why use LangGraph?
- How is Agent State persisted?
- What happens when a tool times out?
- How is hallucination measured?
- Why was chunk size chosen?
```

---

# 11. Prompt to Give Your Coding Agent

Copy the text below together with this file.

```text
You are acting as a Senior AI Engineer reviewing my repository
against the MWG AI Engineer – Agentic AI job description.

Read this entire JD/checklist first.

Then inspect my repository deeply.

Important rules:

1. Do not judge from README alone.
2. Inspect source code, configuration, tests, Docker files,
   API routes, schemas, services, deployment files and evaluation code.
3. Do not assume a feature exists just because a dependency is installed.
4. Every positive assessment must cite concrete evidence:
   file path, class, function, configuration or test.
5. Classify every requirement as:
   ✅ MET
   🟡 PARTIAL
   ❌ NOT MET
   ❓ NOT ENOUGH EVIDENCE
6. Prioritize missing P0 requirements first, then P1, then P2.
7. Do not recommend rewriting the whole project if an incremental
   improvement is sufficient.
8. Identify architecture and production-engineering weaknesses,
   not only missing AI features.
9. Pay special attention to:
   - RAG
   - Retrieval
   - Hybrid Search
   - Reranking
   - Agent workflow
   - Tool Calling
   - Structured Output
   - State
   - Memory
   - Context Engineering
   - MCP
   - Evaluation
   - Guardrails
   - Observability
   - FastAPI
   - SQL
   - Redis
   - Docker
   - failure handling
   - latency/cost/reliability
10. At the end, produce:
    A. Executive Summary
    B. Readiness score /100
    C. Requirement Matrix
    D. Current architecture diagram
    E. Missing P0/P1 capabilities
    F. Top 5 improvements before applying
    G. Interview risk areas
    H. Exact files/modules you recommend changing or adding.

Be strict. I want to know whether this repository provides
real evidence that I can perform this AI Engineer role.
```

---

# 12. Quick Definition of a Strong Matching Project

A particularly strong portfolio project for this role would roughly look like:

```text
                         Client
                           │
                           ▼
                        FastAPI
                           │
                    Auth / Guardrail
                           │
                           ▼
                         Agent
                           │
           ┌───────────────┼───────────────┐
           │               │               │
           ▼               ▼               ▼
          RAG           Tool/API         Memory
           │               │               │
   ┌───────┴────────┐      │             Redis
   │                │      │
Hybrid Search   Vector DB   │
   │                │      │
   └───────┬────────┘      │
           ▼               │
        Reranker           │
           └───────┬───────┘
                   ▼
                  LLM
                   │
           Structured Output
                   │
                Validator
                   │
                Response

────────────────────────────────────────────

Evaluation:
Golden Dataset
Retrieval Evaluation
Tool-call Accuracy
LLM-as-a-Judge
Regression Tests

Observability:
Tracing
Logs
Latency
Token Usage
Cost
Errors
```

The project does not need every optional technology in the JD.

The most important evidence is that the candidate understands how to build a **reliable, testable, observable, production-oriented LLM/Agent system**, not merely a chatbot demo.

---

# 13. Source Note

This document is a normalized, audit-oriented rewrite of the publicly available MWG recruitment information for the **AI Engineer – Agentic AI** role.

It is intentionally reorganized for project/repository assessment rather than copied verbatim.

Always re-check the live recruitment page before submitting an application because job requirements can change.
