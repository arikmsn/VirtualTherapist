"""
Core AI Agent - TherapyCompanion.AI
This is the heart of the system - the personalized AI therapist assistant
"""

from typing import Optional, Dict, Any
from anthropic import Anthropic
import openai
from app.core.config import settings
from app.models.therapist import Therapist, TherapistProfile
from loguru import logger


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
        self.profile = therapist_profile
        self.ai_provider = settings.AI_PROVIDER

        # Initialize AI client based on provider
        if self.ai_provider == "anthropic":
            self.client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        elif self.ai_provider == "openai":
            openai.api_key = settings.OPENAI_API_KEY
            self.client = openai

        self.system_prompt = self._build_system_prompt()

    def _build_system_prompt(self) -> str:
        """
        Build the system prompt that defines the agent's personality
        This is customized based on the therapist's profile
        """

        base_prompt = """
אתה **TherapyCompanion.AI** - סוכן AI מתקדם המשמש כ"עוזר מטפל וירטואלי אישי" שממשיך את עבודת המטפל האנושי בין הפגישות.

## 🎯 תפקיד כפול:
1. **סייע למטפל בזרימת העבודה היומית** (תיעוד, סיכומים, משימות)
2. **המשך פעילות טיפולית** עם מטופלים בין פגישות (תמיכה, תרגילי המשך, בדיקות מצב)

## 🔒 אבטחה ופרטיות (קריטי!)
```
⚠️ חוקים ברזליים - לעולם אל תפר:
1. אף פעם לא לשלוח דבר למטופל ללא אישור מפורש של המטפל
2. כל השיחות מוצפנות מקצה לקצה (AES-256)
3. מלוא תיעוד ביקורת על כל פעולה
4. אפשרות מחיקה מלאה בכל עת (GDPR)
5. אין שיתוף נתונים עם צדדים שלישיים
```

## 🎭 התאמה אישית מלאה לכל מטפל:
אתה צריך לדבר בדיוק כמו המטפל - להשתמש במינוח שלו, בטון שלו, בסגנון הכתיבה שלו.

"""

        # Add therapist-specific customization if profile exists
        if self.profile:
            custom_prompt = f"""
## 👤 פרופיל המטפל שאתה מחקה:

**שם המטפל:** {self.profile.therapist.full_name if hasattr(self.profile, 'therapist') else 'לא צוין'}
**גישה טיפולית:** {self.profile.therapeutic_approach.value}
{f"**תיאור הגישה:** {self.profile.approach_description}" if self.profile.approach_description else ""}

**טון ושפה:**
- טון: {self.profile.tone if self.profile.tone else 'תומך וישיר'}
- אורך הודעות: {self.profile.message_length_preference if self.profile.message_length_preference else 'קצר ממוקד'}
- מינוח נפוץ: {', '.join(self.profile.common_terminology) if self.profile.common_terminology else 'לא צוין'}

**סגנון סיכומים:**
- תדירות מעקב: {self.profile.follow_up_frequency if self.profile.follow_up_frequency else 'שבועי'}
- תרגילים מועדפים: {', '.join(self.profile.preferred_exercises) if self.profile.preferred_exercises else 'לא צוין'}

## 📋 דוגמאות מהמטפל:
{self._format_examples()}

**חשוב:** דבר תמיד בשם המטפל, לא בשם עצמך. למשל:
"היי [שם מטופל], זה {self.profile.therapist.full_name if hasattr(self.profile, 'therapist') else '[שם המטפל]'}. רציתי לשמוע איך הלך..."
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

            logger.info(f"Generated response for therapist: {self.profile.therapist.email if self.profile else 'Unknown'}")
            return response

        except Exception as e:
            logger.error(f"Error generating response: {str(e)}")
            raise

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
