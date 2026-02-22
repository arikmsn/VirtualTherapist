# TherapyCompanion.AI - Frontend Guide

Complete guide to the web interface.

## 🎯 Overview

The frontend is a **dead simple, beautiful interface** designed for therapists who aren't technical. It follows the core principle: **Just 3 buttons**.

## 🏠 The 3-Button Dashboard

The main interface has exactly 3 buttons as specified in the original requirements:

### Button 1: 📝 Write Summary
- Click to create a session summary
- Choose: Audio recording OR text input
- AI generates structured summary in therapist's style
- Therapist reviews and edits (30 seconds)
- Save

**Time saved:** 10-15 minutes per session

### Button 2: 👤 Send to Patient
- Select patient
- Choose message type (follow-up, reminder, check-in)
- AI drafts message in therapist's voice
- **Therapist MUST approve before sending**
- Edit if needed
- Approve and send

**Critical:** No message is ever sent without explicit therapist approval!

### Button 3: 🎙️ New Recording
- Record audio (2 minutes)
- AI transcribes using Whisper
- AI generates summary
- Same as Button 1, but starts with audio

## 📱 Pages Overview

### 1. Login & Registration

**Login** (`/login`)
- Email + password
- Security notice (encrypted, GDPR, Israel servers)
- Link to registration

**Register** (`/register`)
- Full name, email, phone, password
- After registration → Onboarding

### 2. Onboarding (5 Steps)

**Step 1: Therapeutic Approach**
- Select approach (CBT, psychodynamic, etc.)
- Describe in detail

**Step 2: Writing Style**
- Tone (supportive, direct, etc.)
- Message length preference
- Common terminology

**Step 3: Summary Preferences**
- Which sections to include
- Custom template (optional)

**Step 4: Communication Preferences**
- Follow-up frequency
- Preferred exercises

**Step 5: Learning Examples**
- Paste example summary
- Paste example message
- AI learns from these!

After completion → Dashboard

### 3. Main Dashboard

**Stats Cards:**
- Pending messages count
- Today's sessions
- Active patients
- Completed summaries this week

**Recent Activity:**
- Last actions
- Pending approvals (with quick action button)
- Upcoming sessions

**Quick Actions:**
- The 3 main buttons (large, prominent)

### 4. Messages (Approval Interface)

**Critical Feature:** This is where therapists approve AI-generated messages

**For each message:**
- Patient name
- Message type
- Generated content (in therapist's voice!)
- Timestamp

**Actions:**
- ✅ **Approve & Send** - Send to patient
- ✏️ **Edit** - Modify before approving
- ❌ **Reject** - Don't send

**Warning Banner:**
> ⚠️ This message will only be sent after your explicit approval

**States:**
- Draft (just created)
- Pending Approval (waiting for therapist)
- Approved (ready to send)
- Sent (delivered to patient)

### 5. Patients

**Patient Cards:**
- Name (first letter as avatar)
- Status badge (active, paused, etc.)
- Last session date
- Next session date
- Completed sessions count
- Pending exercises (if any)

**Quick Actions per patient:**
- 📝 Create summary
- 💬 Send message

**Search:**
- Find patients by name

**Stats:**
- Total active patients
- Sessions this week
- Pending exercises
- Satisfaction score

### 6. Sessions & Summaries

**Session Cards:**
- Patient name
- Date and duration
- Session number
- Status badge (approved, pending, no summary)
- Topics discussed (as tags)

**Actions:**
- Create summary (if none exists)
- Approve summary (if pending)
- View summary (if approved)

**Filters:**
- All sessions
- Pending approval
- Approved

**Summary Preview:**
Shows approved summary with:
- Topics discussed
- Interventions used
- Patient progress
- Homework assigned
- Next session plan

## 🎨 Design Principles

### 1. Simplicity First
- Large, clear buttons
- Obvious labels
- No technical jargon
- One action per screen

### 2. Hebrew RTL
- Full right-to-left layout
- Hebrew fonts (Rubik, Assistant)
- Proper text alignment
- Date formatting in Hebrew

### 3. Visual Hierarchy
- Important actions are larger
- Colors indicate urgency:
  - Blue (calm) - primary actions
  - Green - approve/success
  - Amber - pending/warning
  - Red - reject/danger

### 4. Feedback
- Loading states (spinner)
- Success messages
- Error messages
- Smooth animations

### 5. Mobile-First
- Touch-friendly buttons (min 44x44px)
- Responsive grid
- Works on phone, tablet, desktop

## 🔐 Security & Privacy

### Authentication
- JWT tokens in localStorage
- Automatic token attachment to API calls
- 401 errors redirect to login
- Logout clears all data

### Data Encryption
- All API calls over HTTPS (production)
- Patient data encrypted on backend
- No sensitive data in frontend state

### Audit Trail
- All approvals logged
- Message edits tracked
- Therapist actions recorded

## 🎯 User Flows

### Flow 1: Create Session Summary

```
1. Therapist clicks "📝 Write Summary"
2. Modal opens
3. Choose method:
   - Audio: Click record → Stop → AI transcribes
   - Text: Type notes directly
4. AI generates summary (5-10 seconds)
5. Summary shown with editable fields
6. Therapist edits (30 seconds)
7. Click "Save"
8. ✓ Done! Summary saved
```

### Flow 2: Send Message to Patient

```
1. Therapist clicks "👤 Send to Patient"
2. Modal opens
3. Select patient from dropdown
4. Select message type (follow-up, reminder, etc.)
5. Click "Create Message (AI)"
6. AI generates draft (5 seconds)
7. Message shown in Messages page
8. Status: "Pending Approval"
9. Therapist reviews:
   - Option A: Approve immediately
   - Option B: Edit first, then approve
   - Option C: Reject
10. If approved:
11. Click "Approve & Send"
12. Message sent to patient
13. ✓ Done! Patient receives message
```

### Flow 3: First-Time Onboarding

```
1. New therapist registers
2. Redirected to /onboarding
3. Progress bar shows 5 steps
4. Step 1: Select therapeutic approach (CBT, etc.)
5. Step 2: Describe writing style
6. Step 3: Choose summary sections
7. Step 4: Set communication preferences
8. Step 5: Paste examples for AI to learn
9. Click "Finish & Start"
10. ✓ AI is now personalized!
11. Redirect to Dashboard
```

## 📊 State Management

### Auth Store (Zustand)
```typescript
{
  token: string | null,
  user: User | null,
  isAuthenticated: boolean,
  setAuth: (token, user) => void,
  logout: () => void
}
```

### Local State
- Each page manages its own data
- API calls trigger re-renders
- No complex global state

## 🔌 API Integration

### API Client (`lib/api.ts`)

```typescript
// Authentication
authAPI.login(email, password)
authAPI.register(email, password, fullName, phone)

// Agent
agentAPI.chat(message, context)
agentAPI.executeCommand(command, args)
agentAPI.startOnboarding()
agentAPI.completeOnboardingStep(step, data)

// Messages
messagesAPI.create(patientId, messageType, context)
messagesAPI.getPending()
messagesAPI.approve(messageId)
messagesAPI.reject(messageId, reason)
messagesAPI.edit(messageId, newContent)
messagesAPI.send(messageId)
```

### Error Handling
- Try/catch on all API calls
- Display error to user
- 401 → Redirect to login
- Network errors → Retry option

## 🎨 Styling Guide

### Tailwind Utility Classes

**Buttons:**
```css
btn-primary     /* Blue, main action */
btn-secondary   /* White, secondary action */
btn-success     /* Green, approve */
btn-warning     /* Amber, caution */
```

**Cards:**
```css
card            /* White card with shadow */
```

**Badges:**
```css
badge           /* Base badge */
badge-pending   /* Amber - waiting */
badge-approved  /* Green - approved */
badge-sent      /* Blue - sent */
badge-draft     /* Gray - draft */
```

**Inputs:**
```css
input-field     /* Styled input/textarea */
```

### Custom Colors

```javascript
therapy-calm: '#4F46E5',    // Indigo
therapy-support: '#10B981', // Green
therapy-warm: '#F59E0B',    // Amber
therapy-gentle: '#8B5CF6',  // Purple
```

## 🧪 Testing Checklist

### Manual Testing

- [ ] Can register new account
- [ ] Can login with credentials
- [ ] Can complete onboarding (all 5 steps)
- [ ] Dashboard shows 3 buttons correctly
- [ ] Can create session summary
- [ ] Can create draft message
- [ ] Can approve message
- [ ] Can edit message before approving
- [ ] Can reject message
- [ ] Can view patients list
- [ ] Can view sessions list
- [ ] Can filter sessions
- [ ] Can logout
- [ ] RTL works correctly (Hebrew)
- [ ] Responsive on mobile
- [ ] Responsive on tablet

## 🚀 Deployment

### Build for Production

```bash
cd frontend
npm run build
```

Output: `frontend/dist/`

### Serve Static Files

**Option 1: Nginx**
```nginx
server {
    listen 80;
    server_name therapy.example.com;
    root /path/to/frontend/dist;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    location /api {
        proxy_pass http://localhost:8000;
    }
}
```

**Option 2: Vercel**
```bash
npm install -g vercel
vercel deploy
```

**Option 3: Netlify**
```bash
npm install -g netlify-cli
netlify deploy --prod
```

## 📝 Customization

### Change Colors

Edit `tailwind.config.js`:

```javascript
colors: {
  primary: {
    500: '#YOUR_COLOR',
  }
}
```

### Change Fonts

Edit `index.html` and `tailwind.config.js`:

```javascript
fontFamily: {
  hebrew: ['YourFont', 'sans-serif'],
}
```

### Add Logo

Replace in `Layout.tsx`:

```tsx
<img src="/logo.png" alt="Logo" className="h-10" />
```

## 🎯 Best Practices

1. **Always test message approval flow** - Critical feature!
2. **Test with Hebrew text** - Ensure RTL works
3. **Test on mobile** - Many therapists use phones
4. **Keep it simple** - Don't add unnecessary features
5. **Fast loading** - Therapists are busy
6. **Clear feedback** - Show what's happening
7. **Error messages in Hebrew** - User-friendly

---

**The interface is designed for therapists, not developers. Keep it simple!**
