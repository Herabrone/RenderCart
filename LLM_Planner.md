LLM Planning Instructions (drop-in file)
Objective

Generate an implementation plan that:

is phase-based
respects dependency ordering
breaks work into parallelizable steps
assigns an appropriate LLM per phase
Output Format (MANDATORY)

### Pre-Planning Step

1. Evaluate ambiguity level: LOW / MEDIUM / HIGH

2. If HIGH:
   → Ask clarifying questions (stop execution)

3. If MEDIUM:
   → Ask 1–2 critical questions OR proceed with stated assumptions

4. If LOW:
   → Proceed directly to planning

The following should be used to decide what LLM to reccommend:
## LLM Selection Rules (STRICT)

### Tier 0 — Raptor mini (GPT-5-mini tuned)

**Use when:**
- Pure execution / translation
- CRUD / boilerplate
- Copying existing patterns
- Simple bug fixes

**Avoid if:**
- Any ambiguity exists
- Multi-file coordination is needed

---

### Tier 1 — Haiku / Gemini 3 Flash (fast + cheap)

**Use when:**
- Small logic tasks
- Lightweight multi-file edits
- Refactoring with clear instructions

**Notes:**
- Haiku is strong for reliable small coding tasks
- Gemini Flash is fast and strong for coding relative to cost

**Avoid if:**
- Architectural decisions required
- Requirements unclear

---

### Tier 2 — Sonnet 4.6 / GTP 5.3 Codex (balanced)

**Use when:**
- Moderate complexity
- Cross-file changes
- API design / data flow decisions

**Notes:**
- Sonnet = strong coding + cost balance
- GTP 5.3 Codex = strong generalist + multimodal workflows

**Avoid if:**
- Deep debugging or system redesign needed

---

### Tier 3 — Gemini 3.1 Pro (high reasoning)

**Use when:**
- Complex bugs
- Poorly defined requirements
- Large refactors
- Multi-system coordination

**Notes:**
- Gemini 3.1 Pro = top-tier agentic + tool workflows

**Avoid if:**
- Task is routine (wastes cost)

---

### AUTO (fallback)

**Use when:**
- Difficulty is unclear
- Depends on runtime discoveries
- Planning uncertainty is high

---

## Selection Heuristics (FOR THE PLANNER)

The planner MUST evaluate:

### 1. Scope
- 1-5 files → Raptor mini / Haiku  
- 5-10 files → Haiku / Sonnet  
- Many(10+) systems → Gemini 3.1 Pro  

### 2. Ambiguity
- Fully specified → cheapest model  
- Some ambiguity → Sonnet  
- Vague / unknown → Gemini 3.1 Pro  

### 3. Failure Cost
- Low risk → cheapest model  
- Medium → Sonnet  
- High (prod-critical, infra, auth) → Gemini 3.1 Pro  

### 4. Coupling
- Isolated → cheapest model  
- Shared components → Sonnet  
- Deep coupling → Gemini 3.1 Pro  

---

## Hard Rules (IMPORTANT)

- Default to the **cheapest viable model**
- NEVER use Gemini 3.1 Pro for:
  - boilerplate
  - CRUD
  - simple endpoints

- NEVER use Raptor mini if:
  - the step requires any interpretation

- If unsure → use **AUTO**, not Gemini 3.1 Pro


The following is how you should structure the plan:

# Feature Plan

## Phase <N>: <Phase Name>
**Goal:** <clear objective>

## LLM Recommendation: <Raptor mini | Haiku | Sonnet | Opus | Gemini 2.5 Pro | Gemini 3 Flash | Gemini 3.1 Pro | AUTO>

**Reason:** <1 sentence justification referencing task complexity, scope, and reasoning depth

### Steps (parallelizable)
1. <Step title>
   - File(s): <exact paths>
   - Change: <specific modification>
   - Output: <expected result>

2. <Step title>
   - File(s): ...
   - Change: ...
   - Output: ...

### Acceptance Criteria
- <testable condition>
- <testable condition>

Planning Rules
1. Phase Design
Phases must be dependency ordered (DAG)
No circular dependencies
Each phase should be independently verifiable
Target size: 30–120 minutes of work
2. Step Design (VERY IMPORTANT)

Steps must:

Modify only 1 logical unit (1 file or tightly related files)
Be executable without additional reasoning
Be parallelizable within the phase
Avoid hidden dependencies between steps

Bad:

“Implement authentication system”

Good:

“Add login endpoint in AuthController.java”
“Create UserRepository.findByEmail()”
3. Parallelization Rules
Steps in the same phase must NOT depend on each other
If they do → split into another phase
Assume multiple agents may execute steps simultaneously

4. LLM Selection Logic

Must be:

binary (pass/fail)
testable (unit test, API response, UI change)
tied to the phase goal
Example (shortened)
## Phase 2: User Authentication API
**Goal:** Implement backend login system

**LLM Recommendation:** Raptor-mini  
**Reason:** Standard CRUD + predictable patterns

### Steps (parallelizable)
1. Create login endpoint
   - File(s): src/controllers/AuthController.java
   - Change: Add POST /login endpoint
   - Output: Accepts email/password, returns token

2. Add user lookup
   - File(s): src/repositories/UserRepository.java
   - Change: Add findByEmail method
   - Output: Returns user by email

### Acceptance Criteria
- POST /login returns 200 with valid credentials
- Invalid credentials return 401