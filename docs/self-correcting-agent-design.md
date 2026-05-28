# Self-Correcting Agent Design

## Overview

A feedback-driven system that allows the agent to evolve its system prompts based on user feedback, with admin approval before changes take effect.

## Goals

- Collect user feedback (thumbs up/down) on each agent response
- Require mandatory text feedback on downvotes
- Agent analyzes feedback and proposes prompt improvements
- Admin reviews and approves/rejects proposed changes
- Full audit trail for traceability

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Feedback granularity | Per-feedback fix | Immediate, traceable corrections |
| Prompt storage | Database with config fallback | Flexibility + safe defaults |
| Admin role | Existing RBAC admin | No new role management needed |
| Scope | System prompts only | Focused scope, easier to validate |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              User Interaction                                │
├─────────────────────────────────────────────────────────────────────────────┤
│  [Chat UI] ──► [Agent Response] ──► [👍 / 👎]                               │
│                                          │                                   │
│                                          ▼ (if 👎)                           │
│                                   [Feedback Modal]                           │
│                                   "What went wrong?"                         │
└─────────────────────────────────────────────────────────────────────────────┘
                                          │
                                          ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            Feedback Storage                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│  feedback_submissions table:                                                 │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ id | conversation_id | message_id | user_id | role | vote | text   │    │
│  │    | timestamp | context_snapshot                                   │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
                                          │
                                          ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Self-Correction Engine                               │
├─────────────────────────────────────────────────────────────────────────────┤
│  1. Receive negative feedback                                                │
│  2. Load: conversation history + current prompt for that role               │
│  3. LLM analyzes: "What instruction would have prevented this?"             │
│  4. Generate proposed prompt diff                                            │
│  5. Store as pending_prompt_change                                           │
└─────────────────────────────────────────────────────────────────────────────┘
                                          │
                                          ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          Admin Review Dashboard                              │
├─────────────────────────────────────────────────────────────────────────────┤
│  ┌───────────────────────────────────────────────────────────────────┐      │
│  │  Pending Change #42                                    [Approve]  │      │
│  │  Role: customer                                        [Reject]   │      │
│  │  ─────────────────────────────────────────────────────────────── │      │
│  │  📝 User Feedback:                                                │      │
│  │  "Agent gave wrong return policy info"                            │      │
│  │                                                                   │      │
│  │  💬 Original Conversation:        (expandable)                    │      │
│  │  ─────────────────────────────────────────────────────────────── │      │
│  │  📋 Proposed Change:                                              │      │
│  │  - You can ONLY help with:                                        │      │
│  │  + You can ONLY help with:                                        │      │
│  │  + - Always verify return policy details using KB articles        │      │
│  └───────────────────────────────────────────────────────────────────┘      │
└─────────────────────────────────────────────────────────────────────────────┘
                                          │
                                          ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            Prompt Storage                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│  system_prompts table:                                                       │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ id | role | prompt_text | version | is_active | created_at        │    │
│  │    | created_by | parent_version                                   │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  On startup: if no active prompt in DB → load from config (guardrails.py)   │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Data Models

### feedback_submissions

| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| conversation_id | UUID | Links to conversation |
| message_id | UUID | Specific agent response |
| user_id | string | User who gave feedback (e.g., cust_001) |
| role | string | User's role at time of feedback |
| vote | enum | `up` or `down` |
| feedback_text | string | Required if vote=down |
| context_snapshot | JSON | Full conversation up to this point |
| created_at | timestamp | When feedback was submitted |

### pending_prompt_changes

| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| feedback_id | UUID | FK to feedback_submissions |
| target_role | string | Which role's prompt to modify |
| current_prompt | text | Prompt at time of proposal |
| proposed_prompt | text | Suggested new prompt |
| diff_summary | text | Human-readable change summary |
| status | enum | `pending`, `approved`, `rejected` |
| reviewed_by | string | Admin who reviewed |
| reviewed_at | timestamp | When reviewed |
| created_at | timestamp | When proposed |

### system_prompts

| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| role | string | `customer`, `operator`, `admin` |
| prompt_text | text | Full system prompt |
| version | int | Auto-incrementing version |
| is_active | boolean | Only one active per role |
| parent_version | int | Previous version (for rollback) |
| change_id | UUID | FK to pending_prompt_changes |
| created_by | string | Admin who approved |
| created_at | timestamp | When activated |

---

## API Endpoints

### Feedback Submission

```
POST /api/feedback
Authorization: Bearer <token>

{
  "conversation_id": "uuid",
  "message_id": "uuid",
  "vote": "down",
  "feedback_text": "Agent gave wrong return window (said 60 days, should be 30)"
}
```

### Admin Endpoints

```
GET  /api/admin/prompt-changes              # List pending changes
GET  /api/admin/prompt-changes/:id          # Get change details + context
POST /api/admin/prompt-changes/:id/approve  # Approve and activate
POST /api/admin/prompt-changes/:id/reject   # Reject with reason

GET  /api/admin/prompts                     # List all prompts (active + history)
GET  /api/admin/prompts/:role/history       # Version history for a role
POST /api/admin/prompts/:role/rollback      # Rollback to previous version
```

---

## Self-Correction Engine

### Prompt Analysis Flow

```python
def analyze_feedback(feedback: FeedbackSubmission) -> PendingPromptChange:
    # 1. Load context
    conversation = get_conversation(feedback.conversation_id)
    current_prompt = get_active_prompt(feedback.role)
    
    # 2. Ask LLM to analyze
    analysis_prompt = f"""
    You are a prompt engineering assistant. A user gave negative feedback 
    on an agent response.
    
    ## Current System Prompt (for {feedback.role} role):
    {current_prompt}
    
    ## Conversation:
    {format_conversation(conversation)}
    
    ## User Feedback:
    {feedback.feedback_text}
    
    ## Task:
    1. Identify what went wrong in the agent's response
    2. Propose a minimal, specific addition or edit to the system prompt
       that would prevent this issue
    3. Return the full updated prompt with your change
    
    Output format:
    ANALYSIS: <what went wrong>
    CHANGE_SUMMARY: <one-line description of the fix>
    PROPOSED_PROMPT: <full updated prompt>
    """
    
    result = llm.complete(analysis_prompt)
    
    # 3. Parse and store
    return PendingPromptChange(
        feedback_id=feedback.id,
        target_role=feedback.role,
        current_prompt=current_prompt,
        proposed_prompt=result.proposed_prompt,
        diff_summary=result.change_summary,
        status="pending"
    )
```

---

## Prompt Loading Logic

```python
def get_system_prompt(role: str) -> str:
    # Try database first
    db_prompt = db.query(SystemPrompt).filter(
        role=role, 
        is_active=True
    ).first()
    
    if db_prompt:
        return db_prompt.prompt_text
    
    # Fallback to config
    return DEFAULT_PROMPTS[role]  # from guardrails.py
```

---

## Admin Dashboard UI

### Pending Changes View

- List of pending prompt changes with:
  - Target role
  - Feedback summary
  - Created timestamp
  - Quick approve/reject buttons

### Change Detail View

- **Feedback section**: User's exact feedback text
- **Conversation section**: Expandable full conversation leading to the feedback
- **Diff section**: Side-by-side or unified diff of prompt changes
- **Actions**: Approve / Reject / Edit before approving

### Prompt History View

- Version timeline per role
- Each version shows: change summary, who approved, when
- One-click rollback to any previous version

---

## Rollback Strategy

1. Each prompt version tracks its `parent_version`
2. Rollback creates a new version (doesn't delete history)
3. Admin can rollback from history view
4. Rollback also records reason

---

## Future Enhancements (Out of Scope)

- [ ] Aggregate similar feedback before proposing changes
- [ ] A/B testing of prompt variants
- [ ] Auto-approve after N successful feedback cycles
- [ ] Extend to tool descriptions and guardrail rules
- [ ] Feedback analytics dashboard

---

## Open Questions

1. **Conflict handling**: What if two pending changes target the same prompt section?
2. **Feedback quality**: How to handle low-quality or abusive feedback?
3. **Rate limiting**: Limit how many prompt changes can be proposed per day?
