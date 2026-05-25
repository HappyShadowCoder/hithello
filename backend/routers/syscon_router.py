from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional

from models.db import get_db
from models.schema import User, Team, ExerciseConfig
from services.deps import get_current_syscon_user, get_current_excon_user
from services.auth import get_password_hash

router = APIRouter()

# --- Pydantic Schemas ---
class TeamCreate(BaseModel):
    name: str
    color: str

class TeamResponse(BaseModel):
    id: int
    name: str
    color: str
    class Config:
        from_attributes = True

class UserCreate(BaseModel):
    username: str
    password: str
    role: str
    team_id: Optional[int] = None

class UserResponse(BaseModel):
    id: int
    username: str
    role: str
    team_id: Optional[int]
    class Config:
        from_attributes = True

class ActiveTeamsSet(BaseModel):
    team_1_id: int
    team_2_id: int

# --- SYSCON Endpoints ---
@router.post("/teams", response_model=TeamResponse, tags=["Syscon"])
def create_team(team: TeamCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_syscon_user)):
    existing = db.query(Team).filter(Team.name == team.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Team name already registered")
    new_team = Team(name=team.name, color=team.color)
    db.add(new_team)
    db.commit()
    db.refresh(new_team)
    return new_team

@router.get("/teams", response_model=List[TeamResponse], tags=["Syscon", "Excon", "Player"])
def get_teams(db: Session = Depends(get_db)):
    return db.query(Team).all()

@router.post("/users", response_model=UserResponse, tags=["Syscon"])
def create_user(user: UserCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_syscon_user)):
    existing = db.query(User).filter(User.username == user.username).first()
    if existing:
        raise HTTPException(status_code=400, detail="Username already registered")
    
    if user.role not in ["syscon", "excon", "player"]:
        raise HTTPException(status_code=400, detail="Invalid role")
        
    if user.role == "player" and not user.team_id:
        raise HTTPException(status_code=400, detail="Players must have a team_id")
        
    new_user = User(
        username=user.username,
        password_hash=get_password_hash(user.password),
        role=user.role,
        team_id=user.team_id
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

@router.get("/users", response_model=List[UserResponse], tags=["Syscon"])
def get_users(db: Session = Depends(get_db), current_user: User = Depends(get_current_syscon_user)):
    return db.query(User).all()

# --- EXCON Endpoints ---
@router.post("/active_teams", tags=["Excon"])
def set_active_teams(teams: ActiveTeamsSet, db: Session = Depends(get_db), current_user: User = Depends(get_current_excon_user)):
    config = db.query(ExerciseConfig).filter(ExerciseConfig.id == 1).first()
    if not config:
        config = ExerciseConfig(id=1, active_team_1_id=teams.team_1_id, active_team_2_id=teams.team_2_id)
        db.add(config)
    else:
        config.active_team_1_id = teams.team_1_id
        config.active_team_2_id = teams.team_2_id
    db.commit()
    return {"status": "success"}

@router.get("/active_teams", tags=["Syscon", "Excon", "Player"])
def get_active_teams(db: Session = Depends(get_db)):
    config = db.query(ExerciseConfig).filter(ExerciseConfig.id == 1).first()
    if not config:
        return {"team_1_id": None, "team_2_id": None}
    return {"team_1_id": config.active_team_1_id, "team_2_id": config.active_team_2_id}
