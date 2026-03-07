# Metapel.online — AI Layer Deep Upgrade
## Complete Instruction to Claude Code

---

## CONTEXT & FRAMING

You are the lead developer of Metapel.online (מטפל אונליין) — an AI-powered client management system for therapists, coaches, and counselors in Israel. You know the full codebase.

We are upgrading the AI layer from a generic summary generator into a **therapist-first clinical intelligence system**. This is a product-critical feature set, not a cosmetic prompt tweak. Implement it as a durable architecture that improves over time from therapist behavior, approved summaries, modality-specific standards, and structured outputs.

---

## HIGH-LEVEL GOAL

Build AI capabilities that are:
1. Modality-aware
2. Therapist-specific
3. Documentation-aware
4. Evidence-supported
5. Longitudinal
6. Transparent and editable
7. Useful in daily workflow — not just "impressive"

---

## IMPORTANT PRODUCT PRINCIPLES

- The therapist is always the clinical authority.
- AI suggestions must stay editable.
- **Therapist-edited/approved content is the main source of truth for future learning.** Raw AI drafts must not be treated as equivalent to therapist-approved summaries.
- Separate "clinical working help" from "formal record help".
- Never present the app as guaranteeing legal compliance. Instead, provide aligned structure + completeness checks + explicit missing items. Use language like "תמיכה בתיעוד" — never "עומד בדרישות החוק".
- Prefer structured intermediate JSON artifacts over one giant prompt that returns prose.
- Everything must be designed for improvement over time.
- **Hebrew quality is a clinical trust signal.** A stilted summary undermines therapist confidence in the entire system. All outputs must be in natural, professional Israeli Hebrew. If a therapist consistently mixes Hebrew-English clinical terminology (e.g., "transference", "schemas", "CBT"), mirror that pattern in all outputs for that therapist.

---

## PHASE 1 — CORE ARCHITECTURE

### A) MODALITY PACKS

Create a modality-pack system that defines the expected structure for different therapist approaches.

Each modality pack should include:
- `id`
- `label`
- `description`
- `target_therapist_types`
- `required_summary_fields`
- `recommended_summary_fields`
- `pre_session_prep_focus_areas`
- `treatment_plan_scaffold`
- `missing_data_checks`
- `preferred_terminology`
- `evidence_tags`
- `output_style_hints`
- `prompt_module` — actual clinical framing text (see below)

Seed at minimum: `generic_integrative`, `cbt`

**CBT pack v1 — prompt module (actual text to inject):**
```
You are assisting a CBT therapist. All outputs should be structured around the cognitive model.
Required elements: presenting problem focus, session agenda, homework review, automatic thoughts
and core beliefs when present, emotional/behavioral patterns, interventions used (name them:
Socratic questioning, thought records, behavioral experiments, etc.), between-session tasks,
next session focus. Use CBT terminology naturally: "automatic thoughts", "core beliefs",
"cognitive distortions", "schemas", "behavioral activation". Flag missing elements explicitly.
Cognitive distortions should be named when identified (catastrophizing, mind-reading, etc.).
Do NOT make CBT rigid or robotic — the goal is guided completeness, not forcing every note into a form.
```

**Psychodynamic pack — prompt module:**
```
You are assisting a psychodynamic therapist. Focus on: transference and countertransference
observations, defense mechanisms (name and contextualize), object relations and attachment
themes, unconscious patterns surfacing in session content, historical material connecting to
present symptoms. Avoid prescriptive language. Favor exploratory, interpretive framing.
Use psychodynamic terminology: "transference", "countertransference", "splitting",
"projection", "internalized objects", "affect regulation".
```

**DBT pack — prompt module:**
```
You are assisting a DBT therapist. Structure outputs around the four DBT skill modules.
Required elements: diary card data if available, skills used (mindfulness, distress tolerance,
emotion regulation, interpersonal effectiveness), chain analysis of problematic behaviors,
commitment to treatment and adherence, balance of validation and change strategies.
Use DBT terminology: "chain analysis", "opposite action", "radical acceptance", "DEAR MAN",
"wise mind". Note which stage of DBT treatment the client is in when relevant.
```

**ACT pack — prompt module:**
```
You are assisting an ACT therapist. Emphasize psychological flexibility using the hexaflex:
acceptance, defusion, present moment awareness, self-as-context, values clarification,
committed action. Focus on avoidance patterns vs. valued living. Note metaphors and
experiential exercises used. Use ACT language: "workability", "fusion", "experiential
avoidance", "values-based action", "psychological flexibility".
```

**Solution-Focused pack — prompt module:**
```
You are assisting a solution-focused therapist. Orient entirely toward strengths, exceptions
to the problem, and future possibilities. Required elements: exceptions to the problem,
client strengths demonstrated, scaling question results and progress, small steps taken,
future-oriented goals. Minimize problem-saturated language. Use SF terminology:
"miracle question", "scaling", "exceptions", "preferred future".
```

**Fallback rule:** If approach is unknown or "integrative", use `generic_integrative` with prompts to help the therapist specify their approach over time.

---

### B) THERAPIST SIGNATURE ENGINE

Build a therapist signature profile that learns from the therapist's approved/edited outputs over time.

**Critical rule: Learn ONLY from therapist-approved summaries, approved treatment plans, and therapist-authored/edited artifacts. Do NOT learn from raw AI-generated drafts unless the therapist accepted them without material edits.**

Profile dimensions to infer:
- `concise_vs_detailed` — average length of approved summaries
- `directive_vs_exploratory` — language patterns in interventions
- `emotional_vs_cognitive_emphasis` — ratio of emotional vs. cognitive language
- `homework_task_orientation` — frequency of homework assignments
- `structure_preference` — bullets vs. narrative prose
- `preferred_intervention_naming` — exact terms they use
- `documentation_rigor` — how complete their notes tend to be
- `risk_followup_inclusion` — do they typically include risk notes?
- `measurable_goals_tendency` — do they set measurable targets?
- `preferred_tone` — formal / warm / direct / exploratory
- `conceptual_evidence_orientation` — do they reference theory/research?
- `hebrew_english_mix` — do they mix languages in clinical notes?
- `preferred_terminology` — specific words and phrases used repeatedly

**Storage requirements:**
- Version this profile over time
- Add confidence scores (0–1) for each inferred trait
- Store internal "evidence snippets" for explainability (not user-facing PHI)
- Minimum data threshold: meaningful personalization should activate after 5+ approved summaries; show "הפרופיל שלך מתבסס — עוד כמה סיכומים ונדייק" until then

---

### C) AI ARTIFACT PIPELINE

Refactor all generation into structured steps. Do NOT rely on one monolithic text prompt.

For each major flow, create:
1. Structured input assembly
2. Structured JSON intermediate output
3. Rendered therapist-facing text derived from JSON

Core flows:
1. Pre-session prep
2. Session summary
3. Deep summary
4. Treatment plan
5. Twin profile update

---

## PHASE 2 — PRE-SESSION PREP 2.0

Upgrade pre-session prep to truly reflect: patient history, therapist-approved prior summaries, open tasks/homework, longitudinal progress, the specific therapist's style, and the selected modality pack.

**Inputs to use:**
- Patient profile
- Full session history
- **Last approved/edited summary (not the raw AI draft)**
- Unresolved open tasks / homework
- Treatment plan (if exists)
- Therapist signature profile
- Modality pack
- Major changes across recent sessions
- Risk/crisis/instability markers
- Therapist side notebook/reference items

**Output — structured JSON:**
```json
{
  "case_trajectory": "...",
  "likely_focus_today": "...",
  "changes_since_last_session": ["..."],
  "open_loops_to_check": ["..."],
  "homework_or_task_followup": ["..."],
  "suggested_questions": ["..."],
  "suggested_interventions": ["..."],
  "therapist_style_alignment_notes": "...",
  "modality_specific_considerations": "...",
  "documentation_reminders": ["..."],
  "confidence": 0.85,
  "missing_context": ["..."]
}
```

Then render a therapist-facing Hebrew prep brief from this JSON.

**UX modes:**
- **מצומצם** — 5 bullet points, 30-second read
- **מעמיק** — full structured brief
- **לפי שיטה** — modality-focused view
- **מה חסר לי?** — surfaces missing context before the session

---

## PHASE 3 — SESSION SUMMARY 2.0

Generate two distinct but connected outputs after a session:

### 1. Clinical Working Summary
Personalized to: therapist style, modality pack, patient history, longitudinal changes.

### 2. Formal Record Support
Documentation-oriented. Aligned to Israeli recordkeeping baseline.

**For Israeli Formal Record support, align specifically to:**
- Israeli Ministry of Health medical record regulations (תקנות בריאות הנפש, 1992 + תקן ניהול רשומה רפואית)
- Required fields: identifying details, date/time, therapist identity metadata, relevant background/history, current clinical picture/assessment, interventions/treatment content, treatment instructions/next steps, risk assessment
- For licensed clinical psychologists: DSM-5/ICD-11 diagnostic language, mandatory risk assessment documentation (even when outcome is "no risk identified"), potential court/insurance review standards

**Legal/product positioning — mandatory:**
- Label this section: **"תמיכה בתיעוד"**
- Never use: "תיעוד תקני", "עומד בדרישות", "מאושר משפטית"
- Use language like: "בדיקת שלמות רשומה", "פריטים מומלצים חסרים", "מבנה מיושר לסטנדרט"

### Completeness Checker

After generation, evaluate:
- Generic baseline completeness
- Modality-specific completeness
- Therapist-specific preferred completeness (based on their signature)

Return structured object:
```json
{
  "completeness_score": 0.78,
  "required_missing_items": ["הערכת סיכון חסרה"],
  "recommended_missing_items": ["לא צוין שיעורי בית לפגישה הבאה"],
  "modality_notes": "CBT: לא תועדו מחשבות אוטומטיות",
  "record_notes": "לפי התקן הישראלי: חסרה תכנית המשך מפורשת",
  "confidence": 0.82
}
```

Display as: **"שלמות סיכום: 78% — 2 פריטים חסרים"** with expandable details.

---

## PHASE 4 — DEEP SUMMARY + EVIDENCE LAYER

Define "depth" operationally through dimensions:
- Longitudinal integration (connects to past sessions)
- Causal/maintaining pattern hypotheses
- Modality relevance
- Specificity of interventions
- Specificity of patient change over time
- Linkage between goals, barriers, interventions, next steps
- External conceptual support when appropriate
- Explicit uncertainty when evidence is weak

### Therapist Reference Vault

Build an internal evidence layer supporting:
- Therapist-owned notebook items
- Curated conceptual references and notes
- Internal tagged knowledge snippets
- Modality-linked reference items

**First implementation: internal material only — no open web retrieval.**

When generating deep summary or treatment plan:
- Optionally show "למה ההמלצה הזו?"
- Cite internal reference titles/tags briefly
- Never dump long copyrighted text
- Never over-quote external material
- Keep the therapist's own voice primary

**Reference pool to seed (internal knowledge base):**
Core theorists: Yalom, Beck, Linehan, Bowlby, Winnicott, Hayes, Frankl, Rogers, Minuchin.
Israeli context: relevant Israeli psychological association standards, local research when applicable.
Match reference depth to therapist seniority: foundational for <5 years experience, advanced/nuanced for senior therapists.

**Example output style (write in therapist's voice, not academic):**
> "מה שעולה כאן מזכיר את מה שבק מדבר עליו לגבי הסכמה המרכזית — המטופל מפעיל את אותו דפוס שוב ושוב בקשרים שונים. זה יכול להסביר את הדינמיקה שראינו היום..."

---

## PHASE 5 — TREATMENT PLAN 2.0

Upgrade treatment plans into longitudinal, therapist-specific, living documents.

**Inputs:**
- Patient history + approved session summaries
- Longitudinal changes + adherence patterns
- Therapist signature profile + modality pack
- Approved references/notebook items
- Prior treatment plans and therapist edits to them

**Output JSON:**
```json
{
  "current_formulation": "...",
  "working_hypothesis": "...",
  "major_goals": [...],
  "short_term_objectives": [...],
  "interventions_fitted_to_therapist": [...],
  "between_session_tasks": [...],
  "measures_to_monitor": [...],
  "anticipated_barriers": [...],
  "review_cadence": "כל 8 פגישות",
  "rationale": "...",
  "evidence_refs": [...],
  "confidence": 0.75,
  "missing_inputs": [...]
}
```

**Render three views:**
- תכנית מצומצמת — one page overview
- תכנית מעמיקה — full structured plan
- תכנית לפי שיטה — modality-structured

**Plan drift/update helper** (runs every 3–5 sessions):
```
- מה השתנה מהתכנית הקודמת?
- מה התקדם?
- מה תקוע?
- מה כדאי לשנות עכשיו?
```
Flag: "תכנית הטיפול עודכנה — עיין ואשר" (therapist must approve before it becomes active).

---

## PHASE 6 — TWIN PROFILE 2.0

The Twin Profile is the system's model of who this therapist IS. It must feel like a living representation — not static onboarding metadata.

**Profile domains:**
- Clinical orientation
- Language style
- Structure preference
- Intervention habits
- Engagement style
- Level of directiveness
- Emotional vs. cognitive emphasis
- Risk posture / caution level
- Documentation rigor
- Affinity to tasks/homework
- Conceptual/evidence orientation
- Change over time (how their practice evolves)

**Therapist-facing explanation layer:**

Display in settings: "מה למדנו על דרך העבודה שלך"

Each entry:
```
גישה: [trait name]
ביטחון: [confidence %]
מבוסס על: [N] סיכומים מאושרים
מה זה משנה בהתנהגות ה-AI: [specific behavioral change]
```

**Twin Profile summary — generated text, second person, warm tone:**

Structure:
- **הגישה שלך** — 2–3 paragraphs on therapeutic philosophy as demonstrated
- **הסגנון שלך** — how they write, specific language examples
- **מה חזק אצלך** — genuine strengths from session patterns
- **הדפוסים שלך** — recurring interventions, preferred techniques
- **מה אנחנו לומדים עליך לאורך זמן** — how practice has evolved
- **איך אנחנו מתאימים את עצמנו לך** — explicit statement of personalizations active

**Rules:**
- Write in natural, warm Israeli Hebrew — this is a trust document
- Reference ACTUAL patterns from their specific sessions — not generic descriptions
- Regenerate every 5 sessions; show changelog: "מה השתנה מאז הפרופיל הקודם"
- Confidence disclaimer if <10 sessions: "אנחנו עדיין מכירים אותך — הפרופיל יעמיק ככל שנעבוד יחד יותר"
- Therapist can add corrections/notes → these feed back into the signature engine

---

## PHASE 7 — MODEL ROUTING

Do NOT replace the current model with a single expensive model. Implement smart routing.

**Default small/fast model handles:**
- Extraction and classification
- Tagging and structured field filling
- Completeness scoring + missing item detection
- Lightweight prep
- Delta detection between versions
- Background jobs

**Stronger model triggers when:**
- Therapist explicitly requests "מצב עמוק"
- Session history length crosses threshold (>15 sessions)
- Cross-session synthesis is complex
- Treatment plan generation
- Twin profile synthesis/update
- Small model confidence is low (<0.65)
- High ambiguity detected in input

**Recommended routing:**
```
extraction/classification → claude-haiku-4-5 (or equivalent fast model)
standard summaries/prep  → claude-sonnet-4-6
deep mode/treatment plan → claude-sonnet-4-6 with extended thinking
twin profile synthesis   → claude-opus-4-5
```

**Engineering requirements:**
- Keep provider abstraction clean — no hardcoded single model path
- Use feature flags/settings for routing thresholds
- Log which model/route was used for each generation
- Current GPT-4 mini flows → migrate to haiku-equivalent minimum; never use mini-class models for clinical synthesis

---

## PHASE 8 — DATA / STORAGE

Add or adapt storage for:
- Modality pack definitions (versioned)
- Therapist modality selection + preferences
- Therapist signature profile + full version history
- Therapist reference vault / notebook items
- AI artifact metadata (model used, confidence, completeness score)
- Twin profile history + changelogs
- Therapist edit diffs (AI output → final approved version)

**Migration rules:**
- Do not break existing flows
- All migrations must be safe and incremental
- Backward compatibility for existing summary screens is required

---

## PHASE 9 — UI / UX

Add therapist-visible affordances that make the new intelligence tangible.

**Required UI signals on every AI output:**
- "מבוסס על גישת [modality]"
- "מותאם אישית מתוך [N] סיכומים מאושרים"
- "שלמות רשומה: [X]%"
- "[N] פריטים מומלצים חסרים"
- כפתור "מצב עמוק"
- כפתור "למה ההמלצה הזו?"
- "מבוסס על סגנון התיעוד האחרון שלך"

**The therapist should always understand:**
1. What was personalized
2. What is modality-based
3. What is a formal documentation reminder
4. What still requires their clinical judgment

**Everything remains editable.** Edit tracking feeds back into the signature engine.

---

## PHASE 10 — EVALUATION FRAMEWORK

Build a minimal internal evaluation framework. This is non-negotiable for a clinical product.

**Target:** 30–50 representative cases covering:
- Generic + CBT modality
- Short history (<5 sessions) + long history (>20 sessions)
- Therapists with different documentation styles

**Metrics:**
- Usefulness score (therapist rating)
- Therapist voice match (edit distance from final approved version)
- Modality relevance
- Completeness improvement (before/after)
- Reduction in missing fields
- Hallucination rate
- Cost and latency by route
- Confidence calibration quality

**Comparison matrix:**
- Baseline (current prompts)
- New structured pipeline
- Small model only
- Routed model strategy

---

## ENGINEERING REQUIREMENTS

- Prefer deterministic structured outputs where possible
- Keep prompts modular and versioned (prompt version stored with each artifact)
- **Tests required for:**
  - Modality pack selection logic
  - Approved-summary precedence over raw drafts
  - Completeness checker accuracy
  - Therapist signature extraction
  - Model routing conditions
- Preserve backward compatibility for existing summary screens
- **Internal logging/telemetry for every generation:**
  - Selected modality pack
  - Route/model used
  - Confidence score
  - Completeness score
  - Therapist edit distance after generation
  - Time to generate

---

## GRACEFUL DEGRADATION BY DATA AVAILABILITY

```
< 5 sessions   → Generic approach-based outputs
                 Show: "הפרופיל שלך מתבסס — עוד כמה סיכומים ונדייק"

5–15 sessions  → Moderate personalization active
                 Show: "מותאם אישית בחלקו"

> 15 sessions  → Full personalization active
                 Show: "מותאם אישית מתוך [N] סיכומים מאושרים"
```

---

## DEFINITION OF DONE

This work is complete only when:

1. ✅ Modality-aware generation is live (at minimum: generic + CBT)
2. ✅ Therapist-approved edits influence future outputs
3. ✅ Pre-session prep uses approved prior summaries (not raw drafts)
4. ✅ Summaries can surface formal documentation gaps (Israeli standard)
5. ✅ CBT has a meaningful first-class implementation with completeness checking
6. ✅ Treatment plans are longitudinal and evidence-supported
7. ✅ Twin profile visibly evolves over time with therapist-facing explanation
8. ✅ Model routing exists and is configurable
9. ✅ Metrics/evaluation framework exists
10. ✅ The feature is measurably more useful to a real therapist over repeated use

---

## IMPLEMENTATION ORDER

```
Week 1  → Model routing architecture + TherapistProfile schema + data migrations
Week 2  → Modality pack system + CBT pack v1 + prompt modules
Week 3  → Pre-session prep 2.0 (JSON pipeline + approved summary precedence)
Week 4  → Session summary 2.0 + completeness checker
Week 5  → Israeli formal record support + legal positioning
Week 6  → Deep summary + therapist reference vault (internal only)
Week 7  → Treatment plan 2.0 + plan drift helper
Week 8  → Twin profile 2.0 + therapist-facing explanation layer
Week 9  → UI affordances + edit tracking → signature feedback loop
Week 10 → Evaluation framework + internal testing
```

---

## DELIVERABLES EXPECTED FROM YOU

1. Implementation plan by phase (before starting)
2. Proposed schema/data changes
3. Backend changes (services, modules, APIs)
4. Prompt/module structure with versioning
5. UI changes (screens, components, signals)
6. Model routing approach and thresholds
7. Migration strategy (safe, incremental)
8. Test plan
9. Rollout order
10. Commits in logical chunks with clear Hebrew/English messages

**Start with the implementation plan. Then execute phase-by-phase in the most stable order. Prioritize architecture that creates compounding value over time — not a one-off "smart summary" trick.**
