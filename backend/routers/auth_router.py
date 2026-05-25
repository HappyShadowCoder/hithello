from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

from models.db import get_db
from models.schema import User, Team
from services.auth import verify_password, create_access_token

router = APIRouter()

class Token(BaseModel):
    access_token: str
    token_type: str
    role: str
    team_id: Optional[int] = None
    team_color: Optional[str] = None
    team_name: Optional[str] = None

@router.post("/login", response_model=Token, tags=["Auth"])
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == form_data.username).first()
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token = create_access_token(data={"sub": user.username, "role": user.role})
    
    team_color = None
    team_name = None
    if user.team:
        team_color = user.team.color
        team_name = user.team.name
        
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "role": user.role,
        "team_id": user.team_id,
        "team_color": team_color,
        "team_name": team_name
    }
