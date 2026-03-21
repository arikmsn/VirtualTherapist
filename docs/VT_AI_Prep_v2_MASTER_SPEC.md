# VirtualTherapist – AI Personalization & Prep v2
## MASTER SPEC (System-Level, Implementation-Oriented)

> Goal: Align the existing VirtualTherapist backend to a **single, coherent architecture** for AI-driven summaries and pre-session prep, using **TherapistProfile**, **TherapistSignatureProfile**, **Patient**, **SessionSummary**, **Session**, and **ModalityPack** as they exist today.  
>  
> You must treat this as a **system alignment task**, not greenfield. Prefer **mapping the spec onto existing models and services**, making minimal, explicit changes with clear diffs.

---

## 0. General Rules for Implementation

1. **Do not break working flows**  
   - `/sessions/{id}/summary/*` (generation, edit, approve) must continue to work as today.  
   - Legacy `/sessions/{id}/prep-brief` must keep its current behavior until we explicitly switch it off.  
   - Deep summary, treatment plan, formal record flows must remain intact.

2. **Phased implementation**  
   Implement in **three phases**, each with separate commits and clear diffs:
   - Phase 1 – Data layer & artifacts (no behavior change to existing endpoints).  
   - Phase 2 – LLM contract & new pipelines (behind flags / options).  
   - Phase 3 – Endpoint migration & feature toggles (switching endpoints to new logic with rollback).

3. **Small diffs, explicit mapping**  
   - For each change, show **which part of this spec** it implements.  
   - Do not rename core models or move files around unless strictly necessary.  
   - Any time the spec conflicts with reality, **document the diff and ask for confirmation** before large refactors.

---

## 1. Core Concepts and Target Architecture

We will introduce one main conceptual object and two supporting “profiles” on top of existing models:

- **PatientTreatmentState** – per patient, cumulative clinical state across sessions (artifacts built from `SessionSummary`, `Patient`, `ModalityPack`, protocols).  
- **TherapistStyleProfile** – a derived view combining `TherapistProfile` + `TherapistSignatureProfile` for style.  
- **AIConstraints** – a derived view of all AI-related limits/preferences from `TherapistProfile` + Modality + settings.

These are **not new DB tables**; they are **structured JSON artifacts and helper functions** that build on existing models.

All AI calls (prep, summaries, deep summary, plan, messages) will move to a shared **LLMContextEnvelope** contract.

---

## 2. PatientTreatmentState – Target Design

### 2.1 Concept

`PatientTreatmentState` is a **computed snapshot per patient** that summarizes:

- Who this patient is (from `Patient`).  
- What protocols they are under and what phase of treatment they are in.  
- What themes, goals, tasks, risks, and patterns emerge from **approved** `SessionSummary` rows.  
- What “open loops” exist for the next session.

It will be represented as a **JSON-like Python dict** built on demand, optionally persisted as an artifact later if needed.

### 2.2 Structure

Define a Python dataclass or TypedDict for:

```python
class PatientTreatmentState(TypedDict):
    patient_id: int
    therapist_id: int
    protocol_context: Dict[str, Any]
    longitudinal_state: Dict[str, Any]
    last_session_state: Dict[str, Any]
    current_risks: Dict[str, Any]
    homework_state: Dict[str, Any]
    open_threads: Dict[str, Any]
    metadata: Dict[str, Any]
```

With these nested sections:

1. `protocol_context`  
   - `primary_protocol_id: Optional[str]` – from `Patient.protocol_ids[0]` or therapist defaults.  
   - `protocols: List[Dict]` – full definitions resolved from system/custom protocols + `ModalityPack`.  
   - `phase: Literal['early','middle','late','undefined']` – inferred from number of completed sessions vs `typical_sessions`.  

2. `longitudinal_state`  
   - `primary_themes: List[str]` – themes across all approved summaries (`topics_discussed`, `patient_progress`).  
   - `active_goals: List[str]` – from `Patient.treatment_goals` + goals extracted from summaries.  
   - `coping_strengths: List[str]` – positive resources from `SessionSummary.patient_progress`.  
   - `persistent_challenges: List[str]` – recurring difficulties across sessions.  

3. `last_session_state`  
   - `session_id: Optional[int]` – last session with approved summary.  
   - `session_number: Optional[int]` – from `Session.session_number`.  
   - `key_points: List[str]` – major events/themes from last `SessionSummary`.  
   - `homework_given: Optional[str]` – from `homework_assigned`.  
   - `homework_status: Optional[str]` – inferred if there is info about completion in later sessions.  
   - `risk_notes: Optional[str]` – from `risk_assessment`.  

4. `current_risks`  
   - `has_active_risk: bool`  
   - `risk_descriptions: List[str]` – from `risk_assessment` across summaries.  
   - `last_risk_update_session_id: Optional[int]`  

5. `homework_state`  
   - `open_homework_items: List[Dict]` – from `Patient.current_exercises` and summaries.  
   - `recent_completions: List[Dict]` – if recorded.  

6. `open_threads`  
   - `unresolved_topics: List[str]` – items that appear as open questions in summaries.  
   - `assessment_due: List[str]` – from “gaps” (e.g. specific assessments not done).  

7. `metadata`  
   - `sessions_analyzed: int` – count of approved summaries included.  
   - `last_updated_at: datetime`  
   - `source: Literal['computed','cached']`  
   - `version: int` – state schema version.

### 2.3 Implementation Plan

**Phase 1 (no behavior change):**

- Implement a pure function in a new module, e.g. `app/ai/state.py`:

```python
def build_patient_treatment_state(
    therapist: Therapist,
    profile: TherapistProfile,
    patient: Patient,
    modality_pack: ModalityPack,
    summaries: List[SessionSummary],
) -> PatientTreatmentState:
    ...
```

- Use **only existing fields**:
  - `Patient.protocol_ids`, `Patient.treatment_goals`, `Patient.demographics`.  
  - `SessionSummary.full_summary`, `topics_discussed`, `patient_progress`, `homework_assigned`, `risk_assessment`.  
  - `Session.session_number`, `session_date`.  
  - `ModalityPack` protocol information and prompt module.  
- In this phase:  
  - Build the structure using **simple heuristics** and/or 1 LLM call if needed, but **do not wire it into endpoints yet**.  
  - Add unit-style tests or scripts that create `PatientTreatmentState` for one or two real patients (no HTTP exposure yet).

**Phase 2:**

- Use `PatientTreatmentState` as the **primary input** for prep and deep summary pipelines, instead of ad hoc manual context building.  

---

## 3. TherapistStyleProfile and AIConstraints

### 3.1 TherapistStyleProfile

Concept: a **computed view** that merges `TherapistProfile` and `TherapistSignatureProfile` into one object describing how we should "sound" when writing for this therapist.

```python
class TherapistStyleProfile(TypedDict):
    therapist_id: int
    profession: str
    therapeutic_approach: str
    primary_therapy_modes: List[str]
    tone: str
    tone_warmth: int
    directiveness: int
    message_length_preference: str
    style_summary: Optional[str]
    style_examples: List[str]
    preferred_sentence_length: Optional[str]
    preferred_voice: Optional[str]
    uses_clinical_jargon: bool
    preferred_terminology: Dict[str, int]
    style_version: int
```

Implementation:

- Add a helper in `app/ai/style.py`:

```python
def build_therapist_style_profile(
    profile: TherapistProfile,
    signature: Optional[TherapistSignatureProfile],
) -> TherapistStyleProfile:
    ...
```

- Use:
  - From `TherapistProfile`: `profession`, `therapeutic_approach`, `primary_therapy_modes`, `tone`, `tone_warmth`, `directiveness`, `message_length_preference`, `common_terminology`, `style_version`.  
  - From `TherapistSignatureProfile`: `style_summary`, `style_examples`, `preferred_sentence_length`, `preferred_voice`, `uses_clinical_jargon`, `preferred_terminology`.  
- If `signature` is missing or inactive, fields from it should be `None` or appropriate defaults.

### 3.2 AIConstraints

Concept: a **single object** capturing all limits / "must/never" rules for AI, combining:

- `TherapistProfile.prohibitions`  
- `TherapistProfile.custom_rules`  
- `TherapistProfile.language`  
- Modality-specific constraints from `ModalityPack`  
- Future AI-related flags if added.

```python
class AIConstraints(TypedDict):
    language: str
    prohibitions: List[str]
    custom_rules: List[str]
    max_length_hint: Literal['short','medium','detailed']
    modality_required_fields: List[str]
    modality_recommended_fields: List[str]
    disallowed_behaviors: List[str]
    must_never_ending_with_question: bool
```

Implementation:

- Add helper in `app/ai/constraints.py`:

```python
def build_ai_constraints(
    profile: TherapistProfile,
    modality_pack: ModalityPack,
) -> AIConstraints:
    ...
```

- `must_never_ending_with_question` should be set to `True` as per product requirement.  
- `max_length_hint` derived from `message_length_preference`.  
- `modality_required_fields` and `modality_recommended_fields` from `ModalityPack.required_summary_fields` and `.recommended_summary_fields`.

---

## 4. Common LLMContextEnvelope

### 4.1 Structure

Define a central envelope type, used by all AI pipelines:

```python
class LLMContextEnvelope(TypedDict):
    therapist_style: TherapistStyleProfile
    ai_constraints: AIConstraints
    patient_state: PatientTreatmentState
    request_type: Literal[
        'prep',
        'session_summary',
        'deep_summary',
        'treatment_plan',
        'message',
        'homework',
    ]
    request_mode: Optional[str]   # e.g. 'concise', 'deep', 'gap_analysis'
    extra: Dict[str, Any]         # for request-specific data
```

### 4.2 Builder Function

Implement in a central place, e.g. `app/ai/context.py`:

```python
def build_llm_context_envelope_for_session(
    therapist: Therapist,
    profile: TherapistProfile,
    signature: Optional[TherapistSignatureProfile],
    patient: Patient,
    modality_pack: ModalityPack,
    summaries: List[SessionSummary],
    request_type: str,
    request_mode: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> LLMContextEnvelope:
    ...
```

This function must:

1. Call `build_therapist_style_profile`.  
2. Call `build_ai_constraints`.  
3. Call `build_patient_treatment_state`.  
4. Merge them into one `LLMContextEnvelope`.

**Phase 1**: build it but use it only for logging / debug.  
**Phase 2**: use it inside prep, summaries, etc., instead of each pipeline constructing its own context.

---

## 5. Prep v2 – Aligning to the New Contract

We want `PrepPipeline` to **consume LLMContextEnvelope** rather than separately assembled pieces.

### 5.1 Extraction Pass (Call 1) – JSON Only

Requirements:

- Must consume `LLMContextEnvelope` and use:
  - `patient_state.longitudinal_state`, `last_session_state`, `homework_state`, `open_threads`, `current_risks`.  
  - `protocol_context` (including phase).  
- Must **not** produce "no data" text. If there is no data for a field, set it to `null` or empty list in JSON.

Implementation changes:

- Refactor `PrepPipeline.extract_only()` to accept:

```python
def extract_only(
    envelope: LLMContextEnvelope,
) -> Dict[str, Any]:
    ...
```

- Internally:  
  - Construct the extraction prompt from `envelope`, not from separate `approved_summaries` and `ai_context`.  
  - Keep `PREP_JSON_SCHEMA` as the output target, but populate from envelope.  

### 5.2 Render Pass (Call 2) – Hebrew Prose

Requirements:

- Must use:
  - `therapist_style` for style instructions and few-shot examples.  
  - `patient_state` and `prep_json` only.  
  - `ai_constraints` for language, length, and "no question at the end".

Implementation changes:

- Refactor `PrepPipeline.render()` and `render_stream()` to accept:

```python
def render(
    envelope: LLMContextEnvelope,
    prep_json: Dict[str, Any],
) -> str:
    ...

async def render_stream(
    envelope: LLMContextEnvelope,
    prep_json: Dict[str, Any],
) -> AsyncIterator[str]:
    ...
```

- Prompt rules:
  - If `patient_state.metadata.sessions_analyzed == 0`:  
    - Allowed to say explicitly "אין עדיין סיכומים מאושרים" and use only protocol context.  
  - If `sessions_analyzed > 0`:  
    - **Forbidden** to say "אין נתונים", "מבוסס על פרוטוקול בלבד", etc.  
    - Must reference at least 2–3 concrete details derived from `prep_json` / `patient_state`.

- Always ensure:
  - Output is in Hebrew (`ai_constraints.language`).  
  - Output does not end with a question mark or question sentence.  

### 5.3 Session Model Persistence

Maintain existing `Session` fields (`prep_json`, `prep_rendered_text`, `prep_input_fingerprint`, etc.), but:

- The fingerprint input should be derived from **envelope + summaries**, not raw `approved_summaries` only.  
- Add a new derived field `prep_sessions_analyzed` to `Session` (if not already) or store this inside `prep_json.metadata.sessions_analyzed`.

---

## 6. Events → Jobs → Artifacts

We want a clear mapping of events to jobs. Implement as backend functions; use existing infra (celery/async tasks) if present, or synchronous for now.

### 6.1 Events

Use these core events:

- `TherapistProfile` updated (or onboarding step completed).  
- `TherapistSignatureProfile` rebuilt.  
- `Patient` updated (protocols, goals, demographics).  
- `SessionSummary` approved.  
- `ModalityPack` changed (for this therapist).

### 6.2 Jobs

Define the following jobs (can be simple service methods for now):

1. `rebuild_therapist_style_profile(therapist_id)`  
   - Reads `TherapistProfile` + latest `TherapistSignatureProfile`.  
   - Calls `build_therapist_style_profile`.  
   - No persistence needed; used at runtime only.

2. `rebuild_patient_treatment_state(patient_id)`  
   - Reads `Patient`, `Therapist`, `TherapistProfile`, `ModalityPack`, all approved `SessionSummary`.  
   - Calls `build_patient_treatment_state`.  
   - Optionally stores snapshot in a new field (e.g. `Patient.treatment_state_json`), but this is not required in Phase 1.

3. `refresh_prep_for_session(session_id, mode)` (optional Phase 3)  
   - Builds envelope and runs both extraction and render, updates `Session` prep fields.

### 6.3 Wiring Events to Jobs (Phase 1)

Phase 1: **no scheduler / queue**, just add calls to these jobs in appropriate service methods:

- When `SessionService.approve_summary()` runs:  
  - Call `rebuild_patient_treatment_state(patient_id)` in the background (best-effort).  
- When `TherapistSignatureProfile` is rebuilt:  
  - Future prep calls will automatically pick up the new style via `build_therapist_style_profile`.  
- When `Patient.protocol_ids` is updated:  
  - Call `rebuild_patient_treatment_state(patient_id)`.

---

## 7. Endpoint Migration Strategy

### 7.1 Phase 1 – No Behavior Change

- Implement all **builders** (`PatientTreatmentState`, `TherapistStyleProfile`, `AIConstraints`, `LLMContextEnvelope`) and wire them only for **logging / experimentation** (e.g. additional debug in `PrepPipeline`), without changing user-visible behavior.

### 7.2 Phase 2 – Optional New Prep Path

- Add a feature flag (env var) `PREP_V3_ENABLED`.  
- If enabled, `/sessions/{id}/prep` and `/sessions/{id}/prep/stream` will:
  - Build envelope via `build_llm_context_envelope_for_session`.  
  - Use the refactored `PrepPipeline.extract_only(envelope)` and `render/render_stream(envelope, json)`.

Maintain:

- Same HTTP responses as today (`prep_json`, `rendered_text`, `sessions_analyzed`, cache behavior).  
- Existing caching contract (time-based + fingerprint).

### 7.3 Phase 3 – Legacy Prep Decommissioning

Only after testing:

- Make `PREP_V3_ENABLED=True` default.  
- Optionally deprecate or alias legacy `/prep-brief` to the new mechanism, or keep as a separate, simple clinical view.

---

## 8. Guardrails and Testing Requirements

1. **No regression in prep content quality**  
   - For several real patients, compare current prep output vs v3 output.  
   - Ensure v3 never falls back to generic protocol text when `sessions_analyzed > 0`.

2. **No more "אין נתונים / פרוטוקול בלבד" escape**  
   - When there is at least one approved summary, model must always derive content from it.  

3. **Logging**  
   - For each prep generation, log:
     - `sessions_analyzed`, `mode`, `style_version`, whether cache hit, and if `patient_state` was computed or cached.  

4. **Explicit diffs**  
   - For each PR/commit, include a summary:  
     - "Implements spec section X.Y (e.g. 2.3 PatientTreatmentState.metadata)".  

---

## 9. What You Should Do First

1. Implement **Phase 1 builders**:  
   - `build_patient_treatment_state()`  
   - `build_therapist_style_profile()`  
   - `build_ai_constraints()`  
   - `build_llm_context_envelope_for_session()`  

2. Wire them into prep generation in **debug-only mode** (log the envelope, do not change prompts yet).  

3. After confirming envelopes look correct for a couple of real sessions, proceed to Phase 2: refactor `PrepPipeline` to use the envelope while preserving current external behavior.

---

Use this spec as the **single source of truth**.  
Before applying any large refactor not directly covered here, print a short note explaining the mismatch between code and spec and wait for explicit confirmation.
