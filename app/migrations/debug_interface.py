from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import sys
import os
import json

# Add the project root to sys.path so we can import app
sys.path.append(os.getcwd())

from app.config import DATABASE_URL

# Convert async URL to sync for the migration script if needed
SYNC_DATABASE_URL = DATABASE_URL.replace("+aiomysql", "+pymysql") if "+aiomysql" in DATABASE_URL else DATABASE_URL

def debug_interface():
    engine = create_engine(SYNC_DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        # 查找 'Share By Email' 接口
        result = session.execute(text("SELECT id, name, body, request_type FROM interfaces WHERE name LIKE '%Share By Email%'"))
        interfaces = result.fetchall()
        
        print(f"Found {len(interfaces)} interfaces matching 'Share By Email'")
        for inf in interfaces:
            inf_id, name, body_str, req_type = inf
            print("-" * 50)
            print(f"ID: {inf_id}")
            print(f"Name: {name}")
            print(f"Request Type: {req_type}")
            print(f"Body: {body_str}")
            
            if body_str:
                try:
                    body = json.loads(body_str)
                    print(f"Parsed Body Type: {type(body)}")
                    if isinstance(body, dict):
                        print(f"Keys: {list(body.keys())}")
                        for key in body.keys():
                            if "file" in key.lower():
                                print(f"FOUND FILE KEY: {key}")
                except Exception as e:
                    print(f"JSON Parse Error: {e}")
        
    except Exception as e:
        print(f"Debug failed: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    debug_interface()
