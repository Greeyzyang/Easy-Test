from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import sys
import os

# Add the project root to sys.path so we can import app
sys.path.append(os.getcwd())

from app.config import DATABASE_URL

# Convert async URL to sync for the migration script if needed
SYNC_DATABASE_URL = DATABASE_URL.replace("+aiomysql", "+pymysql") if "+aiomysql" in DATABASE_URL else DATABASE_URL

def verify_db_types():
    engine = create_engine(SYNC_DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        # 1. 检查所有不合法的 request_type
        result = session.execute(text("SELECT request_type, COUNT(*) as count FROM interfaces GROUP BY request_type"))
        rows = result.fetchall()
        print("Current request_type distribution in DB:")
        for row in rows:
            print(f"  - {row[0]}: {row[1]}")
            
        # 2. 特别检查 'Share By Email' 接口
        result = session.execute(text("SELECT name, request_type FROM interfaces WHERE name LIKE '%Share By Email%'"))
        inf = result.fetchone()
        if inf:
            print(f"\nInterface 'Share By Email' actual type in DB: '{inf[1]}'")
            
    except Exception as e:
        print(f"Verification failed: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    verify_db_types()
