from models.db import engine, Base, SessionLocal
from models.schema import User, Team, ExerciseConfig
from services.auth import get_password_hash

def init_db():
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    
    # Create Default Teams
    blue_team = db.query(Team).filter(Team.name == "Blue").first()
    if not blue_team:
        blue_team = Team(name="Blue", color="#4d9fff")
        db.add(blue_team)
        
    red_team = db.query(Team).filter(Team.name == "Red").first()
    if not red_team:
        red_team = Team(name="Red", color="#ff4d4d")
        db.add(red_team)
        
    db.commit()
    
    # Create Exercise Config if not exists
    config = db.query(ExerciseConfig).filter(ExerciseConfig.id == 1).first()
    if not config:
        config = ExerciseConfig(id=1, active_team_1_id=blue_team.id, active_team_2_id=red_team.id)
        db.add(config)
        db.commit()
    
    # Create EXCON user
    excon_user = db.query(User).filter(User.username == "excon").first()
    if not excon_user:
        excon_user = User(
            username="excon",
            password_hash=get_password_hash("excon123"),
            role="excon"
        )
        db.add(excon_user)
        
    # Create SYSCON user
    syscon_user = db.query(User).filter(User.username == "syscon").first()
    if not syscon_user:
        syscon_user = User(
            username="syscon",
            password_hash=get_password_hash("syscon123"),
            role="syscon"
        )
        db.add(syscon_user)
        
    # Create Blue Team user
    blue_user = db.query(User).filter(User.username == "blue").first()
    if not blue_user:
        blue_user = User(
            username="blue",
            password_hash=get_password_hash("blue123"),
            role="player",
            team_id=blue_team.id
        )
        db.add(blue_user)
        
    # Create Red Team user
    red_user = db.query(User).filter(User.username == "red").first()
    if not red_user:
        red_user = User(
            username="red",
            password_hash=get_password_hash("red123"),
            role="player",
            team_id=red_team.id
        )
        db.add(red_user)
        
    db.commit()
    db.close()
    
if __name__ == "__main__":
    init_db()
    print("Database initialized successfully.")
