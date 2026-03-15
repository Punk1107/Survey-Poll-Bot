import asyncio
import os
import sys

# Add project root to path
sys.path.append(os.getcwd())

from database import engine, get_session, get_next_question, upsert_answer
from models import Base, Survey, Question, Response, Answer

async def test_optimizations():
    print("🚀 Starting optimization verification on existing DB...")
    
    async with get_session() as session:
        # Create a unique title to find it easily
        title = "Verification Test Survey"
        
        # 1. Create a dummy survey
        survey = Survey(title=title, creator_id="verify_test")
        session.add(survey)
        await session.flush()
        
        # 2. Add questions
        q1 = Question(survey_id=survey.id, text="Q1", qtype="text", order=1)
        q2 = Question(survey_id=survey.id, text="Q2", qtype="text", order=2)
        session.add_all([q1, q2])
        await session.flush()
        
        print(f"✅ Created test survey ID {survey.id}.")
        
        # 3. Test get_next_question (should be Q1)
        next_q = await get_next_question(session, survey.id, "user_v1")
        assert next_q is not None and next_q.id == q1.id, f"Expected Q1, got {next_q.id if next_q else 'None'}"
        print("✅ get_next_question (initial) passed.")
        
        # 4. Test upsert_answer
        val, is_upd = await upsert_answer(session, survey.id, q1.id, "user_v1", "Answer 1")
        assert not is_upd, "Expected is_update=False for first answer"
        print("✅ upsert_answer (insert) passed.")
        
        # 5. Test get_next_question (should be Q2)
        next_q = await get_next_question(session, survey.id, "user_v1")
        assert next_q is not None and next_q.id == q2.id, f"Expected Q2, got {next_q.id if next_q else 'None'}"
        print("✅ get_next_question (sequential) passed.")
        
        # 6. Test upsert_answer (update)
        val, is_upd = await upsert_answer(session, survey.id, q1.id, "user_v1", "Answer 1 Updated")
        assert is_upd, "Expected is_update=True for update"
        print("✅ upsert_answer (update) passed.")
        
        await session.rollback() # Clean up

    print("🎉 All database optimizations verified!")

if __name__ == "__main__":
    asyncio.run(test_optimizations())
