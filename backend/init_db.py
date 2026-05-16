# backend/init_db.py
import asyncio
from app.core.database import engine
from app.models.base import Base

async def init_models():
    async with engine.begin() as conn:
        # This will create all tables based on our ORM models
        await conn.run_sync(Base.metadata.create_all)
    print("Database tables created successfully!")

if __name__ == "__main__":
    asyncio.run(init_models())