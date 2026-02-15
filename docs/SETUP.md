# TherapyCompanion.AI - Setup Guide

## 🚀 Quick Start

### Prerequisites

- Python 3.11 or higher
- PostgreSQL 14 or higher
- Redis 6 or higher
- Anthropic API key or OpenAI API key

### 1. Clone and Install

```bash
# Clone the repository
git clone <repository-url>
cd VirtualTherapist

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Database Setup

```bash
# Create PostgreSQL database
createdb virtual_therapist

# Or using psql
psql -U postgres
CREATE DATABASE virtual_therapist;
\q
```

### 3. Environment Configuration

```bash
# Copy example environment file
cp .env.example .env

# Edit .env with your settings
nano .env
```

**Required environment variables:**

```bash
# Security (CHANGE THESE!)
SECRET_KEY=your-very-secret-key-here-change-me
ENCRYPTION_KEY=your-encryption-key-here-change-me

# Database
DATABASE_URL=postgresql://username:password@localhost:5432/virtual_therapist
REDIS_URL=redis://localhost:6379/0

# AI Provider (choose one)
ANTHROPIC_API_KEY=your-anthropic-api-key
# OR
OPENAI_API_KEY=your-openai-api-key

AI_PROVIDER=anthropic  # or openai
```

### 4. Database Migration

```bash
# Create tables
alembic upgrade head
```

### 5. Run the Application

```bash
# Development mode
python -m app.main

# Or using uvicorn directly
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at: `http://localhost:8000`

## 📋 Detailed Setup

### Python Environment

```bash
# Ensure Python 3.11+
python --version

# Create isolated environment
python -m venv venv

# Activate environment
# Linux/Mac:
source venv/bin/activate
# Windows:
venv\Scripts\activate

# Upgrade pip
pip install --upgrade pip

# Install requirements
pip install -r requirements.txt
```

### PostgreSQL Setup

#### Linux (Ubuntu/Debian)
```bash
sudo apt update
sudo apt install postgresql postgresql-contrib
sudo systemctl start postgresql
sudo systemctl enable postgresql

# Create database user
sudo -u postgres createuser --interactive
# Name: therapy_user
# Superuser: No
# Create databases: Yes
# Create roles: No

# Set password
sudo -u postgres psql
ALTER USER therapy_user WITH PASSWORD 'your_secure_password';
\q

# Create database
createdb -U therapy_user virtual_therapist
```

#### macOS
```bash
brew install postgresql
brew services start postgresql

createdb virtual_therapist
```

#### Windows
Download and install PostgreSQL from https://www.postgresql.org/download/windows/

### Redis Setup

#### Linux (Ubuntu/Debian)
```bash
sudo apt install redis-server
sudo systemctl start redis
sudo systemctl enable redis
```

#### macOS
```bash
brew install redis
brew services start redis
```

#### Windows
Download Redis from https://github.com/microsoftarchive/redis/releases

### Database Migrations

```bash
# Initialize Alembic (only if not already done)
alembic init alembic

# Create migration
alembic revision --autogenerate -m "Initial migration"

# Apply migrations
alembic upgrade head

# Rollback (if needed)
alembic downgrade -1
```

## 🔑 API Keys

### Anthropic API Key (Recommended)

1. Sign up at https://console.anthropic.com/
2. Navigate to API Keys
3. Create new key
4. Add to `.env`: `ANTHROPIC_API_KEY=sk-ant-...`

### OpenAI API Key (Alternative)

1. Sign up at https://platform.openai.com/
2. Navigate to API Keys
3. Create new key
4. Add to `.env`: `OPENAI_API_KEY=sk-...`

## 🧪 Testing the Setup

### 1. Health Check

```bash
curl http://localhost:8000/health
```

Expected response:
```json
{
  "status": "healthy",
  "app": "TherapyCompanion.AI",
  "version": "1.0.0"
}
```

### 2. Register Test Therapist

```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "testpass123",
    "full_name": "Test Therapist",
    "phone": "+972-50-1234567"
  }'
```

### 3. Login

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=test@example.com&password=testpass123"
```

### 4. Test AI Agent

```bash
# Use the token from login
export TOKEN="your-token-here"

curl -X POST http://localhost:8000/api/v1/agent/command \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "command": "start",
    "args": ""
  }'
```

## 🔒 Security Configuration

### Generate Secure Keys

```bash
# Generate SECRET_KEY
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Generate ENCRYPTION_KEY
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Add these to your `.env` file.

### File Permissions

```bash
# Secure .env file
chmod 600 .env

# Secure logs directory
mkdir -p logs
chmod 700 logs
```

## 📁 Directory Structure

```
VirtualTherapist/
├── app/
│   ├── api/              # API routes
│   ├── core/             # Core config & agent
│   ├── models/           # Database models
│   ├── services/         # Business logic
│   ├── security/         # Auth & encryption
│   └── main.py           # FastAPI app
├── docs/                 # Documentation
├── tests/                # Unit tests
├── alembic/              # Database migrations
├── logs/                 # Application logs
├── requirements.txt      # Dependencies
├── .env                  # Environment config
└── README.md             # Project overview
```

## 🐳 Docker Setup (Optional)

```bash
# Build image
docker build -t therapy-companion .

# Run with docker-compose
docker-compose up -d
```

## 🔧 Troubleshooting

### Database Connection Error

```
Error: could not connect to server
```

**Solution:**
- Verify PostgreSQL is running: `sudo systemctl status postgresql`
- Check DATABASE_URL in `.env`
- Verify user credentials

### Redis Connection Error

```
Error: Error connecting to Redis
```

**Solution:**
- Verify Redis is running: `redis-cli ping`
- Should return: `PONG`
- Check REDIS_URL in `.env`

### Import Errors

```
ModuleNotFoundError: No module named 'app'
```

**Solution:**
- Ensure virtual environment is activated
- Run from project root directory
- Reinstall dependencies: `pip install -r requirements.txt`

### AI API Errors

```
Error: Invalid API key
```

**Solution:**
- Verify API key is correct in `.env`
- Check API provider setting: `AI_PROVIDER=anthropic` or `openai`
- Verify API key has not expired

## 🚀 Production Deployment

### Using Gunicorn

```bash
pip install gunicorn

gunicorn app.main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --timeout 120
```

### Environment Variables for Production

```bash
ENVIRONMENT=production
DEBUG=False
```

### HTTPS Configuration

Use a reverse proxy like Nginx:

```nginx
server {
    listen 443 ssl;
    server_name therapy.example.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## 📊 Monitoring

### Logs

```bash
# View logs
tail -f logs/therapy_companion.log

# Search logs
grep "ERROR" logs/therapy_companion.log
```

### Database

```bash
# Connect to database
psql -U therapy_user -d virtual_therapist

# Check tables
\dt

# View recent audit logs
SELECT * FROM audit_logs ORDER BY timestamp DESC LIMIT 10;
```

## 🆘 Support

For issues or questions:
- Check documentation in `/docs`
- Review error logs
- Open an issue on GitHub
