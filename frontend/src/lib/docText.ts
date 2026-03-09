/**
 * Plain-text serializers for AI documents.
 *
 * Used by CopyButton and print pages to convert structured AI objects
 * into human-readable plain text without HTML markup.
 */

export interface DeepSummary {
  overall_treatment_picture?: string
  timeline_highlights?: string[]
  goals_and_tasks?: string
  measurable_progress?: string
  directions_for_next_phase?: string
  // legacy fields
  overview?: string
  progress?: string
  patterns?: string[]
  risks?: string[]
  suggestions_for_next_sessions?: string[]
}

export interface TreatmentPlanGoal {
  id: string | number
  title: string
  description: string
}

export interface TreatmentPlan {
  goals?: TreatmentPlanGoal[]
  focus_areas?: string[]
  suggested_interventions?: string[]
}

export interface SessionSummary {
  full_summary?: string | null
  topics_discussed?: string[] | null
  interventions_used?: string[] | null
  patient_progress?: string | null
  homework_assigned?: string[] | null
  next_session_plan?: string | null
  mood_observed?: string | null
  risk_assessment?: string | null
}

// ─── Deep Summary ───────────────────────────────────────────────────────────

export function deepSummaryToText(insight: DeepSummary): string {
  const parts: string[] = []

  if (insight.overall_treatment_picture) {
    parts.push('תמונת מצב כללית של הטיפול')
    parts.push(insight.overall_treatment_picture)
  }

  if ((insight.timeline_highlights ?? []).length > 0) {
    parts.push('\nאבני דרך לאורך הדרך')
    parts.push((insight.timeline_highlights ?? []).map((h) => `• ${h}`).join('\n'))
  }

  if (insight.goals_and_tasks) {
    parts.push('\nמטרות ומשימות')
    parts.push(insight.goals_and_tasks)
  }

  if (insight.measurable_progress) {
    parts.push('\nסימני התקדמות')
    parts.push(insight.measurable_progress)
  }

  if (insight.directions_for_next_phase) {
    parts.push('\nכיוונים להמשך')
    parts.push(insight.directions_for_next_phase)
  }

  // Legacy format fallback
  if (parts.length === 0) {
    if (insight.overview) {
      parts.push('סקירה כללית')
      parts.push(insight.overview)
    }
    if (insight.progress) {
      parts.push('\nהתקדמות לאורך זמן')
      parts.push(insight.progress)
    }
    if ((insight.patterns ?? []).length > 0) {
      parts.push('\nדפוסים מרכזיים')
      parts.push((insight.patterns ?? []).map((p) => `• ${p}`).join('\n'))
    }
    if ((insight.risks ?? []).length > 0) {
      parts.push('\nנקודות סיכון למעקב')
      parts.push((insight.risks ?? []).map((r) => `• ${r}`).join('\n'))
    }
    if ((insight.suggestions_for_next_sessions ?? []).length > 0) {
      parts.push('\nרעיונות לפגישות הבאות')
      parts.push((insight.suggestions_for_next_sessions ?? []).map((s) => `• ${s}`).join('\n'))
    }
  }

  return parts.join('\n').trim()
}

// ─── Treatment Plan ──────────────────────────────────────────────────────────

export function treatmentPlanToText(plan: TreatmentPlan): string {
  const parts: string[] = []

  if ((plan.goals ?? []).length > 0) {
    parts.push('מטרות טיפול')
    parts.push(
      (plan.goals ?? [])
        .map((g) => `• ${g.title}\n  ${g.description}`)
        .join('\n')
    )
  }

  if ((plan.focus_areas ?? []).length > 0) {
    parts.push('\nנושאים מרכזיים לעבודה')
    parts.push((plan.focus_areas ?? []).map((a) => `• ${a}`).join('\n'))
  }

  if ((plan.suggested_interventions ?? []).length > 0) {
    parts.push('\nסוגי התערבויות מוצעות')
    parts.push((plan.suggested_interventions ?? []).map((i) => `• ${i}`).join('\n'))
  }

  return parts.join('\n').trim()
}

// ─── Clinical Treatment Plan (saved plan_json from TreatmentPlanPipeline) ───

export function clinicalPlanToText(pj: Record<string, unknown>): string {
  const parts: string[] = []

  const presenting = pj.presenting_problem as string | undefined
  if (presenting) {
    parts.push('בעיה מוצגת')
    parts.push(presenting)
  }

  const focusAreas = (pj.focus_areas ?? []) as string[]
  if (focusAreas.length > 0) {
    parts.push('\nתחומי התמקדות')
    parts.push(focusAreas.map((a) => `• ${a}`).join('\n'))
  }

  type Goal = { goal_id?: string; description?: string; priority?: string; status?: string; target_sessions?: number }
  const goals = (pj.primary_goals ?? []) as Goal[]
  if (goals.length > 0) {
    parts.push('\nמטרות טיפוליות')
    const PRIORITY_HE: Record<string, string> = { high: 'גבוהה', medium: 'בינונית', low: 'נמוכה' }
    const STATUS_HE: Record<string, string> = {
      not_started: 'לא החלה', in_progress: 'בתהליך', achieved: 'הושגה', dropped: 'הופסקה'
    }
    parts.push(
      goals.map((g, i) => {
        const id = g.goal_id ?? `G${i + 1}`
        const pri = g.priority ? ` | עדיפות: ${PRIORITY_HE[g.priority] ?? g.priority}` : ''
        const sts = g.status ? ` | סטטוס: ${STATUS_HE[g.status] ?? g.status}` : ''
        return `• [${id}] ${g.description ?? ''}${pri}${sts}`
      }).join('\n')
    )
  }

  type Intervention = { intervention?: string; frequency?: string }
  const interventions = (pj.interventions_planned ?? []) as Intervention[]
  if (interventions.length > 0) {
    parts.push('\nהתערבויות מתוכננות')
    parts.push(
      interventions.map((iv) => {
        const freq = iv.frequency ? ` (${iv.frequency})` : ''
        return `• ${iv.intervention ?? ''}${freq}`
      }).join('\n')
    )
  }

  type Milestone = { description?: string; target_by_session?: number; achieved?: boolean }
  const milestones = (pj.milestones ?? []) as Milestone[]
  if (milestones.length > 0) {
    parts.push('\nאבני דרך')
    parts.push(
      milestones.map((m) => {
        const by = m.target_by_session ? ` — פגישה ${m.target_by_session}` : ''
        const done = m.achieved ? ' ✓' : ''
        return `• ${m.description ?? ''}${by}${done}`
      }).join('\n')
    )
  }

  const risks = (pj.risk_considerations ?? []) as string[]
  if (risks.length > 0) {
    parts.push('\nשיקולי סיכון')
    parts.push(risks.map((r) => `• ${r}`).join('\n'))
  }

  return parts.join('\n').trim()
}

// ─── Session Summary ─────────────────────────────────────────────────────────

function stripAiArtifacts(text: string | null | undefined): string {
  if (!text) return ''
  return text
    .replace(/^```(?:json)?\s*/gm, '')
    .replace(/^```\s*/gm, '')
    .replace(/^\*\*[^*]+\*\*\s*$/gm, '')
    .trim()
}

export function sessionSummaryToText(summary: SessionSummary): string {
  const parts: string[] = []

  const full = stripAiArtifacts(summary.full_summary)
  if (full) {
    parts.push('סיכום כללי')
    parts.push(full)
  }

  if ((summary.topics_discussed ?? []).length > 0) {
    parts.push('\nנושאים שעלו')
    parts.push((summary.topics_discussed ?? []).map((t) => `• ${t}`).join('\n'))
  }

  if ((summary.interventions_used ?? []).length > 0) {
    parts.push('\nהתערבויות')
    parts.push((summary.interventions_used ?? []).map((i) => `• ${i}`).join('\n'))
  }

  if (summary.patient_progress) {
    parts.push('\nהתקדמות')
    parts.push(summary.patient_progress)
  }

  if ((summary.homework_assigned ?? []).length > 0) {
    parts.push('\nמשימות לבית')
    parts.push((summary.homework_assigned ?? []).map((h) => `• ${h}`).join('\n'))
  }

  if (summary.next_session_plan) {
    parts.push('\nתוכנית לפגישה הבאה')
    parts.push(summary.next_session_plan)
  }

  if (summary.mood_observed) {
    parts.push('\nמצב רוח שנצפה')
    parts.push(summary.mood_observed)
  }

  if (summary.risk_assessment) {
    parts.push('\nהערכת סיכון')
    parts.push(summary.risk_assessment)
  }

  return parts.join('\n').trim()
}
