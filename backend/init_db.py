# backend/init_db.py
import asyncio
from app.core.database import engine
from app.models.base import Base
from app.models.user import User
from app.models.note import Note
from app.models.share import NoteShare
from app.models.token import RefreshToken

async def init_models():
    async with engine.begin() as conn:
        # This will create all tables based on our ORM models
        await conn.run_sync(Base.metadata.create_all)
    print("Database tables created successfully!")

if __name__ == "__main__":
    asyncio.run(init_models())