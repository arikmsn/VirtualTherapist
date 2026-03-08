/**
 * PrintPatientPage — clean print view for a patient's AI documents.
 *
 * Route: /patients/:patientId/print
 * Query params:
 *   ?doc=summary   → deep summary only
 *   ?doc=plan      → treatment plan only
 *   (default)      → both documents
 *
 * Fetches patient + latest deep summary + latest treatment plan, then renders
 * a print-friendly document. "הדפסה" button opens the browser print dialog.
 *
 * CSS @media print hides the print button and navigation chrome automatically.
 */

import { useEffect, useState } from 'react'
import { useParams, useSearchParams, Link } from 'react-router-dom'
import { patientsAPI, patientSummariesAPI, treatmentPlanAPI, therapistAPI } from '@/lib/api'
import AppLogo from '@/components/common/AppLogo'
import { deepSummaryToText, treatmentPlanToText, type DeepSummary } from '@/lib/docText'
import { formatDateIL } from '@/lib/dateUtils'

interface Patient {
  id: number
  full_name: string
  primary_concerns?: string
  start_date?: string
}

interface TreatmentPlanVersion {
  plan_id: number
  plan_json: Record<string, unknown> | null
  rendered_text: string | null
  approved_at: string | null
  created_at: string
  version: number
  status: string
  title: string | null
}

export default function PrintPatientPage() {
  const { patientId } = useParams<{ patientId: string }>()
  const [searchParams] = useSearchParams()
  const doc = searchParams.get('doc') // 'summary' | 'plan' | null (both)
  const id = Number(patientId)

  const [patient, setPatient] = useState<Patient | null>(null)
  const [therapistName, setTherapistName] = useState('')
  const [insight, setInsight] = useState<DeepSummary | null>(null)
  const [plan, setPlan] = useState<TreatmentPlanVersion | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const showSummary = !doc || doc === 'summary'
  const showPlan = !doc || doc === 'plan'

  useEffect(() => {
    const load = async () => {
      try {
        const [patientData, profileData] = await Promise.all([
          patientsAPI.get(id),
          therapistAPI.getProfile().catch(() => null),
        ])
        setPatient(patientData)
        if (profileData) {
          setTherapistName((profileData as any).full_name || (profileData as any).email || '')
        }

        // Fetch AI documents in parallel, ignoring 404s.
        // Deep summary: use history (fast GET) instead of regenerating (slow POST).
        const [insightData, planData] = await Promise.allSettled([
          showSummary
            ? patientSummariesAPI.getDeepSummaryHistory(id)
                .then(h => (h[0]?.summary_json as DeepSummary | null) ?? null)
                .catch(() => null)
            : Promise.resolve(null),
          showPlan ? treatmentPlanAPI.get(id).catch(() => null) : Promise.resolve(null),
        ])

        if (insightData.status === 'fulfilled' && insightData.value) {
          setInsight(insightData.value as DeepSummary)
        }
        if (planData.status === 'fulfilled' && planData.value) {
          // treatmentPlanAPI.get returns a TreatmentPlanVersion with plan_json inside
          const v = planData.value as TreatmentPlanVersion
          setPlan(v)
        }
      } catch (err: any) {
        setError(err.response?.data?.detail || 'שגיאה בטעינת הנתונים')
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [id, showSummary, showPlan])

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center" dir="rtl">
        <div className="text-center space-y-3">
          <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-indigo-600 mx-auto"></div>
          <p className="text-sm text-gray-500">טוען מסמכים...</p>
        </div>
      </div>
    )
  }

  if (error || !patient) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center gap-4" dir="rtl">
        <p className="text-red-600">{error || 'לא נמצאו נתונים'}</p>
        <Link to={`/patients/${id}`} className="text-indigo-600 underline text-sm">חזרה לפרופיל המטופל</Link>
      </div>
    )
  }

  // Extract from the clinical plan_json schema (primary_goals / interventions_planned / milestones / risk_considerations)
  const pj = (plan?.plan_json ?? {}) as Record<string, unknown>
  const planPresentingProblem = pj.presenting_problem as string | undefined
  const planPrimaryGoals = (pj.primary_goals ?? []) as Array<{ goal_id?: string; description?: string; priority?: string; status?: string }>
  const planInterventionsPlanned = (pj.interventions_planned ?? []) as Array<{ intervention?: string; frequency?: string }>
  const planMilestones = (pj.milestones ?? []) as Array<{ description?: string; target_by_session?: number; achieved?: boolean }>
  const planRisks = (pj.risk_considerations ?? []) as string[]
  const hasPlanContent = !!(planPresentingProblem || planPrimaryGoals.length || planInterventionsPlanned.length || planMilestones.length || planRisks.length)

  const PRIORITY_HE: Record<string, string> = { high: 'גבוהה', medium: 'בינונית', low: 'נמוכה' }
  const STATUS_HE: Record<string, string> = { not_started: 'לא החלה', in_progress: 'בתהליך', achieved: 'הושגה', dropped: 'הופסקה' }

  return (
    <div className="min-h-screen bg-white" dir="rtl">
      {/* ── Print controls (hidden in print) ── */}
      <div className="no-print sticky top-0 z-10 bg-gray-50 border-b border-gray-200 px-6 py-3 flex items-center justify-between">
        <Link to={`/patients/${id}`} className="text-sm text-gray-600 hover:text-gray-900 flex items-center gap-1">
          ← חזרה לפרופיל המטופל
        </Link>
        <button
          onClick={() => window.print()}
          className="px-4 py-2 bg-indigo-600 text-white text-sm font-medium rounded-lg hover:bg-indigo-700 transition-colors flex items-center gap-2"
        >
          🖨 הדפסה / שמור PDF
        </button>
      </div>

      {/* ── Document body ── */}
      <div className="max-w-2xl mx-auto px-8 py-10 print:px-0 print:py-4">
        {/* Header */}
        <div className="flex items-start justify-between mb-8 pb-4 border-b border-gray-200">
          <AppLogo variant="full" size="sm" />
          <div className="text-left text-xs text-gray-400 print:text-gray-600">
            <p>{new Date().toLocaleDateString('he-IL')}</p>
          </div>
        </div>

        {/* Document meta */}
        <div className="mb-6 space-y-1">
          <h1 className="text-2xl font-bold text-gray-900">
            {showSummary && showPlan
              ? 'מסמכים קליניים'
              : showSummary
              ? 'סיכום עומק AI'
              : 'תוכנית טיפולית'}
          </h1>
          <div className="text-sm text-gray-600 space-y-0.5">
            <p><span className="font-medium">מטופל/ת:</span> {patient.full_name}</p>
            {therapistName && <p><span className="font-medium">מטפל/ת:</span> {therapistName}</p>}
            {patient.start_date && (
              <p><span className="font-medium">תחילת טיפול:</span> {formatDateIL(patient.start_date)}</p>
            )}
            {patient.primary_concerns && (
              <p><span className="font-medium">הפניה בגין:</span> {patient.primary_concerns}</p>
            )}
          </div>
        </div>

        {/* ── Deep Summary ── */}
        {showSummary && (
          <div className="mb-10">
            <h2 className="text-lg font-bold text-purple-900 mb-4 flex items-center gap-2 border-b-2 border-purple-100 pb-2">
              ✦ סיכום עומק AI
            </h2>

            {!insight ? (
              <p className="text-gray-400 text-sm">אין סיכום עומק זמין.</p>
            ) : (
              <div className="space-y-5 text-sm leading-relaxed">
                {insight.overall_treatment_picture && (
                  <section>
                    <h3 className="font-bold text-gray-900 mb-1.5">תמונת מצב כללית של הטיפול</h3>
                    <p className="text-gray-800 whitespace-pre-line">{insight.overall_treatment_picture}</p>
                  </section>
                )}
                {(insight.timeline_highlights ?? []).length > 0 && (
                  <section>
                    <h3 className="font-bold text-gray-900 mb-1.5">אבני דרך לאורך הדרך</h3>
                    <ul className="list-disc list-inside space-y-1 text-gray-800">
                      {(insight.timeline_highlights ?? []).map((h, i) => <li key={i}>{h}</li>)}
                    </ul>
                  </section>
                )}
                {insight.goals_and_tasks && (
                  <section>
                    <h3 className="font-bold text-gray-900 mb-1.5">מטרות ומשימות</h3>
                    <p className="text-gray-800 whitespace-pre-line">{insight.goals_and_tasks}</p>
                  </section>
                )}
                {insight.measurable_progress && (
                  <section>
                    <h3 className="font-bold text-gray-900 mb-1.5">סימני התקדמות</h3>
                    <p className="text-gray-800 whitespace-pre-line">{insight.measurable_progress}</p>
                  </section>
                )}
                {insight.directions_for_next_phase && (
                  <section>
                    <h3 className="font-bold text-gray-900 mb-1.5">כיוונים להמשך</h3>
                    <p className="text-gray-800 whitespace-pre-line">{insight.directions_for_next_phase}</p>
                  </section>
                )}
                {/* Legacy fields */}
                {!insight.overall_treatment_picture && insight.overview && (
                  <section>
                    <h3 className="font-bold text-gray-900 mb-1.5">סקירה כללית</h3>
                    <p className="text-gray-800 whitespace-pre-line">{insight.overview}</p>
                  </section>
                )}
              </div>
            )}
          </div>
        )}

        {/* ── Treatment Plan ── */}
        {showPlan && (
          <div className="mb-10">
            <h2 className="text-lg font-bold text-indigo-900 mb-4 flex items-center gap-2 border-b-2 border-indigo-100 pb-2">
              📋 תוכנית טיפולית
            </h2>

            {!plan || !hasPlanContent ? (
              <p className="text-gray-400 text-sm">אין תוכנית טיפולית שמורה.</p>
            ) : (
              <div className="space-y-5 text-sm leading-relaxed">
                {planPresentingProblem && (
                  <section>
                    <h3 className="font-bold text-gray-900 mb-1.5">📋 בעיה מוצגת</h3>
                    <p className="text-gray-800 whitespace-pre-line">{planPresentingProblem}</p>
                  </section>
                )}

                {planPrimaryGoals.length > 0 && (
                  <section>
                    <h3 className="font-bold text-gray-900 mb-2">🎯 מטרות טיפול</h3>
                    <div className="space-y-2">
                      {planPrimaryGoals.map((g, i) => (
                        <div key={i} className="border border-gray-100 rounded p-3">
                          <p className="text-gray-800">{g.description}</p>
                          <div className="flex gap-3 mt-1 text-xs text-gray-500">
                            {g.priority && <span>עדיפות: {PRIORITY_HE[g.priority] ?? g.priority}</span>}
                            {g.status && <span>סטטוס: {STATUS_HE[g.status] ?? g.status}</span>}
                          </div>
                        </div>
                      ))}
                    </div>
                  </section>
                )}

                {planInterventionsPlanned.length > 0 && (
                  <section>
                    <h3 className="font-bold text-gray-900 mb-1.5">🛠️ התערבויות מתוכננות</h3>
                    <ul className="list-disc list-inside space-y-1 text-gray-800">
                      {planInterventionsPlanned.map((item, i) => (
                        <li key={i}>
                          {item.intervention}
                          {item.frequency && <span className="text-gray-500"> — {item.frequency}</span>}
                        </li>
                      ))}
                    </ul>
                  </section>
                )}

                {planMilestones.length > 0 && (
                  <section>
                    <h3 className="font-bold text-gray-900 mb-1.5">📍 אבני דרך</h3>
                    <ul className="list-disc list-inside space-y-1 text-gray-800">
                      {planMilestones.map((m, i) => (
                        <li key={i}>
                          {m.description}
                          {m.target_by_session && <span className="text-gray-500"> (פגישה יעד: {m.target_by_session})</span>}
                          {m.achieved && <span className="text-green-600"> ✓</span>}
                        </li>
                      ))}
                    </ul>
                  </section>
                )}

                {planRisks.length > 0 && (
                  <section>
                    <h3 className="font-bold text-gray-900 mb-1.5">⚠️ שיקולי סיכון</h3>
                    <ul className="list-disc list-inside space-y-1 text-gray-800">
                      {planRisks.map((r, i) => <li key={i}>{r}</li>)}
                    </ul>
                  </section>
                )}

                {plan.approved_at && (
                  <p className="text-xs text-gray-400">אושר: {formatDateIL(plan.approved_at)}</p>
                )}
                {!plan.approved_at && (
                  <p className="text-xs text-amber-600">* הצעת AI — טרם אושרה</p>
                )}
              </div>
            )}
          </div>
        )}

        {/* Footer */}
        <div className="mt-12 pt-4 border-t border-gray-200 text-xs text-gray-400 text-center">
          <p>מסמך זה הופק על ידי TherapyCompanion.AI · סודי</p>
        </div>
      </div>

      {/* Print-specific styles */}
      <style>{`
        @media print {
          .no-print { display: none !important; }
          body { background: white; }
        }
      `}</style>
    </div>
  )
}

// Re-export text helpers for use by print buttons in other pages
export { deepSummaryToText, treatmentPlanToText }
