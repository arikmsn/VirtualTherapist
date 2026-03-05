"""
Core AI Agent - TherapyCompanion.AI
This is the heart of the system - the personalized AI therapist assistant
"""

from typing import Optional, Dict, Any, List
import json
from app.core.config import settings
from app.models.therapist import TherapistProfile
from app.ai.models import FlowType, GenerationResult
from app.ai.provider import AIProvider, AnthropicProvider
from app.ai.router import ModelRouter
from loguru import logger

# Imported lazily to avoid circular imports at module load
# from app.models.modality import ModalityPack
# from app.ai.modality import assemble_system_prompt


class SessionSummaryResult:
    """Structured result from AI session summary generation."""

    def __init__(
        self,
        topics_discussed: List[str],
        interventions_used: List[str],
        patient_progress: str,
        homework_assigned: List[str],
        next_session_plan: str,
        mood_observed: str,
        risk_assessment: str,
        full_summary: str,
    ):
        self.topics_discussed = topics_discussed
        self.interventions_used = interventions_used
        self.patient_progress = patient_progress
        self.homework_assigned = homework_assigned
        self.next_session_plan = next_session_plan
        self.mood_observed = mood_observed
        self.risk_assessment = risk_assessment
        self.full_summary = full_summary


class PatientInsightResult:
    """Structured result from AI patient insight summary."""

    def __init__(
        self,
        overview: str,
        progress: str,
        patterns: List[str],
        risks: List[str],
        suggestions_for_next_sessions: List[str],
    ):
        self.overview = overview
        self.progress = progress
        self.patterns = patterns
        self.risks = risks
        self.suggestions_for_next_sessions = suggestions_for_next_sessions


class SessionPrepBriefResult:
    """Structured result from AI session preparation brief (4-section clinical format)."""

    def __init__(
        self,
        history_summary: List[str],
        last_session: List[str],
        tasks_to_check: List[str],
        focus_for_today: List[str],
        watch_out_for: List[str],
    ):
        self.history_summary = history_summary        # מה היה עד עכשיו
        self.last_session = last_session              # מה היה בפגישה האחרונה
        self.tasks_to_check = tasks_to_check          # משימות לבדיקה היום
        self.focus_for_today = focus_for_today        # על מה כדאי להתמקד
        self.watch_out_for = watch_out_for            # שים לב / סיכון


class DeepSummaryResult:
    """
    Structured result from AI deep treatment summary.
    JSON keys are always English; text values are in therapist_locale language.
    """

    def __init__(
        self,
        overall_treatment_picture: str,
        timeline_highlights: List[str],
        goals_and_tasks: str,
        measurable_progress: str,
        directions_for_next_phase: str,
    ):
        self.overall_treatment_picture = overall_treatment_picture
        self.timeline_highlights = timeline_highlights
        self.goals_and_tasks = goals_and_tasks
        self.measurable_progress = measurable_progress
        self.directions_for_next_phase = directions_for_next_phase


class TreatmentGoal:
    """A single inferred treatment goal with stable English id."""

    def __init__(self, id: str, title: str, description: str):
        self.id = id
        self.title = title
        self.description = description


class TreatmentPlanResult:
    """
    Structured result from AI treatment plan preview.
    JSON keys are always English; text values are in therapist_locale language.
    """

    def __init__(
        self,
        goals: List[TreatmentGoal],
        focus_areas: List[str],
        suggested_interventions: List[str],
    ):
        self.goals = goals
        self.focus_areas = focus_areas
        self.suggested_interventions = suggested_interventions


class TodayInsightItem:
    """A single per-patient smart reminder for today's sessions."""

    def __init__(self, patient_id: int, title: str, body: str):
        self.patient_id = patient_id
        self.title = title
        self.body = body


class TodayInsightsResult:
    """Result from AI today-insights generation — one item per patient."""

    def __init__(self, insights: List[TodayInsightItem]):
        self.insights = insights


class TherapyAgent:
    """
    The core AI agent that mimics the therapist's personality and style

    This agent:
    1. Learns the therapist's writing style and approach
    2. Generates messages in the therapist's voice
    3. Creates session summaries matching therapist's format
    4. Handles commands (/start, /summary, etc.)
    5. Speaks primarily in Hebrew
    """

    def __init__(
        self,
        therapist_profile: Optional[TherapistProfile] = None,
        provider: Optional[AIProvider] = None,
        modality_pack=None,  # Optional[ModalityPack] — typed loosely to avoid circular import
    ):
        """
        Args:
            therapist_profile: personalises prompts.
            provider:          AI provider; defaults to AnthropicProvider from settings.
            modality_pack:     Active ModalityPack; triggers three-layer prompt assembly.
        """
        from app.core.config import is_placeholder_key

        self.profile = therapist_profile
        self.modality_pack = modality_pack
        self.router = ModelRouter()
        self._last_result: Optional[GenerationResult] = None

        if provider is not None:
            self.provider: Optional[AIProvider] = provider
        elif not is_placeholder_key(settings.ANTHROPIC_API_KEY):
            self.provider = AnthropicProvider(api_key=settings.ANTHROPIC_API_KEY)
        else:
            logger.warning("ANTHROPIC_API_KEY is missing - AI text generation will not work")
            self.provider = None

        base_prompt = self._build_system_prompt()
        # Phase 2: apply three-layer assembly (modality → quality rule → base)
        from app.ai.modality import assemble_system_prompt
        self.system_prompt = assemble_system_prompt(base_prompt, modality_pack)

    def _build_system_prompt(self) -> str:
        """
        Build the system prompt that defines the agent's personality
        This is customized based on the therapist's profile
        """

        base_prompt = """\
אתה **TherapyCompanion.AI** - סוכן AI מתקדם המשמש כ\
"עוזר מטפל וירטואלי אישי" \
שממשיך את עבודת המטפל האנושי בין הפגישות.

## תפקיד כפול:
1. **סייע למטפל בזרימת העבודה היומית** (תיעוד, סיכומים, משימות)
2. **המשך פעילות טיפולית** עם מטופלים בין פגישות

## אבטחה ופרטיות (קריטי!)
1. אף פעם לא לשלוח דבר למטופל ללא אישור מפורש של המטפל
2. כל השיחות מוצפנות מקצה לקצה (AES-256)
3. מלוא תיעוד ביקורת על כל פעולה
4. אפשרות מחיקה מלאה בכל עת (GDPR)
5. אין שיתוף נתונים עם צדדים שלישיים

## התאמה אישית מלאה לכל מטפל:
אתה צריך לדבר בדיוק כמו המטפל - \
להשתמש במינוח שלו, בטון שלו, בסגנון הכתיבה שלו.

"""

        # Add therapist-specific customization if profile exists
        if self.profile:
            p = self.profile
            name = (
                p.therapist.full_name
                if hasattr(p, "therapist") else "לא צוין"
            )
            approach_desc = (
                f"**תיאור הגישה:** {p.approach_description}"
                if p.approach_description else ""
            )
            tone = p.tone or "תומך וישיר"
            msg_len = p.message_length_preference or "קצר ממוקד"
            terminology = (
                ", ".join(p.common_terminology)
                if p.common_terminology else "לא צוין"
            )
            freq = p.follow_up_frequency or "שבועי"
            exercises = (
                ", ".join(p.preferred_exercises)
                if p.preferred_exercises else "לא צוין"
            )

            # Tone/directiveness labels (1-5 scale)
            tone_labels = {1: "פורמלי מאוד", 2: "פורמלי", 3: "מאוזן", 4: "חם", 5: "חם מאוד"}
            dir_labels = {1: "חקרני לחלוטין", 2: "חקרני", 3: "מאוזן", 4: "מכוון", 5: "מכוון מאוד"}
            tw = getattr(p, "tone_warmth", None) or 3
            dv = getattr(p, "directiveness", None) or 3
            tone_label = tone_labels.get(tw, "מאוזן")
            dir_label = dir_labels.get(dv, "מאוזן")

            # Prohibitions block
            prohibitions_list = getattr(p, "prohibitions", None) or []
            prohibitions_block = ""
            if prohibitions_list:
                items = "\n".join(f"❌ {rule}" for rule in prohibitions_list)
                prohibitions_block = f"\n## 🚫 כללים שאסור לעבור (הגדרת המטפל):\n{items}\n"

            # Custom rules block
            custom_rules_val = getattr(p, "custom_rules", None) or ""
            custom_rules_block = ""
            if custom_rules_val.strip():
                custom_rules_block = f"\n## 📝 כללים נוספים של המטפל:\n{custom_rules_val.strip()}\n"

            # Professional credentials block
            edu = getattr(p, "education", None) or ""
            certs = getattr(p, "certifications", None) or ""
            yoe = getattr(p, "years_of_experience", None) or ""
            expertise = getattr(p, "areas_of_expertise", None) or ""
            prof_block = ""
            parts = []
            if edu.strip(): parts.append(f"השכלה: {edu.strip()}")
            if certs.strip(): parts.append(f"הסמכות: {certs.strip()}")
            if yoe.strip(): parts.append(f"ניסיון: {yoe.strip()} שנים")
            if expertise.strip(): parts.append(f"תחומי התמחות: {expertise.strip()}")
            if parts:
                prof_block = "\n**פרטים מקצועיים:**\n" + "\n".join(f"- {pt}" for pt in parts) + "\n"

            custom_prompt = f"""
## פרופיל המטפל שאתה מחקה:

**שם המטפל:** {name}
**גישה טיפולית:** {p.therapeutic_approach.value}
{approach_desc}
{prof_block}
**טון ושפה:**
- טון (כפי שהוגדר): {tone}
- חמימות (Twin): {tone_label} ({tw}/5)
- הכוונה (Twin): {dir_label} ({dv}/5)
- אורך הודעות: {msg_len}
- מינוח נפוץ: {terminology}

**סגנון סיכומים:**
- תדירות מעקב: {freq}
- תרגילים מועדפים: {exercises}

## דוגמאות מהמטפל:
{self._format_examples()}
{prohibitions_block}{custom_rules_block}
**חשוב:** דבר תמיד בשם המטפל, לא בשם עצמך. למשל:
"היי [שם מטופל], זה {name}. רציתי לשמוע איך הלך..."
"""
            base_prompt += custom_prompt

        # Add operational rules
        base_prompt += """

## 🚨 כללי פעולה נוקשים:

### עם המטפל:
✅ תמיד הצע אפשרויות (אל תכתיב)
✅ שאל שאלות הבהרה
✅ הצג דוגמאות לפני אישור
✅ עדכן על כל פעולה
❌ לעולם אל תשלח דבר למטופל ללא אישור מפורש
❌ לעולם אל תשנה סיכומים ללא אישור

### עם מטופל:
✅ דבר כמו המטפל (לא כמו עצמך)
✅ הודעות קצרות (2-4 משפטים)
✅ שאל שאלות פתוחות
✅ הצע תרגילים מעשיים
❌ לעולם אל תיתן אבחנות
❌ לעולם אל תציע תרופות/טיפולים
❌ לעולם אל תשתמש בז'רגון מקצועי מדי

## 🔧 פקודות מיוחדות:
/start - התחל היכרות וקבל הכרת מטפל
/summary - צור סיכום פגישה מהקלטה
/client [שם] - פתח פרופיל מטופל
/message [שם] - צור הודעה למטופל
/templates - נהל תבניות אישיות
/status - מצב כל המטופלים
/privacy - הגדרות פרטיות ואבטחה

דבר תמיד בעברית מקצועית שוטפת.
שמור על פשטות - מטפלים לא טכניים.
שאל שאלות הבהרה כשצריך.
תמיד הצע אישור לפני פעולה.
"""

        return base_prompt

    def _format_examples(self) -> str:
        """Format example summaries and messages from therapist profile"""
        if not self.profile:
            return ""

        examples = ""

        # Add example summaries
        if self.profile.example_summaries:
            examples += "\n### דוגמאות סיכומים:\n"
            for i, summary in enumerate(self.profile.example_summaries[:3], 1):
                examples += f"\n**דוגמה {i}:**\n{summary}\n"

        # Add example messages
        if self.profile.example_messages:
            examples += "\n### דוגמאות הודעות למטופלים:\n"
            for i, message in enumerate(self.profile.example_messages[:3], 1):
                examples += f"\n**דוגמה {i}:**\n{message}\n"

        return examples

    async def generate_response(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Generate a response to a message

        Args:
            message: The input message from therapist
            context: Optional context (patient info, session data, etc.)

        Returns:
            Generated response in therapist's style
        """
        if self.provider is None:
            raise RuntimeError(
                "AI provider not initialised. Set a valid ANTHROPIC_API_KEY in .env."
            )

        try:
            # Build the full prompt with context
            full_prompt = message
            if context:
                full_prompt = f"הקשר: {context}\n\n{message}"

            response = await self._generate(full_prompt, FlowType.CHAT)

            therapist_email = (
                self.profile.therapist.email if self.profile else "Unknown"
            )
            logger.info(f"Generated response for therapist: {therapist_email}")
            return response

        except Exception as e:
            logger.error(f"Error generating response: {str(e)}")
            raise

    async def generate_session_summary(
        self,
        notes: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> SessionSummaryResult:
        """
        Generate a structured session summary from therapist notes.

        Returns a SessionSummaryResult with parsed fields.
        """
        if self.provider is None:
            raise RuntimeError(
                "AI provider not initialised. Set a valid ANTHROPIC_API_KEY in .env."
            )

        summary_prompt = f"""\
צור סיכום פגישה מובנה מהרשימות הבאות. החזר תשובה **אך ורק** כ-JSON תקין (ללא markdown, ללא ```).

**רשימות המטפל:**
{notes}

החזר JSON בדיוק במבנה הבא (כל הערכים בעברית):
{{
  "topics_discussed": ["נושא 1", "נושא 2"],
  "interventions_used": ["התערבות 1", "התערבות 2"],
  "patient_progress": "תיאור התקדמות המטופל",
  "homework_assigned": ["משימה 1", "משימה 2"],
  "next_session_plan": "תוכנית לפגישה הבאה",
  "mood_observed": "מצב רוח נצפה",
  "risk_assessment": "הערכת סיכון - ציין 'ללא סיכון מיוחד' אם לא זוהה סיכון",
  "full_summary": "סיכום מלא בפסקה אחת-שתיים בסגנון הכתיבה של המטפל"
}}

כללים:
- אל תמציא מידע שלא מופיע ברשימות.
- אם משהו לא ברור מהרשימות, כתוב "לא צוין".
- הסיכום המלא (full_summary) צריך להיות בסגנון הכתיבה של המטפל.
- אל תיתן אבחנות. אל תציע טיפולים. רק תעד את מה שהמטפל כתב.
"""

        ctx_str = ""
        if context:
            ctx_str = f"הקשר: מספר פגישה {context.get('session_number', '?')}\n\n"

        full_prompt = ctx_str + summary_prompt

        try:
            raw = await self._generate(full_prompt, FlowType.SESSION_SUMMARY)
            return self._parse_summary_json(raw)

        except Exception as e:
            logger.error(f"Error generating session summary: {e}")
            raise

    def _parse_summary_json(self, raw: str) -> SessionSummaryResult:
        """Parse AI response into SessionSummaryResult, with fallback."""
        # Strip markdown fences if AI included them despite instructions
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[: cleaned.rfind("```")]
        cleaned = cleaned.strip()

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            logger.warning("AI returned non-JSON summary, using full text as fallback")
            return SessionSummaryResult(
                topics_discussed=[],
                interventions_used=[],
                patient_progress="",
                homework_assigned=[],
                next_session_plan="",
                mood_observed="",
                risk_assessment="",
                full_summary=raw,
            )

        return SessionSummaryResult(
            topics_discussed=data.get("topics_discussed", []),
            interventions_used=data.get("interventions_used", []),
            patient_progress=data.get("patient_progress", ""),
            homework_assigned=data.get("homework_assigned", []),
            next_session_plan=data.get("next_session_plan", ""),
            mood_observed=data.get("mood_observed", ""),
            risk_assessment=data.get("risk_assessment", ""),
            full_summary=data.get("full_summary", ""),
        )

    async def generate_patient_insight_summary(
        self,
        patient_name: str,
        summaries_timeline: List[Dict[str, Any]],
    ) -> PatientInsightResult:
        """
        Generate a cross-session insight report for a patient.

        summaries_timeline: list of dicts with keys:
            session_date, session_number, full_summary, topics_discussed,
            patient_progress, risk_assessment
        """
        if self.provider is None:
            raise RuntimeError(
                "AI provider not initialised. Set a valid ANTHROPIC_API_KEY in .env."
            )

        # Build timeline text
        timeline_parts = []
        for s in summaries_timeline:
            date_str = str(s.get("session_date", "?"))
            num = s.get("session_number", "?")
            topics = ", ".join(s.get("topics_discussed", []) or [])
            progress = s.get("patient_progress", "")
            risk = s.get("risk_assessment", "")
            summary_text = s.get("full_summary", "")
            timeline_parts.append(
                f"--- פגישה #{num} ({date_str}) ---\n"
                f"נושאים: {topics}\n"
                f"סיכום: {summary_text}\n"
                f"התקדמות: {progress}\n"
                f"סיכון: {risk}"
            )

        timeline = "\n\n".join(timeline_parts)

        prompt = f"""\
אתה מסייע לחשיבה הקלינית של המטפל. אתה לא מאבחן, לא ממליץ על טיפול תרופתי, ולא מחליף שיקול דעת קליני.

להלן ציר הזמן של סיכומי הפגישות המאושרים עבור המטופל "{patient_name}":

{timeline}

על סמך ציר הזמן, צור דו"ח תובנות **למטפל בלבד** (לא למטופל).

החזר תשובה **אך ורק** כ-JSON תקין (ללא markdown, ללא ```):
{{
  "overview": "סקירה כללית של מהלך הטיפול ב-3-5 משפטים",
  "progress": "תיאור ההתקדמות לאורך זמן — מה השתנה מפגישה ראשונה לאחרונה",
  "patterns": ["דפוס 1", "דפוס 2", "..."],
  "risks": ["נקודת סיכון 1 למעקב", "..."],
  "suggestions_for_next_sessions": ["רעיון 1 לפגישות הבאות", "רעיון 2", "..."]
}}

כללים:
- בסס את התובנות **רק** על מידע שמופיע בסיכומים. אל תמציא.
- אם אין מספיק מידע לשדה מסוים, כתוב ["לא ניתן לקבוע מהנתונים הקיימים"].
- כתוב בעברית מקצועית שוטפת.
- אל תיתן אבחנות. אל תציע תרופות.
"""

        try:
            raw = await self._generate(prompt, FlowType.PATIENT_INSIGHT)
            return self._parse_insight_json(raw)

        except Exception as e:
            logger.error(f"Error generating patient insight summary: {e}")
            raise

    def _parse_insight_json(self, raw: str) -> PatientInsightResult:
        """Parse AI response into PatientInsightResult, with fallback."""
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[: cleaned.rfind("```")]
        cleaned = cleaned.strip()

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            logger.warning("AI returned non-JSON insight, using full text as fallback")
            return PatientInsightResult(
                overview=raw,
                progress="",
                patterns=[],
                risks=[],
                suggestions_for_next_sessions=[],
            )

        return PatientInsightResult(
            overview=data.get("overview", ""),
            progress=data.get("progress", ""),
            patterns=data.get("patterns", []),
            risks=data.get("risks", []),
            suggestions_for_next_sessions=data.get("suggestions_for_next_sessions", []),
        )

    async def generate_session_prep_brief(
        self,
        patient_name: str,
        session_date: str,
        session_number: Optional[int],
        summaries_timeline: List[Dict[str, Any]],
        open_tasks: List[Dict[str, Any]],
    ) -> SessionPrepBriefResult:
        """
        Generate a 4-section clinical prep brief using approved history + open tasks.

        summaries_timeline: all approved summaries ordered oldest → newest (most recent last).
        open_tasks: all incomplete exercises/tasks for this patient.
        """
        if self.provider is None:
            raise RuntimeError(
                "AI provider not initialised. Set a valid ANTHROPIC_API_KEY in .env."
            )

        has_summaries = bool(summaries_timeline)

        # ── Build approved-summaries context ──────────────────────────────────
        if has_summaries:
            history_parts = []
            for s in summaries_timeline:
                date_str = str(s.get("session_date", "?"))
                num = s.get("session_number", "?")
                full_summary = s.get("full_summary", "") or ""
                topics = ", ".join(s.get("topics_discussed", []) or [])
                progress = s.get("patient_progress", "") or ""
                homework = ", ".join(s.get("homework_assigned", []) or [])
                risk = s.get("risk_assessment", "") or ""
                next_plan = s.get("next_session_plan", "") or ""
                summary_block = (
                    f'סיכום (ערוך ע"י המטפל):\n{full_summary}\n' if full_summary else ""
                )
                history_parts.append(
                    f"--- פגישה #{num} ({date_str}) ---\n"
                    f"{summary_block}"
                    f"נושאים: {topics}\n"
                    f"התקדמות: {progress}\n"
                    f"משימות בית: {homework}\n"
                    f"תוכנית להמשך: {next_plan}\n"
                    f"סיכון: {risk}"
                )
            summaries_context = (
                'היסטוריית הפגישות (מאושרת ע"י המטפל, מהישנה לחדשה):\n\n'
                + "\n\n".join(history_parts)
            )
        else:
            summaries_context = "(אין סיכומים מאושרים עדיין)"

        # ── Build open tasks context ──────────────────────────────────────────
        if open_tasks:
            tasks_lines = "\n".join(
                f"- {t.get('description', '')} (נוצר: {str(t.get('created_at', '?'))[:10]})"
                for t in open_tasks
            )
            tasks_context = f"משימות פתוחות (לא הושלמו):\n{tasks_lines}"
        else:
            tasks_context = "משימות פתוחות: אין"

        session_num_str = f"#{session_number}" if session_number else ""

        if not has_summaries:
            no_history_note = (
                "\n⚠️ CRITICAL — NO HISTORY EXISTS FOR THIS PATIENT.\n"
                "There are ZERO approved session summaries in the database.\n"
                "You MUST NOT invent, fabricate, or guess any past sessions, topics, progress, "
                "homework, or clinical details. Any invented history is a serious clinical error.\n"
                "history_summary and last_session MUST state clearly that there is no history yet "
                "and that this appears to be the first documented session. "
                "focus_for_today should contain only general first-session guidance.\n"
            )
        else:
            no_history_note = ""

        prompt = f"""\
אתה עוזר קליני אישי של המטפל. תפקידך לסכם את ההיסטוריה הקלינית ולהכין את המטפל לפגישה הקרובה.
אתה לא מאבחן ולא מקבל החלטות טיפוליות — אתה מארגן את המידע הקיים בצורה ברורה ופרקטית.
{no_history_note}
הפגישה הקרובה: מטופל "{patient_name}", פגישה {session_num_str}, בתאריך {session_date}.

{summaries_context}

{tasks_context}

החזר תשובה **אך ורק** כ-JSON תקין (ללא markdown, ללא ```):
{{
  "history_summary": ["תמה/דפוס מרכזי מכל ההיסטוריה", "מגמת ההתקדמות הכללית", "..."],
  "last_session": ["מה עלה בפגישה האחרונה", "מה הוסכם / נותר פתוח", "..."],
  "tasks_to_check": ["תיאור משימה לבדיקה", "..."],
  "focus_for_today": ["הצעה קונקרטית 1 למה לשים דגש", "הצעה 2", "..."],
  "watch_out_for": ["סיכון/רגישות אם קיים", "..."]
}}

כללים:
- history_summary: 2–3 פריטים — תמות ודפוסים חוצי-פגישות, לא חזרה על כל פגישה.
  אם אין היסטוריה מאושרת — כתוב ["אין סיכומים מאושרים עדיין — זו ככל הנראה הפגישה הראשונה"].
- last_session: 2–3 פריטים — ספציפי לפגישה האחרונה בלבד.
  אם אין היסטוריה — כתוב ["אין פגישות קודמות מתועדות"].
- tasks_to_check: אם אין משימות פתוחות — ["אין משימות פתוחות"]. אחרת — מנה אותן תמציתית.
- focus_for_today: 2–3 הצעות פרקטיות — מבוסס אך ורק על מידע שנמסר לך. אם אין היסטוריה — הצע גישה לפגישה ראשונה.
- watch_out_for: רק אם יש סיכון/רגישות ממשיים בנתונים. אחרת — [].
- אסור בהחלט להמציא פגישות, פרטים קליניים, משימות, נושאים, או כל מידע שלא מופיע במפורש בנתונים שנמסרו.
- כתוב בעברית מקצועית שוטפת. תמציתי — מטפל עסוק קורא את זה ב-30 שניות.
"""

        # Use low temperature for prep brief — factual retrieval, not creative generation.
        # For no-history patients this is critical to prevent hallucination.
        prep_temperature = 0.1

        try:
            raw = await self._generate(prompt, FlowType.SESSION_PREP, temperature=prep_temperature)
            return self._parse_prep_brief_json(raw)

        except Exception as e:
            logger.error(f"Error generating session prep brief: {e}")
            raise

    def _parse_prep_brief_json(self, raw: str) -> SessionPrepBriefResult:
        """Parse AI response into SessionPrepBriefResult, with fallback."""
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[: cleaned.rfind("```")]
        cleaned = cleaned.strip()

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            logger.warning("AI returned non-JSON prep brief, wrapping as fallback")
            return SessionPrepBriefResult(
                history_summary=[raw],
                last_session=[],
                tasks_to_check=[],
                focus_for_today=[],
                watch_out_for=[],
            )

        return SessionPrepBriefResult(
            history_summary=data.get("history_summary", []),
            last_session=data.get("last_session", []),
            tasks_to_check=data.get("tasks_to_check", []),
            focus_for_today=data.get("focus_for_today", []),
            watch_out_for=data.get("watch_out_for", []),
        )

    async def generate_deep_summary(
        self,
        patient_name: str,
        approved_summaries: List[Dict[str, Any]],
        all_tasks: List[Dict[str, Any]],
        metrics: Dict[str, Any],
        therapist_locale: str = "he",
    ) -> DeepSummaryResult:
        """
        Generate a comprehensive deep treatment summary.

        JSON keys are always English; text values are written in therapist_locale.
        approved_summaries: all approved summaries ordered oldest → newest.
        all_tasks: open + completed tasks with status/dates.
        metrics: {total_sessions, first_session_date, last_session_date, long_gaps}.
        therapist_locale: ISO language code, e.g. "he" or "en".
        """
        if self.provider is None:
            raise RuntimeError(
                "AI provider not initialised. Set a valid ANTHROPIC_API_KEY in .env."
            )

        locale_names: Dict[str, str] = {"he": "Hebrew", "en": "English"}
        output_language = locale_names.get(therapist_locale, therapist_locale)

        # ── Summaries context ─────────────────────────────────────────────────
        if approved_summaries:
            summary_parts = []
            for s in approved_summaries:
                date_str = str(s.get("session_date", "?"))
                num = s.get("session_number", "?")
                full_summary = s.get("full_summary", "") or ""
                topics = ", ".join(s.get("topics_discussed", []) or [])
                progress = s.get("patient_progress", "") or ""
                homework = ", ".join(s.get("homework_assigned", []) or [])
                risk = s.get("risk_assessment", "") or ""
                summary_parts.append(
                    f"--- Session #{num} ({date_str}) ---\n"
                    f"Summary: {full_summary}\n"
                    f"Topics: {topics}\n"
                    f"Progress: {progress}\n"
                    f"Homework: {homework}\n"
                    f"Risk: {risk}"
                )
            summaries_context = (
                "Approved session summaries (oldest to newest):\n\n"
                + "\n\n".join(summary_parts)
            )
        else:
            summaries_context = "(No approved session summaries yet)"

        # ── Tasks context ─────────────────────────────────────────────────────
        open_tasks = [t for t in all_tasks if not t.get("completed", False)]
        done_tasks = [t for t in all_tasks if t.get("completed", False)]
        tasks_lines = []
        for t in open_tasks:
            tasks_lines.append(
                f"  [OPEN] {t.get('description', '?')} "
                f"(assigned: {str(t.get('created_at', '?'))[:10]})"
            )
        for t in done_tasks:
            done_date = str(t.get("completed_at", "?"))[:10] if t.get("completed_at") else "?"
            tasks_lines.append(
                f"  [DONE] {t.get('description', '?')} (completed: {done_date})"
            )
        tasks_context = "Tasks:\n" + (
            "\n".join(tasks_lines) if tasks_lines else "  (no tasks recorded)"
        )

        # ── Metrics context ───────────────────────────────────────────────────
        total = metrics.get("total_sessions", "?")
        first_date = str(metrics.get("first_session_date", "?"))
        last_date = str(metrics.get("last_session_date", "?"))
        gaps = metrics.get("long_gaps", [])
        gaps_note = ""
        if gaps:
            gaps_note = "\nLong breaks (>30 days): " + "; ".join(
                f"{g['from']} to {g['to']} ({g['days']} days)" for g in gaps
            )
        metrics_context = (
            f"Total sessions: {total}\n"
            f"First session: {first_date}\n"
            f"Last session: {last_date}" + gaps_note
        )

        approved_count = len(approved_summaries)
        task_count = len(all_tasks)

        # ── Strict data-constraint block (always included) ────────────────────
        data_constraints = (
            f"\nSTRICT DATA CONSTRAINTS — YOU MUST OBEY THESE EXACTLY:\n"
            f"- The data above contains exactly {approved_count} approved session summary(ies).\n"
            f"  Do NOT reference, invent, or imply any sessions beyond those shown.\n"
            f"- The task list above contains exactly {task_count} task(s).\n"
            f"  Do NOT mention any tasks, homework, or exercises not explicitly listed in the task list.\n"
        )
        if approved_count == 1:
            data_constraints += (
                "- There is only ONE session in the data. "
                "Do NOT use plural 'sessions', 'previous sessions', 'across sessions', "
                "'over multiple sessions', or any phrase implying more than one session.\n"
            )
        if approved_count == 0:
            data_constraints += (
                "- There are NO approved sessions. "
                "Every section must state that no session data is available.\n"
            )
        if task_count == 0:
            data_constraints += (
                "- There are NO tasks. "
                "The goals_and_tasks field must describe only the therapeutic focus areas visible "
                "in the session text. Do NOT invent or suggest tasks.\n"
            )

        prompt = f"""\
You are a clinical reflection assistant for the therapist. You synthesize and reflect — you do not diagnose, prescribe, or invent information.
{data_constraints}
Patient: "{patient_name}"

{summaries_context}

{tasks_context}

{metrics_context}
(Note: "Total sessions" above counts all scheduled sessions; only the {approved_count} approved \
summaries shown above are available as data — do not infer content from sessions without summaries.)

LANGUAGE REQUIREMENT: All text values MUST be written in {output_language}. \
JSON field names must remain exactly in English as shown below.

Return ONLY valid JSON (no markdown fences, no text outside JSON):
{{
  "overall_treatment_picture": "2-3 paragraphs summarising the main themes visible in the approved session summaries. If there is only one session, summarise that single session without implying prior history.",
  "timeline_highlights": ["key observation or moment from the data — only from sessions listed above"],
  "goals_and_tasks": "Describe the therapeutic focus areas visible in the session text. List ONLY the tasks that appear in the task list above — if none, state that no tasks have been defined.",
  "measurable_progress": "Concrete examples of change visible in the session summaries. If only one session exists, describe what was observed in that session without comparing to non-existent prior sessions.",
  "directions_for_next_phase": "2-3 suggested directions for the next phase, based solely on the data above."
}}

Rules:
- Base everything ONLY on the data provided above. Do NOT invent sessions, tasks, or details.
- timeline_highlights: 1-3 items when there is only 1 session; up to 6 items for 5+ sessions.
- No clinical diagnoses, no medication suggestions.
- All text values in {output_language}. JSON keys must be English.
"""

        try:
            raw = await self._generate(prompt, FlowType.DEEP_SUMMARY)
            return self._parse_deep_summary_json(raw)
        except Exception as e:
            logger.error(f"Error generating deep summary: {e}")
            raise

    def _parse_deep_summary_json(self, raw: str) -> DeepSummaryResult:
        """Parse AI response into DeepSummaryResult, with fallback."""
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[: cleaned.rfind("```")]
        cleaned = cleaned.strip()

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            logger.warning("AI returned non-JSON deep summary, wrapping as fallback")
            return DeepSummaryResult(
                overall_treatment_picture=raw,
                timeline_highlights=[],
                goals_and_tasks="",
                measurable_progress="",
                directions_for_next_phase="",
            )

        return DeepSummaryResult(
            overall_treatment_picture=data.get("overall_treatment_picture", ""),
            timeline_highlights=data.get("timeline_highlights", []),
            goals_and_tasks=data.get("goals_and_tasks", ""),
            measurable_progress=data.get("measurable_progress", ""),
            directions_for_next_phase=data.get("directions_for_next_phase", ""),
        )

    async def generate_treatment_plan_preview(
        self,
        patient_name: str,
        approved_summaries: List[Dict[str, Any]],
        all_tasks: List[Dict[str, Any]],
        therapist_locale: str = "he",
    ) -> TreatmentPlanResult:
        """
        Generate a treatment plan preview (goals, focus areas, interventions) from history.

        JSON keys are always English; text values are written in therapist_locale.
        """
        if self.provider is None:
            raise RuntimeError(
                "AI provider not initialised. Set a valid ANTHROPIC_API_KEY in .env."
            )

        locale_names: Dict[str, str] = {"he": "Hebrew", "en": "English"}
        output_language = locale_names.get(therapist_locale, therapist_locale)

        # ── Summaries context ─────────────────────────────────────────────────
        if approved_summaries:
            summary_parts = []
            for s in approved_summaries:
                date_str = str(s.get("session_date", "?"))
                num = s.get("session_number", "?")
                full_summary = s.get("full_summary", "") or ""
                topics = ", ".join(s.get("topics_discussed", []) or [])
                progress = s.get("patient_progress", "") or ""
                homework = ", ".join(s.get("homework_assigned", []) or [])
                summary_parts.append(
                    f"--- Session #{num} ({date_str}) ---\n"
                    f"Summary: {full_summary}\n"
                    f"Topics: {topics}\n"
                    f"Progress: {progress}\n"
                    f"Homework: {homework}"
                )
            summaries_context = (
                "Approved session summaries (chronological):\n\n"
                + "\n\n".join(summary_parts)
            )
        else:
            summaries_context = "(No approved session summaries yet)"

        # ── Tasks context ─────────────────────────────────────────────────────
        open_tasks = [t for t in all_tasks if not t.get("completed", False)]
        done_tasks = [t for t in all_tasks if t.get("completed", False)]
        tasks_lines = []
        for t in open_tasks:
            tasks_lines.append(f"  [OPEN] {t.get('description', '?')}")
        for t in done_tasks:
            tasks_lines.append(f"  [DONE] {t.get('description', '?')}")
        tasks_context = "Tasks:\n" + (
            "\n".join(tasks_lines) if tasks_lines else "  (none)"
        )

        limited_data_note = ""
        if len(approved_summaries) < 2:
            limited_data_note = (
                "\nNOTE: Very few approved summaries — infer conservatively "
                "and note the limitation in goal descriptions.\n"
            )

        prompt = f"""\
You are a clinical planning assistant for the therapist. You draft a treatment plan \
from the session history — you do not diagnose or invent information not present in the data.
{limited_data_note}
Patient: "{patient_name}"

{summaries_context}

{tasks_context}

LANGUAGE REQUIREMENT: All text values MUST be written in {output_language}. \
JSON keys must remain exactly in English as shown.

Return ONLY valid JSON (no markdown, no text outside JSON):
{{
  "goals": [
    {{"id": "g1", "title": "Short goal title", "description": "1-2 sentences about this goal, why it matters, how it appears in the session data."}},
    {{"id": "g2", "title": "...", "description": "..."}}
  ],
  "focus_areas": ["main theme/domain 1", "main theme/domain 2", "..."],
  "suggested_interventions": ["intervention type or homework idea 1 (must be grounded in existing data)", "..."]
}}

Rules:
- goals: 3-5 items. IDs must be "g1", "g2", etc. Infer only from the history.
- focus_areas: 3-6 thematic domains to work on.
- suggested_interventions: based ONLY on interventions/tasks already in the data, not generic ideas.
- No clinical diagnoses, no medication suggestions.
- All text values in {output_language}. JSON keys must be English.
"""

        try:
            raw = await self._generate(prompt, FlowType.TREATMENT_PLAN)
            return self._parse_treatment_plan_json(raw)
        except Exception as e:
            logger.error(f"Error generating treatment plan preview: {e}")
            raise

    def _parse_treatment_plan_json(self, raw: str) -> TreatmentPlanResult:
        """Parse AI response into TreatmentPlanResult, with fallback."""
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[: cleaned.rfind("```")]
        cleaned = cleaned.strip()

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            logger.warning("AI returned non-JSON treatment plan, using empty fallback")
            return TreatmentPlanResult(goals=[], focus_areas=[], suggested_interventions=[])

        goals_raw = data.get("goals", [])
        goals = [
            TreatmentGoal(
                id=str(g.get("id", f"g{i + 1}")),
                title=g.get("title", ""),
                description=g.get("description", ""),
            )
            for i, g in enumerate(goals_raw)
            if isinstance(g, dict)
        ]

        return TreatmentPlanResult(
            goals=goals,
            focus_areas=data.get("focus_areas", []),
            suggested_interventions=data.get("suggested_interventions", []),
        )

    async def generate_today_insights(
        self,
        patients_context: List[Dict[str, Any]],
        therapist_locale: str = "he",
    ) -> TodayInsightsResult:
        """
        Generate smart per-patient reminders for today's sessions.

        patients_context: list of dicts with keys:
            patient_id, patient_name, session_number, approved_summaries, open_tasks
        therapist_locale: ISO language code ("he" or "en").

        Makes ONE AI call for all patients combined.
        Returns TodayInsightsResult with one item per patient.
        """
        if self.provider is None:
            raise RuntimeError(
                "AI provider not initialised. Set a valid ANTHROPIC_API_KEY in .env."
            )

        if not patients_context:
            return TodayInsightsResult(insights=[])

        locale_names: Dict[str, str] = {"he": "Hebrew", "en": "English"}
        output_language = locale_names.get(therapist_locale, therapist_locale)

        # Build compact per-patient context block
        patient_blocks = []
        for p in patients_context:
            pid = p.get("patient_id", "?")
            name = p.get("patient_name", "?")
            session_num = p.get("session_number")
            session_label = f"Session #{session_num}" if session_num else "Session"
            summaries = p.get("approved_summaries", [])
            tasks = p.get("open_tasks", [])

            block_lines = [f"[patient_id={pid}] {name} — {session_label} today"]

            if summaries:
                for s in summaries:
                    date_str = str(s.get("session_date", "?"))
                    num = s.get("session_number", "?")
                    full = (s.get("full_summary", "") or "")[:300]
                    topics = ", ".join(s.get("topics_discussed", []) or [])
                    progress = s.get("patient_progress", "") or ""
                    line = f"  Session #{num} ({date_str}): {full}"
                    if topics:
                        line += f" | Topics: {topics}"
                    if progress:
                        line += f" | Progress: {progress}"
                    block_lines.append(line)
            else:
                block_lines.append("  (no approved summaries yet)")

            if tasks:
                task_list = "; ".join(t.get("description", "") for t in tasks[:5])
                block_lines.append(f"  Open tasks: {task_list}")
            else:
                block_lines.append("  Open tasks: none")

            patient_blocks.append("\n".join(block_lines))

        context_str = "\n\n".join(patient_blocks)

        prompt = f"""\
You are a clinical preparation assistant. The therapist has sessions scheduled today. \
For each patient listed, write one concise smart reminder (title + body) to help the \
therapist enter the session prepared.

LANGUAGE REQUIREMENT: All text values MUST be written in {output_language}. \
JSON keys must remain exactly in English as shown.

Return ONLY valid JSON (no markdown fences, no text outside JSON):
{{
  "insights": [
    {{"patient_id": <integer>, "title": "concise title — max 8 words", "body": "1-2 practical sentences based only on the data below"}}
  ]
}}

Rules:
- Include EVERY patient listed below (one item per patient).
- title: max 8 words — the single most important thing to remember.
- body: 1-2 short sentences. Practical and specific. Based ONLY on the session data provided.
- If there is no prior data for a patient: title = "First session" (in {output_language}), body = encourage an open intake approach.
- No clinical diagnoses. No medication suggestions.
- All text values in {output_language}. JSON keys must stay in English.

Today's patients:
{context_str}
"""

        try:
            raw = await self._generate(prompt, FlowType.PATIENT_INSIGHT)
            return self._parse_today_insights_json(raw)
        except Exception as e:
            logger.error(f"Error generating today insights: {e}")
            raise

    def _parse_today_insights_json(self, raw: str) -> TodayInsightsResult:
        """Parse AI response into TodayInsightsResult, with fallback."""
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[: cleaned.rfind("```")]
        cleaned = cleaned.strip()

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            logger.warning("AI returned non-JSON today insights, returning empty")
            return TodayInsightsResult(insights=[])

        items = []
        for item in data.get("insights", []):
            if isinstance(item, dict) and "patient_id" in item:
                try:
                    items.append(
                        TodayInsightItem(
                            patient_id=int(item["patient_id"]),
                            title=item.get("title", ""),
                            body=item.get("body", ""),
                        )
                    )
                except (ValueError, TypeError):
                    pass

        return TodayInsightsResult(insights=items)

    async def _generate(
        self,
        prompt: str,
        flow_type: FlowType,
        temperature: Optional[float] = None,
    ) -> str:
        """
        Core generation method. Routes to the correct model via ModelRouter,
        calls the provider, stores GenerationResult in self._last_result.
        Callers read self._last_result to capture telemetry for ai_generation_log.
        """
        if self.provider is None:
            raise RuntimeError(
                "AI provider not initialised. Set a valid ANTHROPIC_API_KEY in .env."
            )
        model_id, route_reason = self.router.resolve(flow_type)
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": prompt},
        ]
        result = await self.provider.generate(
            messages,
            model=model_id,
            flow_type=flow_type,
            temperature=temperature if temperature is not None else settings.TEMPERATURE,
            max_tokens=settings.MAX_TOKENS,
            route_reason=route_reason,
        )
        self._last_result = result
        return result.content

    @property
    def ai_provider(self) -> str:
        """Provider identifier string for API responses."""
        if self.provider is None:
            return "none"
        return type(self.provider).__name__.replace("Provider", "").lower()

    async def handle_command(self, command: str, args: str = "") -> str:
        """
        Handle special commands like /start, /summary, etc.

        Args:
            command: The command (without /)
            args: Optional arguments

        Returns:
            Command response
        """
        command_handlers = {
            "start": self._handle_start,
            "summary": self._handle_summary,
            "client": self._handle_client,
            "message": self._handle_message,
            "templates": self._handle_templates,
            "status": self._handle_status,
            "privacy": self._handle_privacy,
        }

        handler = command_handlers.get(command)
        if handler:
            return await handler(args)
        else:
            return f"פקודה לא מוכרת: /{command}"

    async def _handle_start(self, args: str) -> str:
        """Handle /start command - onboarding"""
        return """
שלום! אני **TherapyCompanion.AI** - הסוכן האישי שלך.
אני כאן כדי לחסוך לך זמן ולשמור על קשר עם המטופלים שלך בין הפגישות.

כדי להתחיל, בואו נכיר:
1. ספר/י לי על הגישה הטיפולית שלך (CBT, פסיכודינמית וכו')
2. איך את/ה בדרך כלל כותב/ת סיכומים?
3. מה הטון המועדף שלך להודעות למטופלים?
4. יש מטופלים ספציפיים שתרצה/י שאעקוב אחריהם?

אחרי זה אני יכול להתחיל לעזור לך מיד :)
"""

    async def _handle_summary(self, args: str) -> str:
        """Handle /summary command - create session summary"""
        return "בואו ניצור סיכום פגישה. אפשר להקליט, להקליד, או לספק טקסט."

    async def _handle_client(self, args: str) -> str:
        """Handle /client command - open patient profile"""
        if not args:
            return "אנא ציין/י שם מטופל. שימוש: /client [שם]"
        return f"פותח פרופיל מטופל: {args}"

    async def _handle_message(self, args: str) -> str:
        """Handle /message command - create message for patient"""
        if not args:
            return "אנא ציין/י שם מטופל. שימוש: /message [שם]"
        return f"יוצר הודעה למטופל: {args}"

    async def _handle_templates(self, args: str) -> str:
        """Handle /templates command - manage templates"""
        return "ניהול תבניות אישיות"

    async def _handle_status(self, args: str) -> str:
        """Handle /status command - show all patients status"""
        return "מצב כל המטופלים"

    async def _handle_privacy(self, args: str) -> str:
        """Handle /privacy command - privacy settings"""
        return "הגדרות פרטיות ואבטחה"
