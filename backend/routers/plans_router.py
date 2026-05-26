from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel

from models.db import get_db
from models.schema import User, ExercisePlan
from services.deps import get_current_user, get_current_excon_user

router = APIRouter(prefix="/api/plans", tags=["Plans"])

class PlanCreate(BaseModel):
    name: str
    exercise_name: Optional[str] = None
    description: Optional[str] = None
    blue_boundary: Optional[str] = None
    red_boundary: Optional[str] = None
    region_id: Optional[str] = None
    orbat: Optional[str] = None

class PlanReorder(BaseModel):
    plan_ids: List[int] # Ordered list of plan IDs

@router.get("/")
def get_plans(db: Session = Depends(get_db), current_user: User = Depends(get_current_excon_user)):
    plans = db.query(ExercisePlan).filter(ExercisePlan.user_id == current_user.id).order_by(ExercisePlan.sort_order).all()
    return [{"id": p.id, "name": p.name, "exercise_name": p.exercise_name, "description": p.description, "sort_order": p.sort_order, "blue_boundary": p.blue_boundary, "red_boundary": p.red_boundary, "region_id": p.region_id, "orbat": p.orbat} for p in plans]

@router.post("/")
def create_plan(plan: PlanCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_excon_user)):
    count = db.query(ExercisePlan).filter(ExercisePlan.user_id == current_user.id).count()
    if count >= 5:
        raise HTTPException(status_code=400, detail="Maximum 5 plans allowed.")
        
    new_plan = ExercisePlan(
        user_id=current_user.id,
        name=plan.name,
        exercise_name=plan.exercise_name,
        description=plan.description,
        blue_boundary=plan.blue_boundary,
        red_boundary=plan.red_boundary,
        region_id=plan.region_id,
        orbat=plan.orbat,
        sort_order=count
    )
    db.add(new_plan)
    db.commit()
    db.refresh(new_plan)
    return {"id": new_plan.id, "name": new_plan.name, "exercise_name": new_plan.exercise_name, "description": new_plan.description, "sort_order": new_plan.sort_order, "blue_boundary": new_plan.blue_boundary, "red_boundary": new_plan.red_boundary, "region_id": new_plan.region_id, "orbat": new_plan.orbat}

@router.delete("/{plan_id}")
def delete_plan(plan_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_excon_user)):
    plan = db.query(ExercisePlan).filter(ExercisePlan.id == plan_id, ExercisePlan.user_id == current_user.id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    
    db.delete(plan)
    db.commit()
    return {"status": "deleted"}

@router.put("/{plan_id}")
def update_plan(plan_id: int, plan: PlanCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_excon_user)):
    existing_plan = db.query(ExercisePlan).filter(ExercisePlan.id == plan_id, ExercisePlan.user_id == current_user.id).first()
    if not existing_plan:
        raise HTTPException(status_code=404, detail="Plan not found")
        
    existing_plan.name = plan.name
    existing_plan.exercise_name = plan.exercise_name
    existing_plan.description = plan.description
    existing_plan.blue_boundary = plan.blue_boundary
    existing_plan.red_boundary = plan.red_boundary
    existing_plan.region_id = plan.region_id
    existing_plan.orbat = plan.orbat
    
    db.commit()
    db.refresh(existing_plan)
    return {"id": existing_plan.id, "name": existing_plan.name, "exercise_name": existing_plan.exercise_name, "description": existing_plan.description, "sort_order": existing_plan.sort_order, "blue_boundary": existing_plan.blue_boundary, "red_boundary": existing_plan.red_boundary, "region_id": existing_plan.region_id, "orbat": existing_plan.orbat}

@router.put("/reorder")
def reorder_plans(order: PlanReorder, db: Session = Depends(get_db), current_user: User = Depends(get_current_excon_user)):
    for index, plan_id in enumerate(order.plan_ids):
        plan = db.query(ExercisePlan).filter(ExercisePlan.id == plan_id, ExercisePlan.user_id == current_user.id).first()
        if plan:
            plan.sort_order = index
            
    db.commit()
    return {"status": "reordered"}
