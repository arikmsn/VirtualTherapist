import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { agentAPI } from '@/lib/api'
import { CheckCircleIcon } from '@heroicons/react/24/outline'

const STEPS = [
  {
    title: 'גישה טיפולית',
    description: 'ספר לנו על הגישה הטיפולית שלך',
  },
  {
    title: 'סגנון כתיבה',
    description: 'איך אתה אוהב לכתוב סיכומים והודעות?',
  },
  {
    title: 'העדפות סיכום',
    description: 'אילו חלקים חשובים בסיכום פגישה?',
  },
  {
    title: 'תקשורת עם מטופלים',
    description: 'תדירות וסגנון מעקב',
  },
  {
    title: 'דוגמאות ללמידה',
    description: 'ספק דוגמאות כדי שה-AI ילמד את הסגנון שלך',
  },
]

export default function OnboardingPage() {
  const navigate = useNavigate()
  const [currentStep, setCurrentStep] = useState(0)
  const [formData, setFormData] = useState({
    approach: '',
    approachDescription: '',
    tone: '',
    messageLength: 'short',
    terminology: '',
    followUpFrequency: 'weekly',
    preferredExercises: '',
    exampleSummary: '',
    exampleMessage: '',
  })

  const handleNext = async () => {
    if (currentStep < STEPS.length - 1) {
      setCurrentStep(currentStep + 1)
    } else {
      // Complete onboarding
      await completeOnboarding()
    }
  }

  const handleBack = () => {
    if (currentStep > 0) {
      setCurrentStep(currentStep - 1)
    }
  }

  const completeOnboarding = async () => {
    try {
      // Save all onboarding data
      await agentAPI.completeOnboardingStep(5, formData)
      navigate('/dashboard')
    } catch (error) {
      console.error('Error completing onboarding:', error)
    }
  }

  return (
    <div className="max-w-3xl mx-auto animate-fade-in" dir="rtl">
      {/* Progress Bar */}
      <div className="mb-8">
        <div className="flex items-center justify-between mb-4">
          {STEPS.map((step, index) => (
            <div key={index} className="flex items-center">
              <div
                className={`w-10 h-10 rounded-full flex items-center justify-center font-bold ${
                  index < currentStep
                    ? 'bg-therapy-support text-white'
                    : index === currentStep
                    ? 'bg-therapy-calm text-white'
                    : 'bg-gray-200 text-gray-500'
                }`}
              >
                {index < currentStep ? (
                  <CheckCircleIcon className="h-6 w-6" />
                ) : (
                  index + 1
                )}
              </div>
              {index < STEPS.length - 1 && (
                <div
                  className={`w-12 h-1 mx-2 ${
                    index < currentStep ? 'bg-therapy-support' : 'bg-gray-200'
                  }`}
                />
              )}
            </div>
          ))}
        </div>
        <div className="text-center">
          <div className="text-sm text-gray-600">
            שלב {currentStep + 1} מתוך {STEPS.length}
          </div>
        </div>
      </div>

      {/* Step Content */}
      <div className="card">
        <div className="mb-6">
          <h2 className="text-2xl font-bold mb-2">{STEPS[currentStep].title}</h2>
          <p className="text-gray-600">{STEPS[currentStep].description}</p>
        </div>

        {/* Step 1: Approach */}
        {currentStep === 0 && (
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                גישה טיפולית
              </label>
              <select
                value={formData.approach}
                onChange={(e) => setFormData({ ...formData, approach: e.target.value })}
                className="input-field"
              >
                <option value="">בחר גישה</option>
                <option value="CBT">CBT - טיפול קוגניטיבי התנהגותי</option>
                <option value="psychodynamic">פסיכודינמית</option>
                <option value="humanistic">הומניסטית</option>
                <option value="DBT">DBT - טיפול דיאלקטי התנהגותי</option>
                <option value="ACT">ACT - טיפול קבלה ומחויבות</option>
                <option value="integrative">אינטגרטיבית</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                תיאור הגישה שלך
              </label>
              <textarea
                value={formData.approachDescription}
                onChange={(e) => setFormData({ ...formData, approachDescription: e.target.value })}
                className="input-field h-32 resize-none"
                placeholder="למשל: אני עובדת בעיקר עם CBT, עם דגש על חשיפה הדרגתית ומחשבות אוטומטיות..."
              />
            </div>
          </div>
        )}

        {/* Step 2: Writing Style */}
        {currentStep === 1 && (
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                טון כתיבה
              </label>
              <input
                type="text"
                value={formData.tone}
                onChange={(e) => setFormData({ ...formData, tone: e.target.value })}
                className="input-field"
                placeholder="למשל: תומך וישיר, חם ומקצועי, אמפתי וממוקד..."
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                אורך הודעות מועדף
              </label>
              <select
                value={formData.messageLength}
                onChange={(e) => setFormData({ ...formData, messageLength: e.target.value })}
                className="input-field"
              >
                <option value="short">קצר (2-3 משפטים)</option>
                <option value="medium">בינוני (4-6 משפטים)</option>
                <option value="detailed">מפורט (פסקה מלאה)</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                מינוח נפוץ (הפרד בפסיקים)
              </label>
              <input
                type="text"
                value={formData.terminology}
                onChange={(e) => setFormData({ ...formData, terminology: e.target.value })}
                className="input-field"
                placeholder="למשל: תרגיל, חשיפה, מחשבות אוטומטיות, משימת בית..."
              />
            </div>
          </div>
        )}

        {/* Step 3: Summary Preferences */}
        {currentStep === 2 && (
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                חלקים בסיכום (בחר את החשובים)
              </label>
              <div className="space-y-2">
                {['נושאים שנדונו', 'התערבויות', 'התקדמות המטופל', 'משימות בית', 'תוכנית לפגישה הבאה', 'הערכת סיכון'].map(
                  (section) => (
                    <label key={section} className="flex items-center gap-2">
                      <input type="checkbox" className="w-4 h-4" defaultChecked />
                      <span>{section}</span>
                    </label>
                  )
                )}
              </div>
            </div>
          </div>
        )}

        {/* Step 4: Communication */}
        {currentStep === 3 && (
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                תדירות מעקב מועדפת
              </label>
              <select
                value={formData.followUpFrequency}
                onChange={(e) => setFormData({ ...formData, followUpFrequency: e.target.value })}
                className="input-field"
              >
                <option value="daily">יומי</option>
                <option value="weekly">שבועי</option>
                <option value="biweekly">דו-שבועי</option>
                <option value="as_needed">לפי הצורך</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                תרגילים מועדפים (הפרד בפסיקים)
              </label>
              <input
                type="text"
                value={formData.preferredExercises}
                onChange={(e) => setFormData({ ...formData, preferredExercises: e.target.value })}
                className="input-field"
                placeholder="למשל: נשימה, יומן מחשבות, חשיפה הדרגתית..."
              />
            </div>
          </div>
        )}

        {/* Step 5: Examples */}
        {currentStep === 4 && (
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                דוגמה לסיכום פגישה שלך
              </label>
              <textarea
                value={formData.exampleSummary}
                onChange={(e) => setFormData({ ...formData, exampleSummary: e.target.value })}
                className="input-field h-32 resize-none"
                placeholder="הדבק כאן סיכום פגישה טיפוסי שכתבת..."
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                דוגמה להודעה למטופל
              </label>
              <textarea
                value={formData.exampleMessage}
                onChange={(e) => setFormData({ ...formData, exampleMessage: e.target.value })}
                className="input-field h-24 resize-none"
                placeholder="הדבק כאן הודעה טיפוסית שלך למטופל..."
              />
            </div>
          </div>
        )}

        {/* Navigation */}
        <div className="flex items-center justify-between mt-8 pt-6 border-t border-gray-200">
          <button
            onClick={handleBack}
            disabled={currentStep === 0}
            className="btn-secondary disabled:opacity-50 disabled:cursor-not-allowed"
          >
            ← חזור
          </button>
          <button onClick={handleNext} className="btn-primary">
            {currentStep === STEPS.length - 1 ? 'סיים והתחל' : 'המשך →'}
          </button>
        </div>
      </div>
    </div>
  )
}
