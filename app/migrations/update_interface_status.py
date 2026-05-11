from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# MySQL connection URL
SQLALCHEMY_DATABASE_URL = "mysql+pymysql://root:root@localhost/test_platform"

def update_interface_status():
    engine = create_engine(SQLALCHEMY_DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        # Update empty status values to 'in_progress'
        session.execute(
            text("UPDATE interfaces SET status = 'in_progress' WHERE status = '' OR status IS NULL")
        )
        session.commit()
        logger.info("Successfully updated empty interface status values to 'in_progress'")
    except Exception as e:
        session.rollback()
        logger.error(f"Error updating interface status: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    update_interface_status() 