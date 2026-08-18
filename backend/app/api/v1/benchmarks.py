from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.api.deps import get_db, require_roles, get_current_user
from app.models import BenchmarkDefinition, User
from app.schemas import BenchmarkDefinitionResponse, BenchmarkCreate, BenchmarkUpdate

router = APIRouter()

@router.get("", response_model=List[BenchmarkDefinitionResponse])
def list_benchmarks(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List all benchmark definitions."""
    return db.query(BenchmarkDefinition).all()

@router.post("", response_model=BenchmarkDefinitionResponse)
def create_benchmark(
    benchmark_in: BenchmarkCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["admin"]))
):
    """Create a new benchmark definition (Admin only)."""
    # Check if indicator already exists
    existing = db.query(BenchmarkDefinition).filter(BenchmarkDefinition.indicator == benchmark_in.indicator).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Benchmark for indicator '{benchmark_in.indicator}' already exists")

    benchmark = BenchmarkDefinition(
        indicator=benchmark_in.indicator,
        unit=benchmark_in.unit,
        target_value=benchmark_in.target_value,
        source=benchmark_in.source,
        reference_name=benchmark_in.reference_name,
        notes=benchmark_in.notes
    )
    db.add(benchmark)
    db.commit()
    db.refresh(benchmark)
    return benchmark

@router.put("/{benchmark_id}", response_model=BenchmarkDefinitionResponse)
def update_benchmark(
    benchmark_id: int,
    benchmark_in: BenchmarkUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["admin"]))
):
    """Update a benchmark definition (Admin only)."""
    benchmark = db.query(BenchmarkDefinition).filter(BenchmarkDefinition.id == benchmark_id).first()
    if not benchmark:
        raise HTTPException(status_code=404, detail="Benchmark not found")

    update_data = benchmark_in.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(benchmark, field, value)

    db.add(benchmark)
    db.commit()
    db.refresh(benchmark)
    return benchmark

@router.delete("/{benchmark_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_benchmark(
    benchmark_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["admin"]))
):
    """Delete a benchmark definition (Admin only)."""
    benchmark = db.query(BenchmarkDefinition).filter(BenchmarkDefinition.id == benchmark_id).first()
    if not benchmark:
        raise HTTPException(status_code=404, detail="Benchmark not found")
        
    db.delete(benchmark)
    db.commit()
    return None
