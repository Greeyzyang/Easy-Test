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

def fix_json_to_form_with_files():
    print(f"Connecting to database: {SYNC_DATABASE_URL}")
    engine = create_engine(SYNC_DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        # 查找所有 request_type 为 JSON 的接口
        result = session.execute(text("SELECT id, name, body, request_type FROM interfaces WHERE request_type = 'JSON'"))
        interfaces = result.fetchall()
        
        updated_count = 0
        for inf in interfaces:
            inf_id, name, body_str, req_type = inf
            if not body_str:
                continue
                
            try:
                body = json.loads(body_str) if isinstance(body_str, str) else body_str
                if not isinstance(body, dict):
                    continue
                
                # 检查是否包含文件相关字段
                is_file_related = False
                for key in body.keys():
                    if "file" in key.lower() or "files" in key.lower():
                        is_file_related = True
                        break
                
                # 如果是 POST/PUT 且包含文件，则强转为 FORM
                if is_file_related:
                    print(f"Updating interface '{name}' ({inf_id}) from JSON to FORM due to file fields")
                    session.execute(
                        text("UPDATE interfaces SET request_type = 'FORM' WHERE id = :id"),
                        {"id": inf_id}
                    )
                    updated_count += 1
            except Exception as e:
                print(f"Error processing interface {name}: {e}")
        
        session.commit()
        print(f"Successfully updated {updated_count} interfaces from JSON to FORM.")
        
    except Exception as e:
        session.rollback()
        print(f"Fix failed: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    fix_json_to_form_with_files()
