VirtualTherapist – MVP Product Requirements Document v1.0
Document Version: 1.0
Date: February 18, 2026
Owner: Product Leadership
Status: Final Draft – Ready for Development

Executive Summary
VirtualTherapist is a therapist-first platform that transforms clinical documentation and extends therapeutic continuity between sessions. By learning each therapist's unique style and approach, the system creates a personalized "virtual therapist twin" that continues clinical work between sessions while dramatically simplifying daily practice management.
Core Innovation: Unlike practice management tools (focused on billing/scheduling) or generic AI chatbots (disconnected from clinical context), VirtualTherapist sits at the intersection of clinical intelligence and between-session continuity—enabling therapists to be present for their clients all week without burning out.
Target Market: Independent and small-practice therapists (3–15 years experience, 15–30 active clients) who use structured modalities (CBT, integrative approaches) and struggle with documentation burden and limited between-session engagement.
MVP Timeline: 12 weeks to alpha release with 3–5 pilot therapists.

Table of Contents
Vision & Problem Statement
Target Users & Personas
Value Proposition
Product Architecture
MVP Scope Definition
User Stories
User Journey Maps
Product Roadmap
Implementation Timeline (Gantt)
Technology Recommendations
Success Metrics & Validation
Constraints & Principles
Open Questions & Risk Mitigation

1. Vision & Problem Statement
Vision (2–3 Years)
To become the default "clinical brain and continuity layer" for independent therapists and small practices worldwide. A single platform where therapists manage their day, develop rich clinical understanding of each client, and safely extend therapy between sessions through personalized, therapist-controlled virtual companions.
Over time, this extends to adjacent caring professions: coaches, counselors, dietitians, and other practitioners who rely on continuity, documentation, and between-session engagement.
The Problem
For Therapists:
Temporal constraint: Therapy is confined to 50 minutes per week, while clients' lives—and crises—unfold continuously.
Documentation burden: Clinical notes are cognitively expensive, time-consuming, and often delayed or incomplete. This contributes directly to burnout.
Fragmented memory: With 20–30 active clients, therapists struggle to maintain clear mental models of each client's trajectory, recent progress, and subtle changes.
Between-session gap: task  and behavioral practice are critical to outcomes, but therapists have no scalable way to support or monitor clients between appointments without manual texts/calls.
For Clients:
Loss of momentum: The therapeutic thread often breaks between sessions. task  is forgotten, motivation wanes, and clients feel disconnected from the process.
Lack of real-time support: Clients face challenges all week but have no structured way to stay connected to their treatment plan.
Existing Solutions Fall Short:
EHRs and practice management systems focus on billing, scheduling, and compliance—not clinical intelligence or continuity.
Generic AI chatbots lack clinical context, therapist style, and proper safety boundaries.
Manual systems (notebooks, Word docs, WhatsApp) are fragmented and unsustainable at scale.
VirtualTherapist solves this by becoming the therapist's external clinical memory and between-session proxy—built on their style, governed by their rules, and optimized for their workflow.

2. Target Users & Personas
Primary Persona – "Independent CBT/Integrative Therapist"
Demographics:
Licensed therapist (Psychologist, LCSW, MFT, or equivalent)
3–15 years of clinical experience
Private practice or small group practice
15–30 active clients per week
Clinical Profile:
Modality: CBT, integrative, or evidence-based approaches that use structured task 
Documentation style: Mix of handwritten notes, Word/Google Docs, partial EHR use
Often delays documentation due to cognitive load and time pressure
Technology Profile:
Not highly technical, but comfortable with web tools if value is clear
Uses basic tools: Google Calendar, email, WhatsApp for client communication
Frustrated by complex systems with steep learning curves
Pain Points (Ranked by Intensity):
Documentation overload: Feels like administrative burden rather than clinical value
Mental fragmentation: Difficulty maintaining clear picture of all clients simultaneously
Between-session guilt: Wants to support clients more but cannot sustainably text/call everyone
Limited continuity: Clients forget task  or lose momentum between sessions
Goals:
Reduce time spent on documentation without sacrificing quality
Feel "on top of" every client's story and progress
Extend therapeutic continuity between sessions in a scalable, ethical way
Maintain clinical control and responsibility
Quote:
"I love the actual therapy work. I hate spending my evenings writing notes and feeling guilty that I can't be there for my clients between our weekly sessions."

3. Value Proposition
For Therapists
Primary Value:
"Capture session insights in under 2 minutes, maintain a living clinical picture of every client, and extend your work between sessions—without working more hours."
Key Benefits:
Frictionless documentation: Voice recap → structured summary in therapist's style, ready to approve in 60 seconds.
Clinical clarity: Insight Summaries synthesize treatment trajectory, themes, and next steps for every client.
Between-session continuity: Safe, structured task  support and check-ins that feel like the therapist's presence, not a bot.
Cognitive offload: The system remembers everything, so the therapist can focus on being present in sessions.
Professional growth: Personalized learning suggestions based on actual clinical patterns (later phases).
For Clients (Indirect Benefits)
Primary Value:
"Therapy doesn't end when you leave the room—it continues through the week with guidance that feels like your therapist."
Key Benefits:
Consistency: task  reminders and check-ins maintain momentum between sessions.
Felt support: Brief, therapist-style messages provide continuity without overwhelming.
Better outcomes: Higher task  completion correlates with treatment success.
Differentiation from Competitors
Dimension
EHR/Practice Management
AI Chatbots
VirtualTherapist
Focus
Billing, scheduling, compliance
Generic conversations
Clinical intelligence + continuity
Clinical Memory
Static notes
No memory
Rich, evolving understanding per client
Therapist Style
Template-based
Generic
Learned from therapist's actual work
Between-Session Support
None
Unstructured, risky
Structured, safe, therapist-controlled
Documentation
Manual typing required
Not applicable
Voice → auto-summary in therapist's voice


4. Product Architecture
High-Level Architecture Diagram
text
┌─────────────────────────────────────────────────────────────────┐
│                    THERAPIST WEB APPLICATION                     │
│  (Today View, Patient List, Patient Profile, Session Mgmt)      │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                   API GATEWAY / BACKEND                          │
│                                                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │ Auth Service │  │Session Service│  │Patient Service│          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
│                                                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │Summary Service│  │ Twin Service │  │In-Between Svc│          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                      AI PROCESSING LAYER                         │
│                                                                   │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │  ASR/STT Engine │  │  LLM Services   │  │   OCR Engine    │ │
│  │  (Voice Recap)  │  │ (Summarization, │  │  (Handwriting)  │ │
│  │                 │  │  Insights, Twin, │  │   [Phase 2]     │ │
│  │                 │  │  In-Between)    │  │                 │ │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                    DATA PERSISTENCE LAYER                        │
│                    (PostgreSQL Database)                         │
│                                                                   │
│  Tables:                                                          │
│  • Therapists           • Patients                               │
│  • Sessions             • Summaries (approved)                   │
│  • InBetweenFlows       • InBetweenEvents                        │
│  • TherapistProfiles    • AuditLogs                              │
└─────────────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│              CLIENT-FACING CHANNEL (In-Between)                  │
│  Simple web interface or messaging (SMS/WhatsApp-like)          │
│  Managed by In-Between Flow Service                              │
└─────────────────────────────────────────────────────────────────┘

Architectural Principles
Separation of Concerns:
Frontend never talks directly to AI providers—only to backend services.
AI layer is abstracted behind service interfaces, allowing provider changes without product rewrites.
Data Integrity:
All clinical content persisted in relational database with clear ownership and audit trails.
Only approved summaries feed downstream logic (Insights, Twin, In-Between).
Safety by Design:
In-Between flows modeled as explicit state machines with templates and boundaries, not free-form chat.
All AI-generated client-facing content goes through therapist-defined constraints.
Scalability Path:
Stateless API services enable horizontal scaling.
Async job queue for heavy AI processing (summarization, insight generation).
Separate read/write concerns as needed in later phases.

5. MVP Scope Definition
5.1 Must-Have Features (MVP v0.1)
Feature 1: Therapist Workspace
Description:
Secure web application providing core navigation and clinical overview.
Components:
Authentication: Secure login with password reset, basic 2FA support.
Today View: Dashboard showing today's scheduled sessions with:
Client name and appointment time
Last session snippet or "No summary yet"
Active In-Between Flow indicator
Quick access to Prep Brief or Insight Summary
Patient List: Sortable/filterable list of all clients with status (Active/Paused/Closed).
Patient Profile Page:
Session history timeline
Approved session summaries
Insight Summary (treatment synthesis)
Controls to enable/disable In-Between Flow
Acceptance Criteria:
Therapist can log in and see today's schedule in under 5 seconds.
Clicking any client opens their complete profile with full history.
All navigation is intuitive without training documentation.

Language Support (MVP)
The system must fully support Hebrew for:
Therapist-facing UI labels and copy (at least a Hebrew locale for core screens).
Session summaries and Insight Summaries generated from Hebrew inputs.
In-Between Flow messages sent to clients in Hebrew.
The system should also support English in parallel (for future markets and documentation).
LLM and ASR providers must be configured and tested for high-quality Hebrew input/output (including right-to-left text handling in the UI).

Feature 2: Session Capture & Voice Recap
Description:
Effortless post-session documentation via voice recording, transcription, and AI-generated summary.
Flow:
Therapist finishes session and opens client profile.
Clicks "Voice Recap" button.
Sees brief prompt: "Cover: client presentation, interventions, response, task , risk level. 1–2 minutes."
Records audio directly in browser or via mobile device.
System transcribes audio (ASR).
AI generates structured summary in therapist's style (SOAP or free-form with headers).
Therapist reviews side-by-side: original transcript + draft summary.
Therapist edits as needed and clicks "Approve".
Summary is locked and added to session history.
Alternative Input Methods:
Paste text summary from external document.
Upload short Word/PDF file (later: handwritten note photo with OCR).
Technical Requirements:
ASR latency: < 30 seconds for 2-minute recording.
Summary generation: < 60 seconds.
Transcript and summary stored separately for audit.
Acceptance Criteria:
Therapist can complete entire flow (record → approve) in under 3 minutes.
Generated summaries feel natural and match therapist's prior writing style (validated qualitatively in pilot).
90%+ of summaries require ≤ 2 minor edits before approval.

Feature 3: Insight Summary per Client
Description:
AI-generated synthesis of a client's full treatment trajectory based on all approved session summaries.
Content Includes:
Presenting issues and history: Condensed from early sessions.
Key themes: Recurring patterns, beliefs, or behaviors.
Progress indicators: What's improved, what's stable, what's stuck.
Current treatment focus: Based on recent sessions.
Suggested next steps: 2–3 clinically grounded hypotheses or directions.
Risk assessment summary: Aggregated risk signals over time.
Triggers:
Automatically updated after each new approved summary.
Therapist can manually trigger regeneration.
Acceptance Criteria:
Insight Summary accurately reflects treatment narrative (therapist validation).
Summary length: 200–400 words, scannable in 60–90 seconds.
Includes actionable suggestions, not just description.

**Insight Summary – Optional Therapist Recommendations (Phase 2+)**
In later phases (after MVP v0.1), the Insight Summary can include an optional section: “Suggested Directions & Resources (For You)”:
- 2–3 brief suggestions like:
  - “Given these themes and your CBT style, many therapists explore [technique X] or [technique Y].”
  - “Here is a short worksheet/article that aligns with how you typically work with similar cases.”
- These suggestions must:
  - Be explicitly labeled as non-binding ideas.
  - Never include diagnoses, medication, or crisis instructions.
  - Be dismissible (therapist can hide or mark as “not relevant”).

Feature 4: In-Between Flow v1 (task  + Check-ins)
Description:
Structured between-session support focused on a single template: task  monitoring with daily/periodic check-ins.
Template: "Weekly task  + Daily Check-ins"
Configuration (Therapist Side):
Task description in therapist's words (e.g., "Practice 5-minute exposure to social situations daily").
Frequency: daily, every other day, or custom schedule.
Tone: formal, neutral, warm.
Boundaries:
No new topics beyond the defined task.
No crisis support (redirect to therapist/hotline).
No diagnoses or medication advice.

Client Experience (MVP v0.1):
- Receives brief reminder messages at scheduled times (for tasks and/or upcoming sessions).
- Messages are **one-way only** from the system (on behalf of the therapist) to the client/parent.
- The system does **not** read, parse, or act on client replies in MVP v0.1.


Supported Channel (MVP requirement)
In-Between Flow must support WhatsApp as a primary client-facing channel in MVP, via an official or reliable API/connector (e.g., WhatsApp Business API via Twilio or similar provider).

The channel abstraction should allow future support for additional channels (web, SMS), but WhatsApp is non-negotiable for MVP pilot usage.

**MVP Limitation – One-Way Only (Phase C)**  
For the first version of the In-Between / Messaging feature, all WhatsApp messages are **one-directional only** (therapist → client/parent).  
The system does **not** read, parse, or act on client replies in MVP v0.1.  
Structured replies and reporting based on replies will be introduced in a later phase, once safety, misuse, and prompt-injection risks are fully addressed.

Feature 5: Therapist Profile (Twin v0.1)
Description:
Internal representation of therapist's clinical style, automatically learned from approved summaries and adjustable by therapist.
Learned Attributes:
Language patterns: Common phrases, terminology preferences, level of formality.
Clinical approach: Inferred modalities (CBT, ACT, psychodynamic, etc.) based on intervention descriptions.
task  style: How therapist typically structures and assigns between-session tasks.
Risk sensitivity: How therapist describes and categorizes risk levels.
Boundaries: Implicit "do's and don'ts" from historical notes.
Therapist Controls:
View Current Profile: Simple dashboard showing:
Detected style summary (2–3 paragraphs).
Sample phrases the system associates with the therapist.
Current modality tags.
Adjust Settings:
Tone slider: Formal ↔ Warm.
Directiveness slider: Exploratory ↔ Directive.
Explicit prohibitions (checkboxes):
"Never suggest medication."
"Never provide diagnoses."
"Avoid religious/spiritual content."
Custom free-text rules.
Reset/Retrain: Option to clear profile and rebuild from scratch.
Technical Implementation:
Profile updated incrementally after each approved summary.
Uses embeddings and pattern matching to extract style features.
Stored as structured JSON with versioning for audit.
Acceptance Criteria:
After 10–15 approved summaries, profile accurately reflects therapist's self-described style (90% agreement in pilot survey).
Therapist adjustments immediately affect downstream AI outputs (summaries, In-Between messages).
Profile remains stable and doesn't "drift" without therapist input.

**Therapist Twin – Learning Hooks (Phase 3)**
The Therapist Twin can expose learning prompts that tie the twin profile to targeted growth:
- Example: “You often work with social anxiety using behavioral experiments. Would you like 2 short, up-to-date examples or scripts to broaden your repertoire?”
- The therapist can fully opt in/out of such prompts. No recommendations are shown without explicit consent.


Feature 6: Safety & Governance (Baseline)
Description:
Foundational safety measures ensuring ethical, responsible AI use in clinical context.
Audit Logging:
Every AI-generated output logged with:
Timestamp, therapist ID, client ID (if applicable).
Model version and prompt template used.
Full input context and generated output.
Therapist actions (approved/edited/rejected).
Crisis Detection & Response:
Keyword-based detection for high-risk language in client inputs (In-Between Flow).
Automated response protocol:
Immediate safe redirection (crisis resources).
Alert sent to therapist.
Flow paused until therapist reviews.
Compliance Readiness:
Data encryption at rest and in transit.
Role-based access control (therapist sees only their clients).
Audit trail supports compliance reviews (HIPAA readiness, GDPR-aligned data handling).
Acceptance Criteria:
100% of AI outputs logged and retrievable for review.
Crisis detection triggers appropriate response in 100% of test cases.
No therapist can access another therapist's data.

5.2 Should-Have Features (Post-MVP or Late MVP)
OCR for handwritten notes: Upload photo of hand-written notes → text → summary.
Additional In-Between templates: Mood tracking, thought records, mindfulness logs, exposure hierarchies.
Therapist growth suggestions: Personalized learning content (articles, techniques) based on practice patterns.
Basic calendar integration: Read-only sync with Google Calendar to auto-populate Today View.
Multi-language support: Hebrew, Spanish, French (depending on market expansion).

5.3 Explicitly Out of Scope (MVP v0.1)
Full practice management: Billing, insurance claims, complex scheduling, client intake forms.
Rich patient portal: Multi-topic messaging, file exchange, treatment plans visible to clients.
Real-time AI therapy sessions: System is not a replacement therapist; it extends human therapist work.
Multi-clinician/team features: Supervision workflows, shared caseloads, group practices.
Deep third-party integrations: Beyond minimal ASR/LLM providers, no complex EHR/CRM sync.

6. User Stories
Therapist Stories
US-T1: Capture a session quickly in my own style
As a therapist, I want to record a short voice recap right after a session and get a clean, structured summary draft, so that I can keep high-quality documentation without spending extra time typing when I'm tired.
US-T2: See my day at a glance
As a therapist, I want to see all of today's sessions with a short reminder of where I left off with each client, so that I can mentally prepare for the day and each session in a few minutes.
US-T3: Understand a client's trajectory over time
As a therapist, I want to see an "Insight Summary" that synthesizes a client's history, themes, and progress, so that I can quickly reconnect with the bigger picture and choose the best focus for the next session.
US-T4: Extend the work between sessions without burning out
As a therapist, I want to enable a simple between-session task  + check-in flow for selected clients, so that clients stay engaged and accountable without me manually texting them all week.
US-T5: Control my virtual "twin"
As a therapist, I want to see how the system represents my style and set clear boundaries on what it can and cannot say or do, so that any messages or suggestions it generates still feel like they come from me and respect my ethics.
US-T6: Review between-session activity before the next session
As a therapist, I want to see a concise report of a client's task  and check-ins before each session, so that I can start sessions deeper and spend less time asking "So, how was your week?"
US-T7: Trust and verify AI outputs
As a therapist, I want to review and approve any AI-generated summaries or client-facing content before they are finalized, so that I remain clinically responsible for the record and the ongoing care.

Client Stories (Minimal, MVP Logic Level)
US-C1: Get clear, timely reminders about task 
As a client, I want to receive short, clear reminders about my agreed task  tasks between sessions, so that I remember what to do and feel supported without having to chase my therapist.
US-C2: Report my progress in a simple way
As a client, I want to quickly indicate what I did, how it felt, and any small issues, so that my therapist has context next time without me writing long reports.
US-C3: Feel continuity and safety
As a client, I want any between-session messages to feel like they come from my therapist's approach and respect clear boundaries, so that I feel held by the process but not misled into thinking an AI is a replacement for my therapist.

7. User Journey Maps
7.1 Therapist Journey: Adoption Through First Month
Persona: Independent CBT/integrative therapist, ~25 active clients, uses task  assignments.

Phase 1: Onboarding & First Day
Step 1: Invitation & Setup
Therapist signs up via secure link, creates account, sets basic profile details.
Reads short intro: "VirtualTherapist is not a billing/booking system—it's your clinical brain and continuity layer."
Manually adds 3–5 existing clients (name, basic info, status: active).
Step 2: First Look at Today View
On first "live" day, therapist opens app and sees Today View.
Sees 4 clients scheduled (manually entered times).
Each row shows:
Client name, time
Last session snippet (empty for now: "No summary yet")
In-Between Flow status (none active yet)
Clicks one client to explore Patient Profile page—sees empty or minimal history.
Step 3: Expectations Set
Brief in-product tour explains:
"After sessions, use Voice Recap to capture what matters."
"Insight Summaries appear after you have a few approved notes."
"Between sessions, you can enable task  flows for selected clients."
Emotional State: Curious, slightly skeptical, willing to try if it doesn't add friction.

Phase 2: Using Voice Recap After Sessions
Step 4: First Session of the Day
Therapist finishes a session at 10:00am.
Instead of grabbing notebook or opening Word, they open VirtualTherapist on phone or laptop.
Navigate to client, click "Voice Recap".
Step 5: Recording the Recap
Small overlay reminds them what to cover: "Client presentation, interventions, response, task , risk."
Therapist speaks freely for 90 seconds, covering key points naturally.
No forms to fill, no typing required.
Step 6: Draft Summary Arrives
30 seconds later, draft summary appears.
Structured format (SOAP-like) with familiar language.
Therapist skims, fixes two small wording issues, adds one sentence the AI missed.
Clicks "Approve". Summary joins session history.
Step 7: Impact After a Few Sessions
After repeating this for 8–10 sessions across multiple clients over one week:
Therapist notices it feels easier and faster than writing from scratch.
Documentation is more consistent and timely than before.
VirtualTherapist begins building richer Insight Summaries in background.
Emotional State: Pleasantly surprised, beginning to trust the system, documenting more consistently.

Phase 3: First Insight Summary & "Twin Awareness"
Step 8: Seeing Insight Emerge
After 5 approved summaries for one specific client, therapist sees new panel: "Insight Summary".
It highlights:
Key themes ("persistent social anxiety with avoidance patterns")
Progress ("reduced avoidance behaviors, increased exposure tolerance")
Potential focus areas ("explore core beliefs about judgment and self-worth")
Therapist reads and thinks: "This is close to how I think; I'd tweak X and Y, but it's useful."
Step 9: Meeting Their "Twin"
System surfaces a "Therapist Profile" view:
"Here's how we currently see your style based on your summaries: tone is warm and exploratory; you often use CBT techniques with emphasis on behavioral experiments; typical task  involves graded exposure and thought records."
Therapist adjusts:
Tone slider: slightly more neutral than warm.
Adds explicit rule: "Do not suggest medication. Do not give diagnoses."
Understands that any client-facing automation will be constrained by this profile.
Emotional State: Intrigued, feeling a sense of partnership with the system, more confident about automation.

Phase 4: Enabling In-Between Flow for a Single Client
Step 10: Choosing a Candidate Client
Therapist identifies one client where task  is critical and therapeutic relationship is stable.
After a session defining task  (exposure tasks), therapist clicks "Enable between-session support" on that client's profile.
Step 11: Configuring the Flow
Simple form appears:
Task description: "Practice 5-minute social interaction with coworker daily, rate anxiety before/after."
Frequency: Daily at 8:00 PM.
Tone: Warm, encouraging.
Boundaries: No crisis support, no new topics beyond this task.
Therapist previews sample messages client will receive.
Confirms and activates flow for one week.
Step 12: Week in Motion (Therapist's Perspective)
Over the week, therapist does not manually check messages.
Trusts that VirtualTherapist is sending scheduled prompts and logging client responses.
Receives one mid-week alert: "Client reported high distress (8/10) on Day 3. Review recommended."
Therapist reviews, sends brief personal follow-up via usual channel (text/email).
Emotional State: Relieved to have structured support running without constant oversight, appreciates safety alert system.

Phase 5: Pre-Next Session Review
Step 13: Before the Next Session
Morning of next session (one week later), therapist opens Today View.
For client with active In-Between Flow, sees badge: "task  week complete – 5/7 days logged."
Step 14: Reviewing the Report
Clicks client, finds concise between-session report:
Completion: 5 out of 7 days
Average pre-exposure anxiety: 7.2/10
Average post-exposure anxiety: 5.4/10
Key quote: "Felt too anxious to try in front of my boss on Thursday, but managed with peer on Friday."
Pattern note: "Avoidance primarily around authority figures."
Insight Summary has been updated with this behavioral data.
Step 15: Starting the Session Deeper
When client arrives, therapist already knows roughly what happened.
Session starts: "I saw you did really well with the exposures this week—five out of seven. Tell me about the two days you skipped, especially Thursday with your boss."
Less time on logistics, more time on meaning-making and deepening the work.
Emotional State: Confident, prepared, clinically effective, feels like they're finally "staying with" the client all week.

Phase 6: Reflection & Decision to Expand
Step 16: After a Few Weeks
Therapist has used Voice Recap for ~20 sessions, In-Between Flow for 3 clients.
Realizes:
Documentation feels lighter, more timely, less of a chore.
Feeling more "on top of" all cases simultaneously.
For clients with In-Between support, task  adherence noticeably improved.
Step 17: Decision Point
Decides to:
Expand In-Between support to 5 more clients.
Rely on Insight Summaries regularly for supervision prep.
Provide structured feedback to VirtualTherapist team on where system feels too generic or needs refinement.
Emotional State: Committed user, early advocate, sees VirtualTherapist as essential to practice.

7.2 Client Journey (In-Between Flow)
Scenario: Client in CBT for social anxiety, therapist activates one-week task  flow.

Monday Morning, 9:00 AM (First Session)
Therapist and client agree on task : practice brief social interactions daily.
Client leaves session with clear task.
Monday Evening, 8:00 PM
Client receives first message (via SMS or web link):
"Hi [Name], this is a reminder from your therapist about this week's practice: try one 5-minute social interaction today. Rate your anxiety before and after (1–10). How did it go?"
Client responds: "Did it—talked to coworker about weekend. Anxiety was 7 before, 5 after."
System logs response, sends brief acknowledgment: "Great work. Same plan tomorrow."
Tuesday–Friday
Similar daily prompts and brief exchanges.
Client completes task 4 out of 5 days, skips Thursday due to high anxiety.
Thursday Evening
Client responds: "Couldn't do it today. Too anxious (9/10). Felt like I'd mess up in front of my boss."
System detects elevated distress, sends: "That's okay—this is part of the process. If you're feeling overwhelmed, please reach out to your therapist or [crisis resource]. Otherwise, let's try again tomorrow with a peer instead."
Alert sent to therapist for review.
Saturday Morning
Client receives summary prompt: "You practiced 4 out of 6 days this week—well done. Any overall reflections before your next session?"
Client responds: "Easier with peers, still scared of authority figures."
Next Monday Session
Therapist begins with: "I saw your week—really solid effort. Let's talk about that moment on Thursday with your boss..."
Client feels heard, supported, and that therapy is "always on," not just during sessions.
Emotional State: Client feels accountable, supported, connected to treatment between sessions—not abandoned or forgotten.

8. Product Roadmap (12–18 Months)
Phase 0: Foundations (Months 0–1)
Focus: Clarity and alignment before building.
Deliverables:
Finalize MVP Product Decisions (this document).
Define Therapist Persona v1 and refine Golden Path.
Specify Therapist Twin v0.1 and In-Between Flow v1.
Conduct desirability validation with 5–10 target therapists (interviews, concept tests).
Select tech stack and set up development environment.
Outcome: Green light to build with validated assumptions.

Phase 1: MVP v0.1 – Golden Path End-to-End (Months 1–3)
Focus: One complete flow working for a small set of therapists.
Key Features:
Therapist Web Workspace: Auth, Today View, Patient List, Patient Profile.
Session & Summary Flow: Voice Recap → transcription → summary draft → approval.
Insight Summary v0.1: Per-client treatment synthesis.
In-Between Flow v1: Single task  + check-ins template.
Therapist Profile (Twin v0.1): Basic inferred attributes + simple controls.
Baseline safety & logging.
Milestones:
Week 6: Core flows functional (voice recap → summary approval).
Week 9: In-Between Flow operational.
Week 12: Private alpha with 3–5 therapists, structured feedback loops.
Success Metrics:
80%+ of sessions documented via Voice Recap (vs. manual typing).
Therapists report "documentation feels easier" (qualitative + Likert scale ≥ 4/5).
At least one In-Between Flow active per therapist; task  completion rate improves (therapist-reported).

Phase 2: MVP v0.2 – Robustness & Fit (Months 4–6)
Focus: Polish, onboarding, and broader usability.
Key Features:
Improved summary quality and therapist controls (regeneration, tone adjustments, feedback loop).
Expand In-Between Flow templates (add mood tracking variant).
Introduce light "therapist growth" hints (optional module: suggest relevant techniques/content based on patterns).
Enhance Twin UX (clearer explanations, better boundary controls).
Support one external channel for In-Between (SMS or WhatsApp integration).
Performance hardening: response time optimization, error handling, basic scaling.
Milestones:
Week 18: Closed beta with 10–20 therapists across 2–3 practice types.
Week 24: Onboarding flow tested and refined; churn minimized.
Success Metrics:
90%+ of beta therapists use system weekly after initial onboarding.
In-Between Flow adoption: 40%+ of clients have at least one active flow.
NPS ≥ 40 among beta cohort.

Phase 2 extension – Structured Replies, Reporting & Safety
- Add optional structured client replies for tasks (done/not done/partially, 1–10 difficulty).
- Build Pre-Next-Session Report based on these replies (completion rate, difficulty, key quotes, red flags).
- Introduce crisis keyword detection for client replies, with safe response and therapist alerts.


Phase 3: Productization & Differentiation (Months 7–12)
Focus: From "it works" to "I can't work without it."
Key Features:
OCR for handwritten notes → text → summary (for high-fit therapists).
Deeper Therapist Twin:
Better modality detection (CBT vs. ACT vs. psychodynamic, etc.).
More nuanced style & boundary controls.
Richer In-Between library: 3–5 well-defined flows (exposure, thought records, mood tracking, brief DBT skills).
Therapist Growth Layer v1: Personalized learning suggestions (articles, short techniques) based on clinical patterns.
Optional: Read-only calendar integration (Google Calendar sync).
Mobile-responsive UI optimization.
Milestones:
Month 9: Feature-complete product ready for early access launch.
Month 12: Launch early access with monetization (tiered pricing).
Success Metrics:
100+ active therapists (early access).
60%+ of therapists use In-Between Flows for ≥3 clients.
Revenue validation: $50–150/therapist/month, 6-month retention ≥ 70%.

Phase 3 (extended) – Therapist Growth Layer v1 (Recommendations)
Focus: turn the Twin + Insight into a light clinical recommender for the therapist (not for clients).
New capabilities:
Based on the Therapist Twin and Insight Summaries, the system can surface non-intrusive, optional recommendations such as:
Relevant articles, short summaries, or clinical blog posts that match the therapist’s main modalities and the client’s current themes (eg, CBT for social anxiety, graded exposure examples).
Concrete intervention ideas, phrased as “many CBT/ACT therapists in similar situations might consider…”, never as fixed prescriptions.
Recommendations are always:
Clearly labeled as “Suggestions for you as a therapist”, not as treatment plans.
Visible only to the therapist, never pushed directly to clients.
Free of medication or diagnostic advice (no pharmacology, no labels).
Examples:
In an Insight Summary for a client with persistent social avoidance:
“Given the pattern of avoidance around authority figures and your CBT-oriented style, you may want to consider: (1) graded exposure hierarchy with bosses/managers, (2) a short values-based exercise from ACT on ‘courage and self-respect’. Here are 2 brief resources you can skim (optional).”
In the Twin Profile view:
“You frequently work with OCD using exposure and response prevention. Would you like 2–3 recent brief articles or worksheets to refresh/expand your toolkit?”
Constraints:
All content must be evidence-based or therapist-approved (curated library, not random web search).
The system never ranks “best therapy” for a client; it only offers ideas and resources for the therapist to consider.

Phase 4: Expansion & Scale (Months 13–18)
Focus: New verticals and institutional readiness.
Key Features:
Extend to adjacent professions: coaches, dietitians, wellness practitioners (tailored In-Between flows).
Deeper analytics for therapists and supervisors (progress dashboards, caseload insights).
Multi-therapist practice support (small teams, shared clients, supervision workflows).
Advanced learning/growth modules (micro-courses, curated reading lists).
White-label or partnership opportunities (clinics, group practices).
Milestones:
Month 15: Launch vertical-specific offerings (coaching, nutrition).
Month 18: 500+ therapists, partnerships with 3–5 small practice networks.
Success Metrics:
500+ active therapists across 2–3 verticals.
80% 12-month retention.
NPS ≥ 50.

9. Implementation Timeline (Gantt Overview)
Total Duration: 12 weeks to MVP v0.1 alpha release.
text
Week 1–2: Architecture & Core Data
├─ Finalize DB schema (Therapists, Patients, Sessions, Summaries, etc.)
├─ Backend skeleton (API, auth, basic logging)
└─ Minimal frontend shell (login, empty Today View)


Week 3–4: Session & Summary Flow
├─ Patient/session CRUD endpoints
├─ Voice Recap endpoint + ASR integration
├─ Session Summarizer (LLM-based, first version)
└─ UI: create session, record recap, approve summary
    Milestone: Therapist can document sessions via voice


Week 5–6: Insight Summary & Twin v0.1
├─ Insight Summary generator (aggregate approved summaries)
├─ Therapist Profile logic (extract stylistic patterns)
└─ UI: Insight panel on Patient Profile, Therapist Profile page
    Milestone: Therapist sees living Insight per client + profile summary


Week 7–9: In-Between Flow v1
├─ Data model for InBetweenFlows and InBetweenEvents
├─ Flow engine for one template (task  + check-ins)
├─ AI prompts for client-facing messages within constraints
├─ Therapist UI to configure/enable flow
├─ Minimal client-facing interface (test channel)
└─ Pre-session report generation
    Milestone: Full In-Between week functional, report ready before next session


Week 10–12: Hardening & Pilot Prep
├─ UX polish (copy, error states, loading indicators)
├─ Analytics/logs for pilot measurement
├─ Onboarding flow for pilot therapists
├─ Dry-runs with synthetic data, then 1–2 real therapists
└─ Adjust prompts, boundaries, flows based on early feedback
    Milestone: MVP v0.1 ready for 3–5 therapist alpha


Week 13+: Alpha feedback, iterate into v0.2

Critical Path:
Voice Recap → Summary (Weeks 3–4) blocks Insight Summary (Weeks 5–6).
Therapist Profile (Week 6) blocks In-Between Flow message generation (Weeks 7–9).
In-Between Flow (Weeks 7–9) is MVP's differentiator—highest priority.

10. Technology Recommendations
Backend & Data Layer
Language/Framework:
Python with FastAPI (recommended)
Rationale: Fast development, strong AI/ML ecosystem, excellent async support, easy to integrate with LLM providers.
Alternative: Node.js with NestJS if team has stronger JS background.
Database:
PostgreSQL (recommended)
Rationale: Relational model fits clinical data structure (therapists → patients → sessions → summaries), mature, excellent JSON support for flexible fields (e.g., TherapistProfile config).
ORM & Migrations:
SQLAlchemy + Alembic (Python)
Rationale: Industry standard, strong migration support, type-safe queries.
API Style:
RESTful JSON APIs for MVP.
Consider GraphQL in later phases if client querying becomes complex.

Frontend
Framework:
React + TypeScript
Bundler: Vite (for speed) or Next.js (if SSR needed later).
Router: React Router v6.
UI Toolkit:
Tailwind CSS + headless component library (Radix UI or Headless UI)
Rationale: Fast prototyping, highly customizable, accessible by default.
Alternative: Chakra UI or Material-UI for faster out-of-box components.
State Management:
React Query (TanStack Query) for server state.
Zustand or Context API for local UI state.

AI & ML Layer
LLM Provider:
Anthropic Claude or OpenAI GPT-4 (recommended)
Rationale: Strong instruction-following, safety features, multilingual (English/Hebrew), API reliability.
Ensure fallback strategy (secondary provider or local model) for critical paths.
Speech-to-Text (ASR):
OpenAI Whisper API or Deepgram
Rationale: High accuracy, multilingual support, reasonable latency (< 30s for 2-min audio).
Multilingual (Hebrew + English) Support
Choose LLM and ASR providers with strong support for Hebrew and English.
Prompt templates, evaluation, and testing must explicitly cover Hebrew use cases (session recap, summaries, insights, and client messages).
Frontend must support RTL layout where applicable (Hebrew UI), including correct rendering of mixed Hebrew/English text.

OCR (Phase 2):
Google Cloud Vision API or Azure Computer Vision
Rationale: Strong handwriting recognition, multilingual.
Service Abstraction:
Wrap all AI calls in internal service classes:
SummarizerService, InsightService, TwinService, InBetweenOrchestrator.
Never expose LLM API keys or call providers directly from frontend.

Infrastructure & DevOps
Hosting:
PaaS (Platform-as-a-Service): Render, Railway, Fly.io, or Heroku-style
Rationale: Managed Postgres, easy scaling, minimal DevOps overhead for MVP.
Plan migration to AWS/GCP/Azure later for enterprise needs.
Secrets Management:
Environment variables via PaaS secret store initially.
Migrate to HashiCorp Vault or cloud-native secret managers in Phase 2.
Logging & Monitoring:
Centralized Logging: Logtail, Datadog, or ELK stack.
Error Tracking: Sentry or Rollbar.
APM: Datadog or New Relic for API performance monitoring.
CI/CD:
GitHub Actions for automated testing and deployment pipeline.
Run unit tests, integration tests, linting on every PR.
Auto-deploy to staging on merge to main.
Manual promotion to production.
Async Job Processing:
Celery (Python) or Bull (Node.js) with Redis as broker.
Use for heavy AI tasks (summary generation, insight updates) to keep API responsive.

Security & Compliance
Authentication:
OAuth 2.0 + JWT tokens.
Password hashing: bcrypt or Argon2.
Optional 2FA via TOTP (Google Authenticator).
Data Encryption:
At rest: Database-level encryption (PG native or cloud provider).
In transit: TLS 1.3 for all API calls.
Audit Logging:
Log every:
AI generation event (input, output, model version).
Therapist action (approve, edit, delete).
Access to sensitive patient data.
Store logs in append-only table or dedicated service.
Compliance Readiness:
HIPAA: Not required for MVP (therapists are the "covered entities"), but design with HIPAA principles:
Minimum necessary access.
Audit trails.
Data retention policies.
GDPR: Data export/deletion capabilities, clear consent flows.

Product & Collaboration Tools
Product Management:
Linear or Notion
Use for backlog, sprint planning, roadmap.
Keep it minimal—focus on Golden Path.
Design:
Figma for UI/UX mockups and prototyping.
Documentation:
Markdown in Git repo for specs, ADRs (Architecture Decision Records).
Notion or Confluence for collaborative docs and pilot feedback summaries.
Communication:
Slack or Discord for team comms.
Structured pilot feedback forms (Typeform or Google Forms) for alpha/beta therapists.

11. Success Metrics & Validation
Primary Metrics (MVP v0.1, 3–5 Therapists, 6 Weeks)
Adoption Metrics
Voice Recap Usage:
Target: ≥ 80% of sessions documented via Voice Recap (vs. manual typing or skipped).
Measurement: Track session creation vs. approved summaries.
In-Between Flow Activation:
Target: ≥ 1 active flow per therapist, covering ≥ 20% of their clients.
Measurement: Count of active flows per therapist.
Quality Metrics
Summary Accuracy:
Target: ≥ 90% of summaries require ≤ 2 minor edits before approval.
Measurement: Edit count per summary (tracked in audit logs).
Therapist Satisfaction (Qualitative):
Survey questions (5-point Likert scale):
"Documentation feels less burdensome with VirtualTherapist." → Target: ≥ 4.0 avg.
"I feel more on top of each client's story and progress." → Target: ≥ 4.0 avg.
"I trust the AI-generated summaries and insights." → Target: ≥ 3.8 avg.
"I would recommend this to colleagues." (NPS proxy) → Target: ≥ 70% promoters.
Behavioral Metrics
Time to Summary Approval:
Target: Median < 3 minutes from session end to approved summary.
Measurement: Timestamp tracking.
In-Between task  Completion (Therapist-Reported):
Target: Therapists report improved task  completion for clients with active flows vs. those without.
Measurement: Post-pilot survey question: "Have you noticed a difference in task  adherence for clients using In-Between support?" (Yes/Somewhat/No).
Safety Metrics
Crisis Handling:
Target: 100% of crisis keywords detected and handled appropriately (safe redirect, therapist alert).
Measurement: Manual review of 100% of In-Between interactions during alpha.
Zero Harmful Outputs:
Target: Zero instances of inappropriate advice (diagnoses, medication suggestions, crisis mismanagement).
Measurement: Manual audit + therapist-reported incidents.

Key Hypotheses to Validate
Hypothesis 1: Voice Recap Reduces Documentation Burden
Validation: 80%+ adoption rate + therapist feedback "documentation feels easier" (Likert ≥ 4.0).
Hypothesis 2: AI-Generated Summaries Are Clinically Acceptable
Validation: 90%+ summaries approved with minimal edits + qualitative feedback confirms accuracy and style match.
Hypothesis 3: In-Between Flow Creates Meaningful Continuity
Validation: Therapists report higher task  completion and better session depth; clients (via therapist proxy) feel more supported between sessions.
Hypothesis 4: Therapists Trust the "Twin" When They Control It
Validation: Therapists actively adjust Twin settings (≥ 50% make at least one adjustment) and feel comfortable with automated outputs (Likert ≥ 3.8).

Long-Term Success Indicators (Phase 2–3)
Retention: 70%+ of therapists still active after 6 months.
Expansion: Therapists add more clients to In-Between Flows over time (indicative of trust and value).
NPS: ≥ 50 after 6 months.
Revenue: Willingness to pay $50–150/month (validated via pricing experiments in Phase 3).

12. Constraints & Principles
Core Product Principles
Therapist-First Design
All flows optimize for therapist experience, control, and clinical responsibility.
Client-facing features are extensions of the therapist, not independent agents.
Human-in-the-Loop
No AI-generated clinical content becomes "real" without therapist approval where it affects the record or client.
Therapist retains full clinical authority and accountability.
Minimal Surface Area for MVP
Prioritize one narrow but deep path (single therapist persona, limited In-Between template, one main documentation mode) over broad feature coverage.
Depth > breadth for MVP.
Safety Over Cleverness
In ambiguous situations, system chooses safest, most conservative behavior.
Crisis scenarios: default to safe redirection (contact therapist/hotline) rather than engaging.
Privacy by Design
Data model and UX designed around confidentiality from day one.
Clear separation: therapist identity, client identity, clinical content.
Audit trails for all sensitive operations.
Iterative Learning
System learns therapist style incrementally, transparently.
Therapist can always inspect, adjust, or reset the "twin."

Technical Constraints
No real-time video/audio processing in MVP (post-session voice recap only).
Single-tenant data model for MVP (no multi-clinician shared access).
English + Hebrew language support initially; other languages in later phases.
Languages (MVP): Hebrew and English must both be supported in MVP for therapist UI, summaries, and In-Between messaging. Additional languages are Phase 2+.
Web-first: Desktop and mobile-responsive web; native mobile apps in Phase 3+.

Regulatory & Ethical Constraints
Not a medical device: System does not diagnose, prescribe, or replace clinical judgment.
Therapist liability: Therapists remain legally and ethically responsible for all clinical decisions and client interactions.
Informed consent: Therapists must inform clients that AI is used for documentation and between-session support, and obtain appropriate consent.
Data sovereignty: Comply with local data protection laws (GDPR, HIPAA principles, regional equivalents).

13. Open Questions & Risk Mitigation
Open Questions (To Resolve Before Build)
Q1: Exact In-Between Flow Template Definition
Is MVP template strictly "CBT task  for anxiety/exposure cases"?
Do we allow small variations (e.g., exposure vs. cognitive task , mood tracking)?
Decision by: End of Week 1 (pre-development).
Q2: Client-Side Interface for In-Between
Web-only? SMS via Twilio? WhatsApp via API?
Trade-offs: Web = more control, SMS/WhatsApp = lower friction for clients.
Decision by: Week 2 (architecture phase).
Q3: Therapist Twin Transparency Level
Do we expose full "profile text" or simplified view with sliders/controls?
How much detail is helpful vs. overwhelming for non-technical therapists?
Decision by: Week 4 (after initial UX prototypes).
Q4: Legal/Ethical Boundaries by Geography
Are there jurisdiction-specific restrictions on AI-assisted clinical tools or between-session communication?
Do we need legal review before pilot (especially for client-facing In-Between)?
Decision by: Week 0 (before build starts).
Q5: Pricing Model Validation
Per-therapist SaaS ($50–150/month)?
Per-client pricing?
Freemium model?
Decision by: End of Phase 1 (before Phase 2 begins).

Key Risks & Mitigation Strategies
Risk 1: Therapists Don't Trust AI-Generated Summaries
Likelihood: Medium
Impact: High (undermines core value prop)
Mitigation:
Show side-by-side: original transcript + AI summary (transparency).
Allow easy editing and regeneration.
Start with conservative summaries (less interpretation, more factual recap).
Pilot with early adopters who are AI-curious.
Success Indicator: 90%+ summaries approved with minimal edits within first 2 weeks.

Risk 2: In-Between Flow Feels Too Generic or "Robotic"
Likelihood: Medium
Impact: Medium (reduces differentiation, hurts adoption)
Mitigation:
Invest heavily in Therapist Twin quality (style learning from summaries).
Provide tone/style controls upfront.
Pilot with therapists who have distinct, recognizable styles.
Gather qualitative feedback: "Does this sound like you?"
Success Indicator: 70%+ of therapists agree "messages feel like my style" (Likert ≥ 4/5).

Risk 3: Crisis Mismanagement in In-Between Flow
Likelihood: Low (with safeguards)
Impact: Critical (ethical, legal, reputational)
Mitigation:
Keyword-based crisis detection with immediate safe redirection.
Hard constraints: no crisis counseling, no diagnostic discussions.
Manual review of 100% of In-Between interactions during alpha.
Clear therapist and client education: "This is not a crisis support tool."
Success Indicator: Zero harmful interactions in alpha; 100% appropriate crisis response.

Risk 4: Low Adoption of In-Between Flow (Therapists Enable But Don't Use)
Likelihood: Medium
Impact: High (undermines core differentiation)
Mitigation:
Make activation extremely easy (< 2 minutes to configure).
Provide clear value preview: "See what your client will experience."
Start with highly motivated therapists (CBT-focused, task -heavy practices).
Measure weekly: if adoption < 20% of clients per therapist, revisit design.
Success Indicator: 40%+ of pilot therapists' clients have at least one active In-Between Flow by Week 6.

Risk 5: Scalability/Performance Issues (AI Latency, Cost)
Likelihood: Medium
Impact: Medium (hurts UX, increases burn rate)
Mitigation:
Use async job queues for heavy AI tasks (summary, insight generation).
Set API timeout budgets (ASR < 30s, summary < 60s).
Monitor LLM costs closely; optimize prompts for token efficiency.
Have fallback: if AI fails, allow manual summary entry.
Success Indicator: 95%+ of summaries generated within latency targets; LLM costs < $5/therapist/month in alpha.

Risk 6: Regulatory/Legal Barriers
Likelihood: Low–Medium (varies by geography)
Impact: High (could block launch or require significant pivots)
Mitigation:
Engage legal counsel with healthcare/digital health experience early (Week 0).
Design with HIPAA/GDPR principles even if not strictly required.
Position as "therapist productivity tool" (not medical device) to reduce regulatory burden.
Obtain informed consent language reviewed by legal.
Success Indicator: Legal clearance obtained before pilot launch; zero regulatory blockers identified.

Appendices
Appendix A: Glossary
Therapist Twin: Internal AI representation of a therapist's clinical style, learned from approved summaries and configurable by the therapist.
Insight Summary: AI-generated synthesis of a client's treatment trajectory based on all approved session summaries.
In-Between Flow: Structured, templated interaction sequence between client and VirtualTherapist (via therapist's "twin") during the time between sessions.
Voice Recap: Post-session audio recording by therapist, transcribed and turned into structured summary via AI.
Golden Path: The single, core user journey (therapist adoption through first month) that MVP is optimized for.
ASR: Automatic Speech Recognition (speech-to-text).
OCR: Optical Character Recognition (handwriting-to-text).

Appendix B: References & Research
American Psychological Association. (2023). Clinical Documentation Best Practices.
Gaffney, H., et al. (2024). "task  Compliance and Therapeutic Outcomes in CBT: A Meta-Analysis." Journal of Consulting and Clinical Psychology.
National Institute of Mental Health. (2025). Between-Session Support in Psychotherapy: Emerging Evidence.
AI Safety Guidelines for Healthcare Applications (2025). Partnership on AI.

Appendix C: Contact & Approval
Document Owner: Product Leadership
Technical Lead: [TBD]
Clinical Advisor: [TBD – ideally licensed therapist consultant]
Approvals Required:
 Product Leadership
 Technical Lead
 Clinical Advisor
 Legal Counsel (for client-facing features)
Next Steps:
Review and approve this PRD.
Conduct final desirability validation (5–10 therapist interviews).
Finalize tech stack and architecture decisions (Week 1).
Kick off development (Week 2).

End of Document



