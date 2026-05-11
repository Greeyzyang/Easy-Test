from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from app.utils.logger import get_logger

logger = get_logger(__name__)

# MySQL connection URL
SQLALCHEMY_DATABASE_URL = "mysql+pymysql://root:root@localhost/test_platform"

def update_status_case():
    engine = create_engine(SQLALCHEMY_DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        # 更新 execution_details 表中的状态为大写
        session.execute(
            text("""
                UPDATE execution_details 
                SET status = UPPER(status) 
                WHERE status IN ('pending', 'in_progress', 'completed', 'failed')
            """)
        )
        
        # 更新 testreports 表中的状态为大写
        session.execute(
            text("""
                UPDATE testreports 
                SET status = UPPER(status) 
                WHERE status IN ('pending', 'in_progress', 'completed', 'failed')
            """)
        )
        
        session.commit()
        logger.info("Successfully updated status values to uppercase")
    except Exception as e:
        session.rollback()
        logger.error(f"Error updating status: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    update_status_case()