import asyncio
from app.database import get_db
from app.models.user import User, hash_password
import uuid
from datetime import datetime
from sqlalchemy import text

async def create_admin_user():
    async for db in get_db():
        # Check if admin user already exists
        admin = await db.execute(text("SELECT * FROM users WHERE email = 'admin@qq.com'"))
        if admin.scalar_one_or_none():
            print("Admin user already exists")
            return

        # Create admin user
        admin_user = User(
            id=str(uuid.uuid4()),
            email="admin@qq.com",
            username="admin",
            hashed_password=hash_password("admin1234"),
            is_active=True,
            is_superuser=True,
            is_verified=True,
            created_time=datetime.now(),
            updated_time=datetime.now()
        )
        
        db.add(admin_user)
        await db.commit()
        print("Admin user created successfully")

if __name__ == "__main__":
    asyncio.run(create_admin_user()) 