"""
Base repository class with common CRUD operations.

All specific repositories should inherit from this class and override model_class.
Reduces code duplication and provides consistent data access patterns.
"""

from typing import Generic, TypeVar, Optional, List, Type, Any
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.infra.db import Base


# Generic type variables
ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    """
    Base repository with common CRUD operations for all models.
    
    Subclasses must set the model_class attribute.
    
    Example:
        class UserRepository(BaseRepository):
            model_class = UserModel
            
            @classmethod
            def get_by_email(cls, db: Session, tenant_id: UUID, email: str):
                return db.query(cls.model_class).filter(
                    cls.model_class.tenant_id == tenant_id,
                    cls.model_class.email == email
                ).first()
    """
    
    model_class: Type[ModelT] = None
    """Override this in subclass with the actual model class."""
    
    @classmethod
    def _validate_model_class(cls):
        """Ensure model_class is set."""
        if cls.model_class is None:
            raise NotImplementedError(
                f"{cls.__name__}.model_class must be set"
            )
    
    @classmethod
    def get_by_id(
        cls,
        db: Session,
        tenant_id: UUID,
        id: UUID,
    ) -> Optional[ModelT]:
        """
        Get a single record by ID and tenant.
        
        Args:
            db: Database session
            tenant_id: Tenant ID for multi-tenancy filtering
            id: Record ID
            
        Returns:
            Model instance or None if not found
        """
        cls._validate_model_class()
        return db.query(cls.model_class).filter(
            cls.model_class.tenant_id == tenant_id,
            cls.model_class.id == id
        ).first()
    
    @classmethod
    def list_all(
        cls,
        db: Session,
        tenant_id: UUID,
    ) -> List[ModelT]:
        """
        Get all records for a tenant.
        
        Args:
            db: Database session
            tenant_id: Tenant ID for filtering
            
        Returns:
            List of model instances
        """
        cls._validate_model_class()
        return db.query(cls.model_class).filter(
            cls.model_class.tenant_id == tenant_id
        ).all()
    
    @classmethod
    def list_with_filter(
        cls,
        db: Session,
        tenant_id: UUID,
        **filters: Any
    ) -> List[ModelT]:
        """
        Get records with flexible filtering.
        
        Args:
            db: Database session
            tenant_id: Tenant ID for filtering
            **filters: Field-value pairs to filter by
            
        Returns:
            List of model instances matching filters
            
        Example:
            repo.list_with_filter(db, tenant_id, name="Test", active=True)
        """
        cls._validate_model_class()
        
        # Start with tenant filter
        query = db.query(cls.model_class).filter(
            cls.model_class.tenant_id == tenant_id
        )
        
        # Add additional filters
        for field, value in filters.items():
            if hasattr(cls.model_class, field):
                query = query.filter(getattr(cls.model_class, field) == value)
        
        return query.all()
    
    @classmethod
    def create(
        cls,
        db: Session,
        **kwargs: Any
    ) -> ModelT:
        """
        Create a new record.
        
        Args:
            db: Database session
            **kwargs: Fields and values for the new record
            
        Returns:
            Created model instance
        """
        cls._validate_model_class()
        
        obj = cls.model_class(**kwargs)
        db.add(obj)
        db.commit()
        db.refresh(obj)
        return obj
    
    @classmethod
    def update(
        cls,
        db: Session,
        id: UUID,
        **kwargs: Any
    ) -> Optional[ModelT]:
        """
        Update an existing record.
        
        Args:
            db: Database session
            id: Record ID to update
            **kwargs: Fields and new values
            
        Returns:
            Updated model instance or None if not found
        """
        cls._validate_model_class()
        
        obj = db.query(cls.model_class).filter(
            cls.model_class.id == id
        ).first()
        
        if not obj:
            return None
        
        for field, value in kwargs.items():
            if hasattr(obj, field):
                setattr(obj, field, value)
        
        db.commit()
        db.refresh(obj)
        return obj
    
    @classmethod
    def delete(
        cls,
        db: Session,
        id: UUID,
    ) -> bool:
        """
        Delete a record by ID.
        
        Args:
            db: Database session
            id: Record ID to delete
            
        Returns:
            True if deleted, False if not found
        """
        cls._validate_model_class()
        
        obj = db.query(cls.model_class).filter(
            cls.model_class.id == id
        ).first()
        
        if not obj:
            return False
        
        db.delete(obj)
        db.commit()
        return True
    
    @classmethod
    def exists(
        cls,
        db: Session,
        tenant_id: UUID,
        id: UUID,
    ) -> bool:
        """
        Check if a record exists.
        
        Args:
            db: Database session
            tenant_id: Tenant ID for filtering
            id: Record ID to check
            
        Returns:
            True if exists, False otherwise
        """
        cls._validate_model_class()
        
        return db.query(
            cls.model_class
        ).filter(
            cls.model_class.tenant_id == tenant_id,
            cls.model_class.id == id
        ).first() is not None
    
    @classmethod
    def count(
        cls,
        db: Session,
        tenant_id: UUID,
        **filters: Any
    ) -> int:
        """
        Count records matching criteria.
        
        Args:
            db: Database session
            tenant_id: Tenant ID for filtering
            **filters: Additional filters
            
        Returns:
            Number of matching records
        """
        cls._validate_model_class()
        
        query = db.query(cls.model_class).filter(
            cls.model_class.tenant_id == tenant_id
        )
        
        for field, value in filters.items():
            if hasattr(cls.model_class, field):
                query = query.filter(getattr(cls.model_class, field) == value)
        
        return query.count()
    
    @classmethod
    def bulk_create(
        cls,
        db: Session,
        items: List[dict],
    ) -> List[ModelT]:
        """
        Create multiple records in one transaction.
        
        Args:
            db: Database session
            items: List of dicts with record data
            
        Returns:
            List of created model instances
        """
        cls._validate_model_class()
        
        objects = [cls.model_class(**item) for item in items]
        db.add_all(objects)
        db.commit()
        
        for obj in objects:
            db.refresh(obj)
        
        return objects
    
    @classmethod
    def bulk_delete(
        cls,
        db: Session,
        ids: List[UUID],
    ) -> int:
        """
        Delete multiple records.
        
        Args:
            db: Database session
            ids: List of IDs to delete
            
        Returns:
            Number of deleted records
        """
        cls._validate_model_class()
        
        count = db.query(cls.model_class).filter(
            cls.model_class.id.in_(ids)
        ).delete(synchronize_session=False)
        
        db.commit()
        return count
