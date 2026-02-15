"""
Example usage of TherapyCompanion.AI
Demonstrates core functionality
"""

import asyncio
from app.core.agent import TherapyAgent
from app.models.therapist import TherapistProfile, TherapeuticApproach


async def example_basic_agent():
    """Example: Basic agent without personalization"""
    print("\n=== Example 1: Basic Agent ===")

    agent = TherapyAgent()

    # Execute /start command
    response = await agent.handle_command("start")
    print(f"Agent: {response}")


async def example_personalized_agent():
    """Example: Personalized agent with therapist profile"""
    print("\n=== Example 2: Personalized Agent ===")

    # Create a sample therapist profile
    profile = TherapistProfile(
        therapeutic_approach=TherapeuticApproach.CBT,
        approach_description="CBT עם דגש על חשיבה אוטומטית וחשיפה הדרגתית",
        tone="תומכת וישירה",
        message_length_preference="short",
        common_terminology=["תרגיל", "חשיפה", "מחשבות אוטומטיות"],
        follow_up_frequency="weekly",
        preferred_exercises=["נשימה", "יומן מחשבות", "חשיפה הדרגתית"],
        language="he"
    )

    # Create personalized agent
    agent = TherapyAgent(therapist_profile=profile)

    # Chat with agent
    response = await agent.generate_response(
        "בואי ניצור הודעה למטופל יוסי שיזכיר לו לעשות את תרגיל הנשימה",
        context={"patient_name": "יוסי"}
    )

    print(f"Agent: {response}")


async def example_onboarding_flow():
    """Example: Therapist onboarding flow"""
    print("\n=== Example 3: Onboarding Flow ===")

    agent = TherapyAgent()

    # Step 1: Start onboarding
    print("Step 1: Starting onboarding...")
    response = await agent.handle_command("start")
    print(f"Agent: {response[:200]}...\n")

    # Step 2: Therapist provides approach
    print("Step 2: Therapist selects CBT approach...")
    # In real app, this would update the database
    print("✓ Approach saved\n")

    # Step 3: Therapist describes style
    print("Step 3: Therapist describes writing style...")
    print("✓ Style saved\n")

    print("Onboarding complete!")


async def example_message_workflow():
    """Example: Patient message creation and approval workflow"""
    print("\n=== Example 4: Message Workflow ===")

    # Create personalized agent
    profile = TherapistProfile(
        therapeutic_approach=TherapeuticApproach.CBT,
        tone="חם ותומך",
        message_length_preference="short",
        language="he"
    )

    agent = TherapyAgent(therapist_profile=profile)

    # Step 1: AI creates draft message
    print("Step 1: AI creates draft message...")
    draft = await agent.generate_response(
        "צור הודעת מעקב קצרה למטופל שרה לבדוק איך הלך תרגיל החשיפה",
        context={
            "patient_name": "שרה",
            "last_exercise": "חשיפה הדרגתית לעליות"
        }
    )
    print(f"Draft: {draft}\n")

    # Step 2: Therapist reviews
    print("Step 2: Therapist reviews draft...")
    print("Status: PENDING APPROVAL\n")

    # Step 3: Therapist can edit
    print("Step 3: Therapist can edit if needed...")
    edited = draft  # In real app, therapist might edit
    print(f"Final: {edited}\n")

    # Step 4: Therapist approves
    print("Step 4: Therapist approves message...")
    print("Status: APPROVED\n")

    # Step 5: Message sent
    print("Step 5: Message sent to patient!")
    print("✓ Message delivered\n")


async def example_session_summary():
    """Example: Session summary generation"""
    print("\n=== Example 5: Session Summary ===")

    profile = TherapistProfile(
        therapeutic_approach=TherapeuticApproach.CBT,
        tone="מקצועי וממוקד",
        language="he"
    )

    agent = TherapyAgent(therapist_profile=profile)

    # Simulated therapist notes
    notes = """
    פגישה עם דני, מספר 5.
    דיברנו על חרדה חברתית, במיוחד בפגישות עבודה.
    עשינו תרגיל חשיפה קטן - דני סימולט פגישה.
    התקדמות טובה, פחות הימנעות.
    הטלתי תרגיל: זיהוי מחשבות אוטומטיות בפגישה הבאה.
    """

    # Generate summary
    print("Generating session summary...")
    summary = await agent.generate_response(
        f"צור סיכום מובנה מהרשימות הבאות:\n{notes}",
        context={"session_number": 5}
    )

    print(f"\nSession Summary:\n{summary}")


async def main():
    """Run all examples"""
    print("=" * 60)
    print("TherapyCompanion.AI - Example Usage")
    print("=" * 60)

    await example_basic_agent()
    await example_personalized_agent()
    await example_onboarding_flow()
    await example_message_workflow()
    await example_session_summary()

    print("\n" + "=" * 60)
    print("Examples completed!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
