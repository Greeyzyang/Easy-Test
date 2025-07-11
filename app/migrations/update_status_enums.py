from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
SQLALCHEMY_DATABASE_URL = "mysql+pymysql://root:root@localhost/test_platform"

def update_status_enums():
    engine = create_engine(SQLALCHEMY_DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        # 修改枚举类型
        session.execute(text("""
            ALTER TABLE execution_details 
            MODIFY status ENUM('PENDING', 'IN_PROGRESS', 'PASSED', 'FAILED') 
            DEFAULT 'PENDING'
        """))
        
        # 更新现有值为大写
        session.execute(text("""
            UPDATE execution_details 
            SET status = UPPER(status)
        """))
        
        session.commit()
        print("成功更新所有状态枚举值为大写")
        
        # 验证更新
        result = session.execute(text("SELECT DISTINCT status FROM execution_details"))
        print("当前状态值:", [r[0] for r in result])
        
    except Exception as e:
        session.rollback()
        print(f"更新状态枚举值时出错: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    update_status_enums()