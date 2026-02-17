"""
Core AI Agent - TherapyCompanion.AI
This is the heart of the system - the personalized AI therapist assistant
"""

from typing import Optional, Dict, Any, List
import json
from anthropic import Anthropic
import openai
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
        self.ai_provider = settings.AI_PROVIDER
        self.client = None

        # Initialize AI client only if a real key is available
        if self.ai_provider == "anthropic":
            if not is_placeholder_key(settings.ANTHROPIC_API_KEY):
                self.client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)
            else:
                logger.warning("Anthropic client not initialized: missing or placeholder API key")
        elif self.ai_provider == "openai":
            if not is_placeholder_key(settings.OPENAI_API_KEY):
                openai.api_key = settings.OPENAI_API_KEY
                self.client = openai
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

            custom_prompt = f"""
## פרופיל המטפל שאתה מחקה:

**שם המטפל:** {name}
**גישה טיפולית:** {p.therapeutic_approach.value}
{approach_desc}

**טון ושפה:**
- טון: {tone}
- אורך הודעות: {msg_len}
- מינוח נפוץ: {terminology}

**סגנון סיכומים:**
- תדירות מעקב: {freq}
- תרגילים מועדפים: {exercises}

## דוגמאות מהמטפל:
{self._format_examples()}

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
                "AI client not initialized. "
                f"Set a valid API key in .env for AI_PROVIDER='{self.ai_provider}'."
            )

        try:
            # Build the full prompt with context
            full_prompt = message
            if context:
                full_prompt = f"הקשר: {context}\n\n{message}"

            # Generate response based on provider
            if self.ai_provider == "anthropic":
                response = await self._generate_anthropic(full_prompt)
            else:
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
                "AI client not initialized. "
                f"Set a valid API key in .env for AI_PROVIDER='{self.ai_provider}'."
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
            if self.ai_provider == "anthropic":
                raw = await self._generate_anthropic(full_prompt)
            else:
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

    async def _generate_anthropic(self, prompt: str) -> str:
        """Generate response using Anthropic Claude"""
        response = self.client.messages.create(
            model=settings.AI_MODEL,
            max_tokens=settings.MAX_TOKENS,
            temperature=settings.TEMPERATURE,
            system=self.system_prompt,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        return response.content[0].text

    async def _generate_openai(self, prompt: str) -> str:
        """Generate response using OpenAI"""
        response = await self.client.ChatCompletion.acreate(
            model=settings.AI_MODEL,
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": prompt}
            ],
            temperature=settings.TEMPERATURE,
            max_tokens=settings.MAX_TOKENS
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
