#!/usr/bin/env python3
"""
Create a test therapist account for testing
"""
import sys
import os

# Add the app directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import SessionLocal, engine
from app.models.base import Base
from app.models.therapist import Therapist, TherapistProfile, TherapeuticApproach
from app.security.auth import get_password_hash

# Create tables
Base.metadata.create_all(bind=engine)

# Create session
db = SessionLocal()

try:
    # Check if test user already exists
    existing = db.query(Therapist).filter(Therapist.email == "test@therapy.ai").first()

    if existing:
        print("✅ משתמש בדיקה כבר קיים!")
        print("\n📧 פרטי התחברות:")
        print("   Email: test@therapy.ai")
        print("   Password: test123456")
        print("\n🌐 גש ל: http://localhost:3000")
    else:
        # Create test therapist
        therapist = Therapist(
            email="test@therapy.ai",
            hashed_password=get_password_hash("test123456"),
            full_name="ד״ר שרה כהן - בדיקה",
            phone="050-1234567",
            is_active=True,
            is_verified=True
        )

        db.add(therapist)
        db.commit()
        db.refresh(therapist)

        # Create profile
        profile = TherapistProfile(
            therapist_id=therapist.id,
            therapeutic_approach=TherapeuticApproach.CBT,
            approach_description="CBT עם דגש על חשיפה הדרגתית",
            tone="תומכת וישירה",
            message_length_preference="short",
            common_terminology=["תרגיל", "חשיפה", "מחשבות אוטומטיות"],
            follow_up_frequency="weekly",
            preferred_exercises=["נשימה", "יומן מחשבות", "חשיפה הדרגתית"],
            language="he",
            onboarding_completed=True,  # Skip onboarding
            onboarding_step=5
        )

        db.add(profile)
        db.commit()

        print("✅ נוצר משתמש בדיקה בהצלחה!")
        print("\n📧 פרטי התחברות:")
        print("   Email: test@therapy.ai")
        print("   Password: test123456")
        print("\n🌐 גש ל: http://localhost:3000")
        print("\n💡 המשתמש עבר כבר את תהליך ההיכרות, אז תגיע ישר לדשבורד!")

except Exception as e:
    print(f"❌ שגיאה: {str(e)}")
    db.rollback()
finally:
    db.close()
