# 🧠 TherapyCompanion.AI

**AI-powered virtual therapist assistant that continues human therapy work between sessions while assisting therapists with daily documentation.**

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109+-green.svg)](https://fastapi.tiangolo.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## 🎯 What is TherapyCompanion.AI?

TherapyCompanion.AI is an advanced AI agent that serves as a **personal virtual therapist assistant**. It has two main roles:

1. **Assist therapists with daily workflow** - Documentation, session summaries, administrative tasks
2. **Continue therapeutic activity** with patients between sessions - Support, follow-up exercises, check-ins

### 🌟 Key Features

- **✨ Fully Personalized AI Agent** - Each therapist gets an AI that speaks exactly like them
- **🔒 Security & Privacy First** - AES-256 encryption, GDPR compliant, Israel/EU servers only
- **✅ Therapist Approval Required** - AI never acts autonomously with patients
- **🎨 Dead Simple Interface** - Just 3 buttons: Write Summary, Send to Patient, New Recording
- **🇮🇱 Hebrew Language Support** - Native RTL support with Hebrew as the primary language
- **📝 Session Summaries** - Auto-generate from audio or text in therapist's style
- **💬 Patient Messages** - AI drafts, therapist approves, maintains therapeutic relationship
- **📊 Full Audit Trail** - Complete logging for compliance and security

---

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL 14+
- Redis 6+
- Anthropic API key (or OpenAI)

### Backend Installation

```bash
# Clone the repository
git clone <repository-url>
cd VirtualTherapist

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Setup environment
cp .env.example .env
# Edit .env with your configuration

# Setup database
createdb virtual_therapist
alembic upgrade head

# Run the application
python -m app.main
```

The API will be available at: **http://localhost:8000**

> **Dependency note — bcrypt/passlib:**
> `passlib==1.7.4` (last official release) reads `bcrypt.__about__.__version__` internally.
> This attribute was removed in `bcrypt>=4.1`. The project pins `bcrypt==4.0.1` to keep the
> two libraries compatible. Do **not** upgrade bcrypt past `4.0.1` without replacing passlib
> (e.g. with `bcrypt` directly or `argon2-cffi`). A startup shim in `app/main.py` also
> injects a stub `__about__` module as a belt-and-suspenders fallback.

### Frontend Installation

```bash
# In a new terminal
cd frontend

# Install dependencies
npm install

# Setup environment
cp .env.example .env

# Run development server
npm run dev
```

The web interface will be available at: **http://localhost:3000**

📖 **Full setup guide:** [docs/SETUP.md](docs/SETUP.md)
📖 **Frontend guide:** [frontend/README.md](frontend/README.md)

---

## 📋 How It Works

### Phase 1: Therapist Learning (Onboarding)

The AI learns your personal style through a 5-step onboarding:

1. **Therapeutic Approach** - CBT, psychodynamic, etc.
2. **Writing Style** - Tone, length, terminology
3. **Summary Preferences** - Sections, format, templates
4. **Communication Style** - Follow-up frequency, preferred exercises
5. **Learning Examples** - Your actual summaries and messages

### Phase 2: Fully Personalized Agent

Once onboarding is complete, you get an AI that:

```
✅ Speaks exactly like you
✅ Uses your preferred terminology
✅ Matches your therapeutic approach
✅ Signs messages with your name
✅ Maintains your style consistently
```

**Example Message:**

```
NOT: "Good morning, I am artificial intelligence..."
YES: "Hi Sarah, this is Dr. Cohen. How was your week?"
```

---

## 🔐 Security & Privacy (CRITICAL!)

### Ironclad Rules

```
⚠️ NEVER store data outside encrypted Israel/EU servers
⚠️ ALL patient data encrypted end-to-end (AES-256)
⚠️ THERAPIST MUST approve every message to patients
⚠️ FULL audit log of every action
⚠️ GDPR compliant with full deletion capability
⚠️ NO data sharing with 3rd parties
```

### Compliance

- ✅ **GDPR Compliant** - Right to access, deletion, portability
- ✅ **End-to-End Encryption** - AES-256 for all sensitive data
- ✅ **Complete Audit Trail** - Every action logged
- ✅ **Data Residency** - Israel/EU servers only
- ✅ **No Third-Party Sharing** - Your data stays yours

---

## 🎭 Example Workflows

### Workflow 1: Session Summary

```
1. Therapist ends session
2. Clicks "📝 Write Summary"
3. Records 2 minutes OR types notes
4. AI generates structured summary in therapist's style:
   - Topics discussed
   - Interventions used
   - Patient progress
   - Homework assigned
   - Next session plan
5. Therapist edits (30 seconds)
6. Clicks "💾 Save"
7. ✓ Done!
```

**Time saved:** ~10-15 minutes per session

### Workflow 2: Patient Follow-up

```
1. AI detects: "Patient hasn't completed homework"
2. AI creates draft message in therapist's voice:
   "Hi Yossi, this is Dr. Cohen. How did the breathing
   exercise go? Anything new come up?"
3. Therapist sees notification
4. Reviews message → Can edit or approve
5. Therapist approves
6. Message sent to patient
7. ✓ Therapeutic continuity maintained
```

**Result:** Patients stay engaged between sessions

---

## 🔧 Commands

The AI supports special commands for common tasks:

- `/start` - Begin onboarding and get to know therapist
- `/summary` - Create session summary from recording or text
- `/client [name]` - Open patient profile
- `/message [name]` - Create message for patient
- `/templates` - Manage personal templates
- `/status` - View all patients status
- `/privacy` - Privacy & security settings

---

## 📐 Architecture

### Tech Stack

**Backend:**
- **Framework:** FastAPI (Python 3.11+)
- **Database:** PostgreSQL with SQLAlchemy ORM
- **Cache:** Redis
- **AI:** Anthropic Claude / OpenAI GPT
- **Encryption:** AES-256 via Cryptography library
- **Auth:** JWT with BCrypt
- **Audio:** OpenAI Whisper (transcription)

**Frontend:**
- **Framework:** React 18 with TypeScript
- **Build Tool:** Vite
- **Styling:** Tailwind CSS
- **State:** Zustand
- **Router:** React Router v6
- **HTTP Client:** Axios
- **Icons:** Heroicons

### Project Structure

```
VirtualTherapist/
├── app/                  # Backend (Python/FastAPI)
│   ├── api/              # FastAPI routes
│   │   └── routes/       # Auth, agent, messages
│   ├── core/             # Core config & AI agent
│   ├── models/           # SQLAlchemy models
│   ├── services/         # Business logic
│   ├── security/         # Auth & encryption
│   └── main.py           # FastAPI application
├── frontend/             # Frontend (React/TypeScript)
│   ├── src/
│   │   ├── components/   # React components
│   │   ├── pages/        # Page components
│   │   ├── lib/          # API client
│   │   └── store/        # State management
│   ├── public/           # Static assets
│   └── package.json      # Frontend dependencies
├── docs/                 # Comprehensive documentation
│   ├── ARCHITECTURE.md   # System architecture
│   ├── API_GUIDE.md      # API documentation
│   ├── SETUP.md          # Setup instructions
│   └── FRONTEND_GUIDE.md # Frontend guide
├── tests/                # Unit tests
├── examples/             # Usage examples
├── alembic/              # Database migrations
└── requirements.txt      # Backend dependencies
```

📖 **Full architecture:** [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)

---

## 📚 Documentation

- **[Setup Guide](docs/SETUP.md)** - Installation and configuration
- **[API Guide](docs/API_GUIDE.md)** - Complete API documentation
- **[Architecture](docs/ARCHITECTURE.md)** - System design and components
- **[Frontend Guide](docs/FRONTEND_GUIDE.md)** - Web interface guide
- **[Frontend README](frontend/README.md)** - Frontend setup
- **[Examples](examples/example_usage.py)** - Usage examples

---

## 🧪 Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app tests/

# Run specific test file
pytest tests/test_agent.py

# Run examples
python examples/example_usage.py
```

---

## 🌐 API Endpoints

### Authentication
- `POST /api/v1/auth/register` - Register new therapist
- `POST /api/v1/auth/login` - Login and get token

### AI Agent
- `POST /api/v1/agent/chat` - Chat with personalized agent
- `POST /api/v1/agent/command` - Execute command (/start, /summary, etc.)
- `POST /api/v1/agent/onboarding/start` - Start onboarding
- `POST /api/v1/agent/onboarding/complete-step` - Complete onboarding step

### Messages
- `POST /api/v1/messages/create` - Create draft message
- `POST /api/v1/messages/approve` - Approve message (required!)
- `POST /api/v1/messages/reject` - Reject message
- `POST /api/v1/messages/edit` - Edit draft message
- `POST /api/v1/messages/send/{id}` - Send approved message
- `GET /api/v1/messages/pending` - Get pending approvals
- `GET /api/v1/messages/patient/{id}` - Get patient message history

📖 **Full API documentation:** [docs/API_GUIDE.md](docs/API_GUIDE.md)

---

## ⚖️ Ethical Boundaries

### What the AI Does

✅ Assists with documentation
✅ Drafts messages for therapist approval
✅ Maintains therapeutic continuity
✅ Speaks in therapist's voice (with permission)

### What the AI NEVER Does

❌ Acts autonomously with patients
❌ Provides diagnoses
❌ Recommends medications
❌ Handles crisis situations
❌ Replaces human therapist

**The AI is an assistant, not a replacement.**

---

## 🎯 Measurable Goals

- **Therapist:** Save 1.5 hours weekly on documentation
- **Patient:** Maintain momentum between sessions
- **Business:** 30% Freemium → Paid conversion
- **Quality:** NPS ≥ 8/10 from therapists

---

## 🤝 Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

---

## 📝 License

This project is licensed under the MIT License - see the LICENSE file for details.

---

## 🆘 Support

For issues, questions, or feature requests:

- **Issues:** Open a GitHub issue
- **Documentation:** Check `/docs` directory
- **Examples:** See `/examples` directory

---

## 🔮 Roadmap

### Version 1.0 (Current)
- ✅ Core AI agent with personalization
- ✅ Session summary generation
- ✅ Message approval workflow
- ✅ Security & encryption
- ✅ Hebrew language support

### Version 1.1 (Planned)
- 🔄 Frontend web interface
- 🔄 Mobile app support
- 🔄 Integration with WhatsApp/SMS
- 🔄 Analytics dashboard

### Version 2.0 (Future)
- 🔮 Multi-language support
- 🔮 Video session analysis
- 🔮 EMR system integration
- 🔮 Group therapy support

---

## 🙏 Acknowledgments

- Built with [FastAPI](https://fastapi.tiangolo.com/)
- AI powered by [Anthropic Claude](https://www.anthropic.com/)
- Transcription by [OpenAI Whisper](https://openai.com/research/whisper)

---

## ⚠️ Disclaimer

This system is designed to **assist** licensed therapists, not replace them. All therapeutic decisions and patient communications must be reviewed and approved by qualified mental health professionals. This system should not be used for crisis intervention or emergency situations.

---

<div align="center">

**TherapyCompanion.AI** - Empowering therapists with AI

Made with ❤️ for mental health professionals

</div>
