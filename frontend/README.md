# TherapyCompanion.AI - Frontend

Beautiful, simple web interface for therapists.

## 🎨 Features

- **✨ 3-Button Interface** - Dead simple: Write Summary, Send to Patient, New Recording
- **🇮🇱 Hebrew RTL Support** - Full right-to-left support with Hebrew fonts
- **📱 Responsive Design** - Works on desktop, tablet, and mobile
- **⚡ Fast & Modern** - Built with React, TypeScript, and Vite
- **🎯 Intuitive UX** - Designed for non-technical therapists

## 🚀 Quick Start

### Prerequisites

- Node.js 18+
- npm or yarn

### Installation

```bash
cd frontend

# Install dependencies
npm install

# Create environment file
cp .env.example .env

# Start development server
npm run dev
```

The app will be available at: **http://localhost:3000**

## 📦 Build for Production

```bash
# Build
npm run build

# Preview production build
npm run preview
```

## 🏗️ Project Structure

```
frontend/
├── src/
│   ├── components/       # Reusable components
│   │   └── Layout.tsx    # Main layout with navigation
│   ├── pages/            # Page components
│   │   ├── DashboardPage.tsx     # 3-button main dashboard
│   │   ├── MessagesPage.tsx      # Message approval interface
│   │   ├── PatientsPage.tsx      # Patient management
│   │   ├── SessionsPage.tsx      # Sessions and summaries
│   │   ├── OnboardingPage.tsx    # 5-step onboarding
│   │   ├── LoginPage.tsx         # Login
│   │   └── RegisterPage.tsx      # Registration
│   ├── lib/
│   │   └── api.ts        # API client
│   ├── store/
│   │   └── authStore.ts  # Authentication state
│   ├── App.tsx           # Main app component
│   ├── main.tsx          # Entry point
│   └── index.css         # Global styles
├── public/               # Static assets
├── index.html           # HTML template
├── package.json         # Dependencies
├── vite.config.ts       # Vite configuration
├── tailwind.config.js   # Tailwind CSS config
└── tsconfig.json        # TypeScript config
```

## 🎯 Main Pages

### 1. Dashboard (3 Buttons!)
The core interface with 3 main actions:
- 📝 **Write Summary** - Create session summary
- 👤 **Send to Patient** - Draft message for patient
- 🎙️ **New Recording** - Record and transcribe

### 2. Messages (Approval Interface)
- View all pending messages
- Approve, edit, or reject AI-generated messages
- Send approved messages to patients
- **Critical:** Nothing sends without therapist approval!

### 3. Patients
- View all patients
- Quick stats per patient
- Create summaries and messages
- Track homework and progress

### 4. Sessions
- View all therapy sessions
- Review and approve summaries
- Filter by status (pending, approved)

### 5. Onboarding
- 5-step personalization process
- Teaches AI the therapist's style
- Examples for learning

## 🎨 Design System

### Colors
- **Primary (Calm):** `#4F46E5` - Main actions
- **Support (Green):** `#10B981` - Approve, success
- **Warm (Amber):** `#F59E0B` - Warnings, reminders
- **Gentle (Purple):** `#8B5CF6` - Accents

### Typography
- **Hebrew:** Rubik, Assistant
- **RTL Support:** Full right-to-left layout

### Components
- **btn-primary** - Main action buttons
- **btn-secondary** - Secondary actions
- **btn-success** - Approve/confirm actions
- **card** - Content containers
- **badge** - Status indicators

## 🔧 Configuration

### Environment Variables

Create `.env` file:

```env
VITE_API_URL=http://localhost:8000/api/v1
```

### API Integration

The frontend connects to the FastAPI backend. Make sure the backend is running:

```bash
# In root directory
python -m app.main
```

## 🧪 Development

### Run Development Server

```bash
npm run dev
```

### Build for Production

```bash
npm run build
```

### Preview Production Build

```bash
npm run preview
```

### Lint Code

```bash
npm run lint
```

## 📱 Responsive Design

The interface is fully responsive:
- **Desktop:** Full 3-column layout
- **Tablet:** 2-column layout
- **Mobile:** Single column, optimized for touch

## 🌐 Browser Support

- Chrome/Edge (latest)
- Firefox (latest)
- Safari (latest)
- Mobile browsers (iOS Safari, Chrome Mobile)

## 🔒 Security

- All API calls require JWT authentication
- Tokens stored securely in localStorage
- Automatic token refresh
- 401 errors redirect to login

## 📖 Learn More

- [React Documentation](https://react.dev/)
- [Vite Documentation](https://vitejs.dev/)
- [Tailwind CSS](https://tailwindcss.com/)
- [TypeScript](https://www.typescriptlang.org/)

## 🆘 Troubleshooting

### Port already in use

Change the port in `vite.config.ts`:

```typescript
server: {
  port: 3001, // Change this
}
```

### API connection errors

1. Check backend is running: `http://localhost:8000/health`
2. Verify `VITE_API_URL` in `.env`
3. Check browser console for errors

### Build errors

```bash
# Clear cache and reinstall
rm -rf node_modules
npm install
npm run build
```

## 🎯 Next Steps

1. ✅ **Customize branding** - Update colors, logo
2. ✅ **Add real data** - Connect to actual API
3. ✅ **Test thoroughly** - Test all user flows
4. ✅ **Deploy** - Deploy to production

---

**Made with ❤️ for mental health professionals**
