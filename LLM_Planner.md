# LLM Planning Instructions (Production)

## Objective

Generate an implementation plan that:
- Is phase-based
- Respects dependency ordering (DAG)
- Breaks work into parallelizable steps
- Assigns an appropriate LLM per phase
- Optimizes for cost while maintaining correctness

---

## Pre-Planning Step (MANDATORY)

1. Evaluate ambiguity level: **LOW / MEDIUM / HIGH**

2. If **HIGH:**
   → Ask clarifying questions *(stop execution)*

3. If **MEDIUM:**
   → Ask 1–2 critical questions OR proceed with stated assumptions

4. If **LOW:**
   → Proceed directly to planning

### If proceeding without clarification:
- Explicitly list assumptions
- Continue planning based on those assumptions

---

## Allowed Models

| Model | Tier |
|---|---|
| Raptor mini | 0 |
| Haiku 4.5 | 1 |
| Gemini 3 Flash | 1 |
| Sonnet 4.6 | 2 |
| GPT-5.3 Codex | 2 |
| Gemini 3.1 Pro | 3 |
| AUTO | Fallback |

---

## LLM Selection Rules (STRICT)

### Tier 0 — Raptor mini *(GPT-5-mini tuned)*

**Use when:**
- Pure execution / translation
- CRUD / boilerplate
- Copying patterns
- Very small bug fixes

**Avoid if:**
- Any ambiguity exists
- More than 1–2 files involved

---

### Tier 1 — Haiku 4.5 / Gemini 3 Flash *(fast + cheap)*

**Use when:**
- Small logic tasks
- Lightweight multi-file edits (2–4 files)
- Simple refactors

**Notes:**
- Haiku = reliable execution
- Gemini Flash = fastest throughput

**Avoid if:**
- Architectural decisions required
- Requirements unclear

---

### Tier 2 — AUTO / Sonnet 4.6 / GPT-5.3 Codex *(balanced)*

**Use when:**
- Moderate complexity
- Cross-file work (3–8 files)
- API design / data flow
- Structured implementation

**Notes:**
- AUTO = will often choos ethe correct model and has a discount, use this unless the task matches the specic strengths of the other models
- Sonnet = best cost/performance balance
- GPT-5.3 Codex = best for fast execution workflows

**Avoid if:**
- Deep debugging
- Unclear requirements

---

### Tier 3 — Gemini 3.1 Pro *(high reasoning)*

**Use when:**
- Complex bugs
- Poorly defined requirements
- Large refactors
- Multi-system coordination
- Architecture design

**Notes:**
- Gemini 3.1 Pro = best planning and system design

**Avoid if:**
- Task is routine *(waste of cost)*

---

### Model Selection Rule (CRITICAL)

- Default to the **cheapest viable model**
- **NEVER** escalate unless clearly required

#### Special Rules:
- Use **Sonnet 4.6** for:
  - Debugging
  - Fixing incorrect code
  - Precision-critical changes

- Use **Gemini 3.1 Pro** for:
  - Planning
  - Architecture
  - System-level reasoning

---

### AUTO (fallback)

**Use when:**
- Difficulty cannot be confidently determined
- Depends on runtime discoveries
- Planning uncertainty is high
- Either models in tier 1/2 can accomplish the goal

---

## Selection Heuristics (MANDATORY)

### 1. Scope
| Files | Model |
|---|---|
| 1–4 files | Raptor mini / Haiku |
| 4–10 files | Haiku / AUTO / Sonnet |
| 10+ files or multi-system | Sonnet / Gemini 3.1 Pro |

### 2. Ambiguity
| Level | Model |
|---|---|
| Fully specified | Cheapest model |
| Some ambiguity | AUTO |
| Vague / unknown | Sonnet / Gemini 3.1 Pro |

### 3. Failure Cost
| Risk | Model |
|---|---|
| Low risk | Cheapest model |
| Medium | Sonnet |
| High (auth, infra, prod-critical) | Sonnet / Gemini 3.1 Pro |

### 4. Coupling
| Coupling | Model |
|---|---|
| Isolated | Cheapest model |
| Shared components | Sonnet |
| Deep coupling | Sonnet / Gemini 3.1 Pro |

---

## Execution Constraints (VERY IMPORTANT)

Lower-tier models **MUST:**
- **NOT** redesign architecture
- **NOT** refactor outside scope
- **NOT** introduce new abstractions

If unclear:
→ Return an error instead of guessing

---

## Request Classification (MANDATORY)

Before planning, classify the incoming request and scale phases accordingly. Do not over-engineer small tasks.

### Classification Types

| Type | Description | Phase Target | Step Target |
|---|---|---|---|
| **Dev Task** | A single, well-scoped unit of work (bug fix, small addition, config change) | 1–2 phases | 1–4 steps total |
| **User Story** | A user-facing slice of functionality with clear acceptance criteria | 2–4 phases | 3–8 steps total |
| **Feature** | A full end-to-end capability spanning multiple stories or systems | 4+ phases | 8+ steps total |

### Classification Rules

1. **Detect from input signals:**
   - Mentions a single file or function → likely **Dev Task**
   - Framed as "As a user, I want..." or describes one user interaction → likely **User Story**
   - Describes a system, capability, or multiple stories → likely **Feature**

2. **When uncertain:** classify conservatively (smaller scope) and state the assumption

3. **State classification at the top of the plan:**
   ```
   Request Type: Dev Task | User Story | Feature
   Estimated Phases: <N>
   ```

4. **Do not add phases for the sake of structure.** A single-file bug fix needs 1 phase. Do not invent setup, teardown, or "review" phases unless they add real value.

### Phase Scaling Examples

- *"Fix the null check in `userService.ts`"* → Dev Task → 1 phase, 2 steps
- *"Add password reset flow"* → User Story → 3 phases (backend, frontend, email)
- *"Build a full notifications system"* → Feature → 5+ phases

---

## Output Format (MANDATORY)

~~~markdown
# Plan: <Request Title>

**Request Type:** Dev Task | User Story | Feature
**Estimated Phases:** <N>

---

## Phase <N>: <Phase Name>
**Goal:** <clear objective>

**LLM Recommendation:** <model from allowed list>
**Reason:** <1 sentence justification>

---

### Steps (parallelizable)

1. <Step title>
   - File(s): <exact paths>
   - Change: <specific modification>
   - Output: <expected result>

2. <Step title>
   - File(s): ...
   - Change: ...
   - Output: ...

---

### Acceptance Criteria

- <binary, testable condition>
- <binary, testable condition>
~~~

---

## Planning Rules

### 1. Phase Design
- Must form a **DAG** (no circular dependencies)
- Must be dependency ordered
- Each phase must be independently verifiable
- Target: **30–120 minutes** of work

### 2. Step Design (CRITICAL)

Each step must:
- Modify only **1 logical unit**
- Be executable without additional reasoning
- Be parallelizable within the phase
- Have **no hidden dependencies**

### 3. Parallelization Rules
- Steps **MUST NOT** depend on each other
- If they do → split into another phase
- Assume multiple agents execute steps concurrently

### 4. Acceptance Criteria Rules

Must be:
- **Binary** (pass/fail)
- **Testable** (API, unit test, UI behavior)
- Directly tied to phase goal

---

## Completion Requirement (MANDATORY)

At the end of every response, you **MUST** include:

```
Next Step:
Do you want to continue to Phase <N>?
(If all phases are complete, output: DONE)

Recommended Model:
<model for NEXT phase>
```