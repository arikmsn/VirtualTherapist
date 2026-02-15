# TherapyCompanion.AI - API Guide

## 📚 API Documentation

Base URL: `http://localhost:8000/api/v1`

## 🔐 Authentication

All endpoints (except registration and login) require JWT authentication.

### Register New Therapist

```http
POST /auth/register
Content-Type: application/json

{
  "email": "therapist@example.com",
  "password": "secure_password_123",
  "full_name": "Dr. Sarah Cohen",
  "phone": "+972-50-1234567"
}

Response:
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

### Login

```http
POST /auth/login
Content-Type: application/x-www-form-urlencoded

username=therapist@example.com
password=secure_password_123

Response:
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

### Using the Token

Include the token in all subsequent requests:

```http
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

## 🤖 AI Agent Endpoints

### Chat with Agent

```http
POST /agent/chat
Authorization: Bearer <token>
Content-Type: application/json

{
  "message": "בואי ניצור סיכום מהפגישה עם יוסי היום",
  "context": {
    "patient_name": "יוסי",
    "session_date": "2024-02-15"
  }
}

Response:
{
  "response": "בטח! בואי ניצור סיכום מהפגישה עם יוסי. מה הנושאים העיקריים שדיברתם עליהם?",
  "agent_model": "anthropic"
}
```

### Execute Command

```http
POST /agent/command
Authorization: Bearer <token>
Content-Type: application/json

{
  "command": "start",
  "args": ""
}

Response:
{
  "response": "שלום! אני TherapyCompanion.AI - הסוכן האישי שלך...",
  "agent_model": "anthropic"
}
```

### Start Onboarding

```http
POST /agent/onboarding/start
Authorization: Bearer <token>

Response:
{
  "message": "שלום! אני TherapyCompanion.AI...",
  "onboarding_step": 1
}
```

### Complete Onboarding Step

```http
POST /agent/onboarding/complete-step
Authorization: Bearer <token>
Content-Type: application/json

{
  "step": 1,
  "data": {
    "approach": "CBT",
    "description": "אני עובדת בעיקר עם CBT, עם דגש על חשיבה אוטומטית וחשיפה הדרגתית"
  }
}

Response:
{
  "message": "Step completed successfully",
  "current_step": 1,
  "onboarding_completed": false
}
```

## 💬 Message Endpoints

### Create Draft Message for Patient

```http
POST /messages/create
Authorization: Bearer <token>
Content-Type: application/json

{
  "patient_id": 123,
  "message_type": "follow_up",
  "context": {
    "last_session": "2024-02-10",
    "homework": "breathing exercise"
  }
}

Response:
{
  "id": 456,
  "patient_id": 123,
  "content": "היי יוסי, זה שרה. רציתי לשמוע איך הלך תרגיל הנשימה מהפגישה שלנו?",
  "status": "draft",
  "message_type": "follow_up",
  "created_at": "2024-02-15T10:30:00",
  "requires_approval": true
}
```

### Get Pending Messages (Awaiting Approval)

```http
GET /messages/pending
Authorization: Bearer <token>

Response:
[
  {
    "id": 456,
    "patient_id": 123,
    "content": "היי יוסי, זה שרה...",
    "status": "draft",
    "message_type": "follow_up",
    "created_at": "2024-02-15T10:30:00",
    "requires_approval": true
  },
  ...
]
```

### Edit Draft Message

```http
POST /messages/edit
Authorization: Bearer <token>
Content-Type: application/json

{
  "message_id": 456,
  "new_content": "היי יוסי, זה ד״ר שרה. רציתי לשמוע איך הלך תרגיל הנשימה?"
}

Response:
{
  "message": "Message edited successfully",
  "message_id": 456
}
```

### Approve Message

**CRITICAL:** Only approved messages can be sent to patients!

```http
POST /messages/approve
Authorization: Bearer <token>
Content-Type: application/json

{
  "message_id": 456
}

Response:
{
  "message": "Message approved successfully",
  "message_id": 456,
  "status": "approved"
}
```

### Reject Message

```http
POST /messages/reject
Authorization: Bearer <token>
Content-Type: application/json

{
  "message_id": 456,
  "reason": "הטון לא מתאים למטופל הזה"
}

Response:
{
  "message": "Message rejected",
  "message_id": 456,
  "status": "rejected"
}
```

### Send Approved Message

```http
POST /messages/send/456
Authorization: Bearer <token>

Response:
{
  "message": "Message sent successfully",
  "message_id": 456,
  "sent_at": "2024-02-15T10:35:00"
}
```

### Get Patient Message History

```http
GET /messages/patient/123
Authorization: Bearer <token>

Response:
[
  {
    "id": 456,
    "patient_id": 123,
    "content": "היי יוסי, זה שרה...",
    "status": "sent",
    "message_type": "follow_up",
    "created_at": "2024-02-15T10:30:00",
    "requires_approval": true
  },
  ...
]
```

## 🎯 Common Message Types

- `follow_up` - Follow up on homework/exercises
- `exercise_reminder` - Remind patient about exercises
- `check_in` - General check-in
- `session_reminder` - Reminder for next session
- `response` - Response to patient message

## 🔒 Security Notes

### Rate Limiting
- 100 requests per minute per user
- 1000 requests per hour per user

### Data Privacy
- All patient data is encrypted
- Messages require explicit approval
- Full audit trail maintained
- GDPR compliant

### Error Responses

```json
{
  "detail": "Error message here"
}
```

Common HTTP Status Codes:
- `200` - Success
- `201` - Created
- `400` - Bad Request
- `401` - Unauthorized
- `403` - Forbidden
- `404` - Not Found
- `500` - Internal Server Error

## 📝 Best Practices

1. **Always approve messages** before sending to patients
2. **Review AI-generated content** - don't auto-approve
3. **Use meaningful context** when creating messages
4. **Complete onboarding** for best AI personalization
5. **Provide examples** of your writing style during onboarding
6. **Keep tokens secure** - rotate regularly
7. **Log out inactive sessions**

## 🧪 Testing

### Health Check

```http
GET /health

Response:
{
  "status": "healthy",
  "app": "TherapyCompanion.AI",
  "version": "1.0.0"
}
```

### Interactive API Documentation

When `DEBUG=True`:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
