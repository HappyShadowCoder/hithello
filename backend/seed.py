import os
import sys

# Ensure backend directory is in path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from models.db import SessionLocal
from models.schema import Team, User
from services.auth import get_password_hash

def seed_db():
    db = SessionLocal()
    
    # Check if teams already exist
    red_team = db.query(Team).filter(Team.name == "Red").first()
    if not red_team:
        red_team = Team(name="Red", color="#ff4d4d")
        db.add(red_team)
        
    blue_team = db.query(Team).filter(Team.name == "Blue").first()
    if not blue_team:
        blue_team = Team(name="Blue", color="#4da6ff")
        db.add(blue_team)
        
    db.commit()
    db.refresh(red_team)
    db.refresh(blue_team)
    
    # Add users
    red_user = db.query(User).filter(User.username == "red").first()
    if not red_user:
        red_user = User(
            username="red",
            password_hash=get_password_hash("red123"),
            role="player",
            team_id=red_team.id
        )
        db.add(red_user)
        
    blue_user = db.query(User).filter(User.username == "blue").first()
    if not blue_user:
        blue_user = User(
            username="blue",
            password_hash=get_password_hash("blue123"),
            role="player",
            team_id=blue_team.id
        )
        db.add(blue_user)
        
    db.commit()
    print("Database seeded with Red and Blue teams and users.")
    db.close()

if __name__ == "__main__":
    seed_db()
