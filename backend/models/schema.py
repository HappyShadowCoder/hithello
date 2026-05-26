from sqlalchemy import Column, Integer, String, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from .db import Base

class Team(Base):
    __tablename__ = "teams"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    color = Column(String, nullable=False)
    
    users = relationship("User", back_populates="team")

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String, nullable=False) # 'syscon', 'excon', 'player'
    
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=True)
    team = relationship("Team", back_populates="users")

class ExercisePlan(Base):
    __tablename__ = "exercise_plans"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)
    exercise_name = Column(String, nullable=True)
    description = Column(String, nullable=True)
    sort_order = Column(Integer, nullable=False, default=0)
    blue_boundary = Column(String, nullable=True)
    red_boundary = Column(String, nullable=True)
    region_id = Column(String, nullable=True)
    orbat = Column(String, nullable=True)
    
    user = relationship("User")

class ExerciseConfig(Base):
    """Stores global configuration like active teams."""
    __tablename__ = "exercise_config"
    
    id = Column(Integer, primary_key=True, index=True)
    # We use a single row for config, id = 1
    active_team_1_id = Column(Integer, ForeignKey("teams.id"), nullable=True)
    active_team_2_id = Column(Integer, ForeignKey("teams.id"), nullable=True)
