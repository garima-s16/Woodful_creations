import sys
import os
import argparse
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal, User
from app.core.security import hash_password
from app.core.exceptions import ConflictError
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_master_user(email: str, username: str, full_name: str, password: str):
    db = SessionLocal()
    try:
        existing_user = db.query(User).filter(
            (User.email == email) | (User.username == username)
        ).first()
        
        if existing_user:
            raise ConflictError(f"User with email or username already exists")
        
        user = User(
            email=email,
            username=username,
            full_name=full_name,
            hashed_password=hash_password(password),
            is_active=True,
            is_master=True,
            role="master"
        )
        
        db.add(user)
        db.commit()
        logger.info(f"Master user {username} created successfully")
        return True
    except Exception as e:
        logger.error(f"Error creating user: {str(e)}")
        db.rollback()
        return False
    finally:
        db.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create a master user")
    parser.add_argument("--email", required=True, help="User email")
    parser.add_argument("--username", required=True, help="Username")
    parser.add_argument("--name", required=True, help="Full name")
    parser.add_argument("--password", required=True, help="Password")
    
    args = parser.parse_args()
    create_master_user(args.email, args.username, args.name, args.password)