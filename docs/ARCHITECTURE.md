# TherapyCompanion.AI - System Architecture

## 🏗️ Architecture Overview

TherapyCompanion.AI is a secure, personalized AI assistant for therapists that helps with:
1. Session documentation and summaries
2. Patient follow-up between sessions
3. Message drafting in therapist's personal style

## 🎯 Core Principles

### 1. **Security & Privacy First**
- All patient data encrypted at rest (AES-256)
- End-to-end encryption for communications
- Full audit trail for GDPR compliance
- Data stored only in Israel/EU servers
- No data sharing with third parties

### 2. **Personalization**
Each therapist gets a completely personalized AI agent that:
- Learns their writing style
- Uses their preferred terminology
- Matches their therapeutic approach
- Speaks in their voice (not as "AI")

### 3. **Human-in-the-Loop**
- **Every patient message requires therapist approval**
- AI drafts, therapist reviews and approves
- No autonomous sending to patients
- Full therapist control at all times

## 📐 System Components

### 1. **Core AI Agent** (`app/core/agent.py`)
The heart of the system - personalized AI assistant

**Responsibilities:**
- Generate responses in therapist's style
- Handle commands (/start, /summary, etc.)
- Create session summaries
- Draft patient messages
- Maintain therapist's personality

**Key Features:**
- Dynamic system prompt based on therapist profile
- Context-aware responses
- Hebrew language primary support
- Command routing

### 2. **Data Models** (`app/models/`)

#### Therapist Models
- `Therapist`: Account and authentication
- `TherapistProfile`: Personalization data (approach, style, examples)

#### Patient Models
- `Patient`: Encrypted patient information
- `PatientStatus`: Treatment status tracking

#### Session Models
- `Session`: Therapy session records
- `SessionSummary`: AI-generated summaries in therapist's style

#### Message Models
- `Message`: Patient messages with approval workflow
- `MessageStatus`: Draft → Pending → Approved → Sent

#### Audit Models
- `AuditLog`: Complete action trail for compliance

### 3. **Services Layer** (`app/services/`)

#### TherapistService
- Account creation and management
- Profile customization
- Onboarding workflow (5 steps)
- Agent provisioning

#### SessionService
- Session recording
- Audio transcription (Whisper)
- Summary generation (AI-powered)
- Therapist review and approval

#### MessageService
- Draft creation using AI
- Approval workflow (critical!)
- Edit capabilities
- Sending (only after approval)

#### AuditService
- Action logging
- GDPR compliance
- Access trails
- Security monitoring

#### AudioService
- Audio file validation
- Transcription (Whisper API or local)
- Format support (mp3, wav, m4a, ogg)

### 4. **Security Layer** (`app/security/`)

#### Encryption
- AES-256 for data at rest
- Fernet symmetric encryption
- PBKDF2 key derivation
- All patient data encrypted

#### Authentication
- JWT token-based auth
- BCrypt password hashing
- Secure token generation
- Access control

### 5. **API Layer** (`app/api/`)

#### Routes:
- `/api/v1/auth` - Registration and login
- `/api/v1/agent` - AI agent interaction
- `/api/v1/messages` - Message management
- `/api/v1/sessions` - Session summaries
- `/api/v1/patients` - Patient management

## 🔄 Key Workflows

### Workflow 1: Therapist Onboarding

```
1. Therapist registers → Account created
2. Start onboarding → /start command
3. Step 1: Therapeutic approach (CBT, psychodynamic, etc.)
4. Step 2: Writing style (tone, length, terminology)
5. Step 3: Summary preferences (sections, format)
6. Step 4: Communication preferences (frequency, exercises)
7. Step 5: Examples for AI learning (summaries, messages)
8. Onboarding complete → Personalized agent ready
```

### Workflow 2: Session Summary Generation

```
1. Therapist ends session
2. Records 2-minute audio or types notes
3. AI transcribes (if audio) → Whisper
4. AI generates structured summary in therapist's style
5. Therapist reviews → Edits if needed
6. Therapist approves → Saved to database
7. Backup created automatically
```

### Workflow 3: Patient Message Flow (CRITICAL!)

```
1. AI suggests message (based on patient status)
2. Therapist reviews suggestion
3. AI creates draft message in therapist's voice
4. Status: DRAFT
5. Therapist reviews → Can edit or reject
6. Therapist approves → Status: APPROVED
7. Message sent to patient → Status: SENT
8. Full audit trail logged

❌ Message NEVER sent without therapist approval!
```

## 🔐 Security Architecture

### Data Encryption
```
Patient Data → Encrypt → Database
             ↓
        AES-256
             ↓
     Encrypted at Rest
```

### Authentication Flow
```
User Login → Credentials
           ↓
     Verify Password (BCrypt)
           ↓
     Generate JWT Token
           ↓
     Return Token → User
           ↓
     Subsequent Requests → Bearer Token
           ↓
     Validate & Extract User
```

### Audit Trail
```
Every Action → Log to AuditLog
            ↓
    {who, what, when, where, why}
            ↓
    GDPR Compliant Storage
            ↓
    Available for Compliance Reports
```

## 🌐 Technology Stack

### Backend
- **Framework:** FastAPI (Python 3.11+)
- **Database:** PostgreSQL with SQLAlchemy ORM
- **Cache:** Redis (for sessions)
- **AI:** Anthropic Claude or OpenAI GPT

### Security
- **Encryption:** Cryptography library (AES-256)
- **Auth:** JWT with python-jose
- **Passwords:** Passlib with BCrypt

### Audio Processing
- **Transcription:** OpenAI Whisper
- **Formats:** mp3, wav, m4a, ogg

### Language
- **Primary:** Hebrew (he)
- **Tokenizer:** hebrew-tokenizer
- **RTL Support:** Enabled

## 📊 Database Schema

```sql
therapists
  ├── id, email, password, name
  └── has_one → therapist_profile
      ├── approach, tone, style
      ├── examples (for AI learning)
      └── onboarding status

patients (encrypted!)
  ├── id, therapist_id
  ├── name_encrypted, contact_encrypted
  ├── clinical_notes_encrypted
  └── treatment status

sessions
  ├── id, therapist_id, patient_id
  ├── date, duration, audio_path
  └── has_one → session_summary
      ├── topics, interventions
      ├── progress, homework
      └── full_summary (in therapist style!)

messages (approval workflow!)
  ├── id, therapist_id, patient_id
  ├── content, status, direction
  ├── requires_approval ← ALWAYS TRUE
  ├── approved_at, sent_at
  └── audit trail

audit_logs
  ├── user_id, action, resource
  ├── timestamp, details
  └── GDPR compliance
```

## 🚀 Deployment Considerations

### Environment Requirements
- Python 3.11+
- PostgreSQL 14+
- Redis 6+
- GPU (optional, for local Whisper)

### Scaling
- Horizontal: Multiple API servers behind load balancer
- Database: Read replicas for summaries
- Redis: Cluster mode for sessions
- AI: API-based (Anthropic/OpenAI) for easy scaling

### Monitoring
- Loguru for structured logging
- Audit logs for compliance
- Health check endpoint
- Error tracking (integrate Sentry)

## 🔒 Compliance & Ethics

### GDPR Requirements
✅ Data encryption at rest
✅ Right to access (audit logs)
✅ Right to deletion (cascading deletes)
✅ Data portability
✅ Consent tracking
✅ Audit trail

### Ethical Boundaries
❌ AI never acts autonomously with patients
❌ No medical diagnoses
❌ No medication recommendations
❌ No crisis intervention
✅ Always identifies as [Therapist Name]
✅ Human therapist maintains full control
✅ Transparent about AI assistance

## 📈 Future Enhancements

1. **Multi-language Support** (English, Arabic)
2. **Video Session Analysis** (body language, sentiment)
3. **Integration with EMR systems**
4. **Mobile Apps** (iOS, Android)
5. **Voice Interface** (conversational AI)
6. **Analytics Dashboard** (patient progress insights)
7. **Group Therapy Support**
8. **Insurance Billing Integration**
