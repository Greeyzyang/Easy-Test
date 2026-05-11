from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import sys
import os

# Add the project root to sys.path so we can import app
sys.path.append(os.getcwd())

from app.config import DATABASE_URL

# Convert async URL to sync for the migration script if needed
SYNC_DATABASE_URL = DATABASE_URL.replace("+aiomysql", "+pymysql") if "+aiomysql" in DATABASE_URL else DATABASE_URL

def add_body_schema_column():
    print(f"Connecting to database: {SYNC_DATABASE_URL}")
    engine = create_engine(SYNC_DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        # Check if the column already exists
        check_sql = text(
            """
            SELECT COUNT(*)
            FROM information_schema.columns
            WHERE table_schema = DATABASE()
              AND table_name = 'interfaces'
              AND column_name = 'body_schema'
            """
        )
        exists = session.execute(check_sql).scalar()
        
        if not exists:
            print("Adding 'body_schema' column to 'interfaces' table...")
            # Use JSON type for MySQL if supported, otherwise TEXT
            # Since the project uses aiomysql/pymysql and JSON is common in modern MySQL
            # we'll try JSON first, fallback to TEXT if it fails
            try:
                session.execute(text("ALTER TABLE interfaces ADD COLUMN body_schema JSON NULL"))
                print("Successfully added 'body_schema' column as JSON type.")
            except Exception as e:
                print(f"Failed to add as JSON, trying TEXT: {e}")
                session.execute(text("ALTER TABLE interfaces ADD COLUMN body_schema TEXT NULL"))
                print("Successfully added 'body_schema' column as TEXT type.")
            
            session.commit()
        else:
            print("Column 'body_schema' already exists in 'interfaces' table.")
            
    except Exception as e:
        session.rollback()
        print(f"Error during migration: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    add_body_schema_column()
