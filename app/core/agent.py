"""
Core AI Agent - TherapyCompanion.AI
This is the heart of the system - the personalized AI therapist assistant
"""

from typing import Optional, Dict, Any, List
import json
from openai import AsyncOpenAI
from app.core.config import settings
from app.models.therapist import TherapistProfile
from loguru import logger


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
    """Structured result from AI session preparation brief."""

    def __init__(
        self,
        quick_overview: str,
        recent_progress: str,
        key_points_to_revisit: List[str],
        watch_out_for: List[str],
        ideas_for_this_session: List[str],
    ):
        self.quick_overview = quick_overview
        self.recent_progress = recent_progress
        self.key_points_to_revisit = key_points_to_revisit
        self.watch_out_for = watch_out_for
        self.ideas_for_this_session = ideas_for_this_session


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

    def __init__(self, therapist_profile: Optional[TherapistProfile] = None):
        """Initialize the agent with optional therapist profile"""
        from app.core.config import is_placeholder_key

        self.profile = therapist_profile
        self.client = None

        # Initialize OpenAI client only if a real key is available
        if not is_placeholder_key(settings.OPENAI_API_KEY):
            self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        else:
            logger.warning("OpenAI client not initialized: missing or placeholder API key")

        self.system_prompt = self._build_system_prompt()

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
        if self.client is None:
            raise RuntimeError(
                "AI client not initialized. Set a valid OPENAI_API_KEY in .env."
            )

        try:
            # Build the full prompt with context
            full_prompt = message
            if context:
                full_prompt = f"הקשר: {context}\n\n{message}"

            response = await self._generate_openai(full_prompt)

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
        if self.client is None:
            raise RuntimeError(
                "AI client not initialized. Set a valid OPENAI_API_KEY in .env."
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
            raw = await self._generate_openai(full_prompt)
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
        if self.client is None:
            raise RuntimeError(
                "AI client not initialized. Set a valid OPENAI_API_KEY in .env."
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
            raw = await self._generate_openai(prompt)
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
    ) -> SessionPrepBriefResult:
        """
        Generate a concise prep brief for an upcoming session.

        summaries_timeline: last N approved summaries (most recent last).
        """
        if self.client is None:
            raise RuntimeError(
                "AI client not initialized. Set a valid OPENAI_API_KEY in .env."
            )

        timeline_parts = []
        for s in summaries_timeline:
            date_str = str(s.get("session_date", "?"))
            num = s.get("session_number", "?")
            # Meeting prep must use the therapist-edited summary (full_summary),
            # not structured fields alone — the therapist may have rewritten them.
            full_summary = s.get("full_summary", "") or ""
            topics = ", ".join(s.get("topics_discussed", []) or [])
            progress = s.get("patient_progress", "")
            homework = ", ".join(s.get("homework_assigned", []) or [])
            risk = s.get("risk_assessment", "")
            next_plan = s.get("next_session_plan", "")
            summary_block = f"סיכום מלא (ערוך ע\"י המטפל):\n{full_summary}\n" if full_summary else ""
            timeline_parts.append(
                f"--- פגישה #{num} ({date_str}) ---\n"
                f"{summary_block}"
                f"נושאים: {topics}\n"
                f"התקדמות: {progress}\n"
                f"משימות בית: {homework}\n"
                f"תוכנית להמשך: {next_plan}\n"
                f"סיכון: {risk}"
            )

        timeline = "\n\n".join(timeline_parts)

        session_num_str = f"#{session_number}" if session_number else ""
        prompt = f"""\
אתה מסייע לחשיבה הקלינית של המטפל. אתה לא מאבחן ולא מקבל החלטות טיפוליות בעצמך.
שמור על תמציתיות ופרקטיות — הכנה קצרה לפגישה הקרובה.

הפגישה הקרובה: מטופל "{patient_name}", פגישה {session_num_str}, בתאריך {session_date}.

להלן סיכומי הפגישות האחרונות (מאושרים):

{timeline}

צור תדריך הכנה קצר **למטפל בלבד**.

החזר תשובה **אך ורק** כ-JSON תקין (ללא markdown, ללא ```):
{{
  "quick_overview": "2-3 משפטים תמציתיים על מצב המטופל כרגע",
  "recent_progress": "מה השתנה בפגישות האחרונות",
  "key_points_to_revisit": ["נקודה 1 לחזור אליה", "..."],
  "watch_out_for": ["נושא רגיש / סיכון לשים לב", "..."],
  "ideas_for_this_session": ["רעיון קונקרטי 1", "רעיון 2", "..."]
}}

כללים:
- בסס רק על מידע מהסיכומים. אל תמציא.
- כתוב בעברית מקצועית שוטפת.
- שמור על קיצור — מטפל עסוק צריך לקרוא את זה ב-30 שניות.
"""

        try:
            raw = await self._generate_openai(prompt)
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
            logger.warning("AI returned non-JSON prep brief, using full text as fallback")
            return SessionPrepBriefResult(
                quick_overview=raw,
                recent_progress="",
                key_points_to_revisit=[],
                watch_out_for=[],
                ideas_for_this_session=[],
            )

        return SessionPrepBriefResult(
            quick_overview=data.get("quick_overview", ""),
            recent_progress=data.get("recent_progress", ""),
            key_points_to_revisit=data.get("key_points_to_revisit", []),
            watch_out_for=data.get("watch_out_for", []),
            ideas_for_this_session=data.get("ideas_for_this_session", []),
        )

    async def _generate_openai(self, prompt: str) -> str:
        """Generate response using OpenAI"""
        response = await self.client.chat.completions.create(
            model=settings.AI_MODEL,
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": prompt}
            ],
            temperature=settings.TEMPERATURE,
            max_tokens=settings.MAX_TOKENS,
        )
        return response.choices[0].message.content

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
