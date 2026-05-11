from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import sys
import os

# Add the project root to sys.path so we can import app
sys.path.append(os.getcwd())

from app.config import DATABASE_URL

# Convert async URL to sync for the migration script if needed
SYNC_DATABASE_URL = DATABASE_URL.replace("+aiomysql", "+pymysql") if "+aiomysql" in DATABASE_URL else DATABASE_URL

def migrate_file_to_form():
    print(f"Connecting to database: {SYNC_DATABASE_URL}")
    engine = create_engine(SYNC_DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        # 1. Update interfaces table
        print("Updating interfaces table: FILE -> FORM")
        session.execute(text("UPDATE interfaces SET request_type = 'FORM' WHERE request_type = 'FILE'"))
        
        # 2. Update teststeps table if it exists
        print("Updating teststeps table: FILE -> FORM")
        try:
            session.execute(text("UPDATE teststeps SET request_type = 'FORM' WHERE request_type = 'FILE'"))
        except Exception as e:
            print(f"Note: Could not update teststeps (it might not have request_type or table might not exist): {e}")

        # 3. Modify ENUM definition in MySQL if it's a native ENUM
        # We need to find which tables have this enum. Usually it's interfaces and teststeps.
        print("Modifying ENUM definition for interfaces.request_type")
        try:
            session.execute(text("ALTER TABLE interfaces MODIFY request_type ENUM('JSON', 'FORM') DEFAULT 'JSON'"))
        except Exception as e:
            print(f"Note: Could not modify ENUM on interfaces (might not be a native ENUM): {e}")

        try:
            print("Modifying ENUM definition for teststeps.request_type")
            session.execute(text("ALTER TABLE teststeps MODIFY request_type ENUM('JSON', 'FORM') DEFAULT 'JSON'"))
        except Exception as e:
            print(f"Note: Could not modify ENUM on teststeps (might not be a native ENUM): {e}")
            
        session.commit()
        print("Migration completed successfully!")
        
    except Exception as e:
        session.rollback()
        print(f"Migration failed: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    migrate_file_to_form()
