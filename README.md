# 🚀 AI Interview Evaluation Platform 

A stateful technical interview system with structured evaluation, human feedback loops, prompt versioning, and A/B comparison of agent behavior.


## 🏆Assignment Coverage — Complete Implementation 

This submission **fully implements all required, expected, and multiple bonus components** of the assignment with a production-grade design.

---

## ✅ Must Have Requirements (Fully Covered)

- Stateful interview agent (FSM-based): ✔
  multi-step flow → `ask → evaluate → clarify → next question`
- End-to-end interview execution (3 questions per skill) ✔
- Deployable interface (FastAPI) ✔
- Feedback submission (ratings, flags, comments — persisted) ✔
- Conversation retrieval (full history with evaluation + prompt version) ✔
- Prompt loading from configurable source (DB-driven) ✔
- Test coverage: ✔
  - FSM transitions  
  - resilience cases  
  - prompt loading  
- Complete README + setup + demo walkthrough ✔

---

## 🚀 Expected (Production-Level Features) — Fully Covered

- Containerized deployment (Docker + Docker Compose) ✔
- Conversation discovery & filtering (skill, status, prompt version) ✔
- Prompt versioning & traceability ✔
- Error handling & resilience: (invalid input, missing responses, LLM failures) ✔
- Basic observability: (health endpoint, structured logs)  ✔

## ⭐ Bonus (Additional Enhancements)

- A/B comparison of conversations (side-by-side evaluation) ✔
- Feedback aggregation ✔
- Prompt management UI (create + activate versions) ✔
- Automated prompt improvement suggestions ✔
- Mock LLM mode (no API key required — reviewer friendly) ✔
- Real LLM mode (OpenAI integration) ✔
- Docker Hub deployment (ready-to-run image) ✔


## ✨ Overview

This project implements an end-to-end conversational interview agent and a production feedback loop for human evaluators.

It supports:

- A stateful, multi-step interview agent
- Fixed skills and question banks
- Answer evaluation and clarification
- Persisted conversation history
- Human evaluator feedback
- Prompt versioning and activation
- A/B comparison of conversations / prompt versions
- Basic observability
- Mock LLM mode and real OpenAI mode
- Containerized execution with Docker

## 🎯 Key Features

### 🧠 Architecture & Design Choice:

The interview system is implemented as a **single agent backed by a Finite State Machine (FSM)**.

### Why FSM-based design?

The FSM provides:

- **Deterministic behavior**
-  **Testability** (state transitions can be unit tested)
- **Resilience** (graceful handling of invalid input and retries)
- **Separation of concerns** (evaluation, clarification, and flow control are distinct)

### Why a single agent (vs multiple agents)?

A multi-agent architecture was considered but not chosen because:
- The problem scope is well-structured and sequential
- FSM already provides sufficient modularity
- A single agent reduces complexity while maintaining clarity

### Final Decision

A **single FSM-driven agent** strikes the right balance between:
- Simplicity
- Control  
- Scalability  
- Production readiness

This design is closer to real-world conversational systems used in structured workflows.

Typical flow:

```text
start -> select skill -> ask question -> wait for answer -> triage input -> evaluate answer -> clarify / next question -> wrap up -> end
```
---

## 📏 Scope & Assumptions

To keep the system focused, testable, and aligned with the assignment timeline, the following scope decisions and assumptions were made:

### 🎯 Interview Scope

- Each interview covers **exactly one skill**
- Each skill contains **3 predefined questions**.
- The question bank is **static and controlled** (not dynamically generated)
  
**Reasoning:**  
This ensures consistency across interviews and enables reliable comparison between prompt versions.

---

### 🔄 Clarification Strategy

- The agent allows a **limited number of clarification attempts per question**
- If the candidate repeatedly provides weak answers, the system moves forward
  
**Reasoning:**  
Prevents infinite loops and maintains a realistic interview flow.

---

### 🧑‍⚖️ Evaluator Scope
- Assumes a **small number of evaluators (admins)**
- No complex authentication/authorization system (e.g., roles, permissions)

**Reasoning:**  
Focus is on feedback workflow, not user management systems.

---

### 📝 Feedback Design
- Feedback includes:
  - overall rating  
  - fairness  
  - relevance  
  - flags  
  - optional comments  

**Reasoning:**  
Provides sufficient signal for evaluation without overcomplicating the schema.

---

### 🤖 LLM Scope

#### ✅ Mock LLM (Default)
- No API key required
- Deterministic responses
- Best for reviewers

#### 🔥 Real LLM (OpenAI)
- Uses OpenAI API
- Better evaluation quality
- Controlled via `.env`

**Reasoning:**  
Ensures the system is both testable and realistic.

---

### 💾 Persistence Scope

- Uses **SQLite**
- Data stored locally within the application

**Reasoning:**  
Simple, portable, and requires zero setup for reviewers.

---

### 📊 Observability

- /health endpoint

👉 [http://localhost:8000/health](http://localhost:8000/health)

- structured logs
  
👉 visible in terminal whether MockLLM or Real LLM system activated

**Reasoning:**  
Provides basic production visibility without adding heavy monitoring systems.

---

## 🎯 Summary

These scope decisions ensure the system is:

- Focused on core problem ✔ 
- Easy to test and review ✔ 
- Production-oriented in design ✔ 
- Aligned with assignment goals ✔ 

while avoiding unnecessary complexity.


---

🧑‍⚖️ Human Feedback Loop

Evaluators can:

- Discover conversations by ID, date, skill, status, prompt version, and review state
- View full conversation details
- Submit ratings (Overall, Fairness, Relevance)
- Flag issues (weak evaluation, bias, inappropriate question,generic clarification)
- Compare two conversations side by side
- Record (A/B/Tie) prompt preferences
- Inspect version-level preference summaries

### 🔄 Prompt Versioning

- Prompts stored with versions (`v1`, `v2`, `v3`)
- Each conversation records the version used
- Easy switching of active prompt
- Enables iterative improvement

---

## 🛠️ Tech Stack

- **Backend:** FastAPI  
- **Database:** SQLite + SQLAlchemy  
- **Templating:** Jinja2  
- **LLM:** OpenAI (optional)  
- **Testing:** Pytest  
- **Deployment:** Docker & Docker Compose  

---

## 📁 Project Structure

## Project Structure

- `app/` – Main application code
  - `app/agent/` – Finite‑state machine, state logic, and enums
  - `app/services/` – Interview business logic and domain services
  - `app/llm/` – Mock and real LLM services (client wrappers)
  - `app/prompts/` – Prompt templates, loaders, and versions
  - `app/db/` – Database models and ORM definitions
  - `app/admin/` – Admin routes and simple admin UI
  - `app/core/` – Configuration, settings, and shared utilities
  - `app/ui/` – HTML templates (server‑rendered views)

- `tests/` – Unit and integration tests
- `Dockerfile`, `docker-compose.yml` – Container definitions
- `requirements.txt` – Python dependencies
- `.env` – Environment variables template
- `README.md` – This file

---

## ⚙️ Setup

### 🖥️ Option 1: Run Locally

```bash
git clone https://github.com/Anvesh1826216/interview-agent-feedback-loop.git
cd interview-agent-feedback-loop
python -m venv .venv
.venv\Scripts\activate   # Windows
pip install -r requirements.txt
uvicorn app.main:app --reload
```
---

### 🐳 Option 2: Run with Docker (Recommended)

```bash
git clone https://github.com/Anvesh1826216/interview-agent-feedback-loop.git
cd interview-agent-feedback-loop
docker compose up --build
```

Open the app at:
👉 [http://localhost:8000](http://localhost:8000)

---

### 📦 Run from Docker Hub

```bash
docker pull meher1826216/interview-agent:latest
docker run --env-file .env -p 8000:8000 meher1826216/interview-agent:latest
```
---

### 🔑 Environment Configuration (.env)

```bash
USE_MOCK_LLM=true
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4o-mini
SESSION_SECRET_KEY=change-me
ADMIN_USERNAME=admin
ADMIN_PASSWORD=admin@12345
```
---

### Real LLM Mode 🔥

```bash
USE_MOCK_LLM=false
OPENAI_API_KEY=your_api_key
```
---

### 🧪 Running Tests
```bash
python -m pytest -v
```
---

### 🔐 Admin Access

👉 [http://localhost:8000/login](http://localhost:8000/login)

Default credentials:

```bash
admin / admin@12345
```
---

# 🎬 Demo Walkthrough (Reviewer Guide)

### 1️⃣ Start the system

```bash
docker compose up --build
```
---

### 2️⃣ Run an interview

👉 [http://localhost:8000](http://localhost:8000)

Click Take Interview

---

### 3️⃣ Example answers (Problem Solving)

```bash
Q1:
I solved a backend issue by debugging logs, identifying incorrect validation, fixing logic, and validating results.

Q2:
I break problems into smaller parts, identify unknowns, and validate each step.

Q3:
My first solution failed due to wrong assumptions. I improved validation and redesigned the logic.
```

---

### 4️⃣ View conversation

👉 /admin/conversations

click view to submit feedback

---

### 5️⃣ Submit feedback

Example:

- Overall: 4
- Fairness: 4
- Relevance: 4
- Flags: weak evaluation

---

### 6️⃣ Feedback Summary

👉 /admin/feedback-summary

---

### 7️⃣ Suggested Prompt Improvements 

Generated by LLM after receiving the feedback summary

👉 /admin/prompt-suggestions

---

### 8️⃣  Manage/Update Prompts 

Based on Human feedback and Automated prompt improvement suggestions, Create a new prompt version and activate it.

👉 /admin/prompts

---

###  9️⃣ Run new interview

Start another interview.

---

### 🔟 Verify improvement

- New prompt version used

- Improved evaluation behavior

---

### ⏸️ Compare conversations based on ID's

👉 /admin/compare

---

### ⚠️ Error Handling

Handles:

- Missing input
- Invalid states
- LLM failures
- Prompt issues


### 📌 Assumptions

- Fixed 3 questions per skill
- Limited clarification attempts
- SQLite for simplicity
- Small evaluator group

### 🔒 Notes

- API KEY is NOT included in .env for security
- .env is provided with mockLLM = true
- Mock mode recommended for quick testing

###  🏁 Reviewer Quick Start

```bash
docker compose up --build
```
👉 http://localhost:8000





