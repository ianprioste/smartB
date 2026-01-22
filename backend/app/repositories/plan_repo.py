"""Repository for plan operations."""
from typing import Optional, List
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.models.database import PlanModel
from app.models.enums import PlanTypeEnum, PlanStatusEnum
from app.infra.logging import get_logger

logger = get_logger(__name__)


class PlanRepository:
    """Repository for plan CRUD operations."""

    def __init__(self, db: Session):
        """Initialize repository with database session."""
        self.db = db

    def create(
        self,
        tenant_id: UUID,
        plan_type: PlanTypeEnum,
        input_payload: dict,
        plan_payload: dict,
    ) -> PlanModel:
        """
        Create a new plan.
        
        Args:
            tenant_id: Tenant ID
            plan_type: Type of plan
            input_payload: Original request
            plan_payload: Generated plan
            
        Returns:
            Created plan model
        """
        plan = PlanModel(
            tenant_id=tenant_id,
            type=plan_type,
            status=PlanStatusEnum.DRAFT,
            input_payload=input_payload,
            plan_payload=plan_payload,
        )

        self.db.add(plan)
        self.db.commit()
        self.db.refresh(plan)

        logger.info(f"Created plan {plan.id} for tenant {tenant_id}")
        return plan

    def get_by_id(self, plan_id: UUID, tenant_id: UUID) -> Optional[PlanModel]:
        """
        Get plan by ID and tenant.
        
        Args:
            plan_id: Plan ID
            tenant_id: Tenant ID
            
        Returns:
            Plan model or None
        """
        stmt = select(PlanModel).where(
            PlanModel.id == plan_id,
            PlanModel.tenant_id == tenant_id,
        )
        result = self.db.execute(stmt)
        return result.scalar_one_or_none()

    def list_by_tenant(
        self,
        tenant_id: UUID,
        plan_type: Optional[PlanTypeEnum] = None,
        status: Optional[PlanStatusEnum] = None,
        limit: int = 100,
    ) -> List[PlanModel]:
        """
        List plans for tenant.
        
        Args:
            tenant_id: Tenant ID
            plan_type: Optional plan type filter
            status: Optional status filter
            limit: Maximum number of results
            
        Returns:
            List of plans
        """
        stmt = select(PlanModel).where(PlanModel.tenant_id == tenant_id)

        if plan_type:
            stmt = stmt.where(PlanModel.type == plan_type)

        if status:
            stmt = stmt.where(PlanModel.status == status)

        stmt = stmt.order_by(PlanModel.created_at.desc()).limit(limit)

        result = self.db.execute(stmt)
        return list(result.scalars().all())

    def update_status(
        self, plan_id: UUID, tenant_id: UUID, status: PlanStatusEnum
    ) -> Optional[PlanModel]:
        """
        Update plan status.
        
        Args:
            plan_id: Plan ID
            tenant_id: Tenant ID
            status: New status
            
        Returns:
            Updated plan or None
        """
        plan = self.get_by_id(plan_id, tenant_id)

        if plan is None:
            return None

        plan.status = status
        self.db.commit()
        self.db.refresh(plan)

        logger.info(f"Updated plan {plan_id} status to {status}")
        return plan
