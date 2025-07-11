from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from app.config import DATABASE_URL

def update_enum_values():
    engine = create_engine(DATABASE_URL.replace("+aiomysql", "+pymysql"))
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        # 更新测试用例状态
        session.execute(
            text("""
            UPDATE testcases 
            SET status = UPPER(status) 
            WHERE status IN ('pending', 'in_progress', 'passed', 'failed')
            """)
        )
        
        # 更新测试步骤状态
        session.execute(
            text("""
            UPDATE test_steps 
            SET status = UPPER(status) 
            WHERE status IN ('pending', 'passed', 'failed')
            """)
        )
        
        session.commit()
        print("Successfully updated enum values to uppercase")
    except Exception as e:
        session.rollback()
        print(f"Error updating enum values: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    update_enum_values()