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
    description: Optional[str] = None

class PlanReorder(BaseModel):
    plan_ids: List[int] # Ordered list of plan IDs

@router.get("/")
def get_plans(db: Session = Depends(get_db), current_user: User = Depends(get_current_excon_user)):
    plans = db.query(ExercisePlan).filter(ExercisePlan.user_id == current_user.id).order_by(ExercisePlan.sort_order).all()
    return [{"id": p.id, "name": p.name, "description": p.description, "sort_order": p.sort_order} for p in plans]

@router.post("/")
def create_plan(plan: PlanCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_excon_user)):
    count = db.query(ExercisePlan).filter(ExercisePlan.user_id == current_user.id).count()
    if count >= 5:
        raise HTTPException(status_code=400, detail="Maximum 5 plans allowed.")
        
    new_plan = ExercisePlan(
        user_id=current_user.id,
        name=plan.name,
        description=plan.description,
        sort_order=count
    )
    db.add(new_plan)
    db.commit()
    db.refresh(new_plan)
    return {"id": new_plan.id, "name": new_plan.name, "description": new_plan.description, "sort_order": new_plan.sort_order}

@router.delete("/{plan_id}")
def delete_plan(plan_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_excon_user)):
    plan = db.query(ExercisePlan).filter(ExercisePlan.id == plan_id, ExercisePlan.user_id == current_user.id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    
    db.delete(plan)
    db.commit()
    return {"status": "deleted"}

@router.put("/reorder")
def reorder_plans(order: PlanReorder, db: Session = Depends(get_db), current_user: User = Depends(get_current_excon_user)):
    for index, plan_id in enumerate(order.plan_ids):
        plan = db.query(ExercisePlan).filter(ExercisePlan.id == plan_id, ExercisePlan.user_id == current_user.id).first()
        if plan:
            plan.sort_order = index
            
    db.commit()
    return {"status": "reordered"}
