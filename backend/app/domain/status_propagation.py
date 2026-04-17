"""Status propagation logic for parent-child item synchronized updates."""
from datetime import datetime
from typing import List, Optional, Dict, Any
from uuid import UUID
from sqlalchemy.orm import Session

from app.models.database import ItemProductionNoteModel


DEFAULT_TENANT_ID = UUID("00000000-0000-0000-0000-000000000001")


class StatusPropagationService:
    """Service for handling bidirectional status propagation between parent and child items."""

    @staticmethod
    def propagate_status_to_children(
        db: Session,
        event_id: UUID,
        parent_sku: str,
        new_status: str,
        bling_order_id: Optional[int] = None,
    ) -> List[ItemProductionNoteModel]:
        """
        When a parent item status changes, propagate to all its children.
        
        Args:
            db: Database session
            event_id: Event/campaign ID
            parent_sku: SKU of the parent item
            new_status: New status to apply
            bling_order_id: Optional order ID for context
            
        Returns:
            List of updated child items
        """
        # Find all children of this parent in the same event
        children = StatusPropagationService.get_child_items(
            db, event_id, parent_sku, bling_order_id
        )
        
        updated = []
        for child in children:
            # Update each child
            child.production_status = new_status
            child.updated_at = datetime.utcnow()
            updated.append(child)
        
        if updated:
            db.commit()
        
        return updated

    @staticmethod
    def sync_parent_status_from_children(
        db: Session,
        event_id: UUID,
        parent_sku: str,
        bling_order_id: Optional[int] = None,
    ) -> Optional[ItemProductionNoteModel]:
        """
        After updating a child item, check if all children now have the same status.
        If yes, update parent to match. If statuses are mixed, keep parent as-is.
        
        Args:
            db: Database session
            event_id: Event/campaign ID
            parent_sku: SKU of the parent item
            bling_order_id: Optional order ID for context
            
        Returns:
            Updated parent item, or None if not all children have same status
        """
        # Get parent item
        parent = StatusPropagationService.get_parent_item(
            db, event_id, parent_sku, bling_order_id
        )
        if not parent:
            return None
        
        # Get all children
        children = StatusPropagationService.get_child_items(
            db, event_id, parent_sku, bling_order_id
        )
        
        if not children:
            return None  # No children, nothing to sync
        
        # Check if all children have the same status
        statuses = set(child.production_status for child in children)
        
        if len(statuses) == 1:
            # All children have the same status - update parent
            new_status = statuses.pop()
            parent.production_status = new_status
            parent.updated_at = datetime.utcnow()
            db.commit()
            return parent
        
        # Mixed statuses - keep parent as-is
        return None

    @staticmethod
    def get_parent_item(
        db: Session,
        event_id: UUID,
        sku: str,
        bling_order_id: Optional[int] = None,
    ) -> Optional[ItemProductionNoteModel]:
        """
        Get a parent item by SKU.
        
        Args:
            db: Database session
            event_id: Event/campaign ID
            sku: SKU to search for
            bling_order_id: Optional order ID for filtering
            
        Returns:
            Parent item if found, None otherwise
        """
        norm_sku = sku.strip().upper()
        filters = [
            ItemProductionNoteModel.tenant_id == DEFAULT_TENANT_ID,
            ItemProductionNoteModel.event_id == event_id,
            ItemProductionNoteModel.sku == norm_sku,
            ItemProductionNoteModel.is_parent.is_(True),
        ]
        if bling_order_id is not None:
            filters.append(ItemProductionNoteModel.bling_order_id == bling_order_id)
        
        return db.query(ItemProductionNoteModel).filter(*filters).first()

    @staticmethod
    def get_child_items(
        db: Session,
        event_id: UUID,
        parent_sku: str,
        bling_order_id: Optional[int] = None,
    ) -> List[ItemProductionNoteModel]:
        """
        Get all child items of a parent.
        
        Args:
            db: Database session
            event_id: Event/campaign ID
            parent_sku: SKU of the parent
            bling_order_id: Optional order ID for filtering
            
        Returns:
            List of child items
        """
        norm_parent_sku = parent_sku.strip().upper()
        filters = [
            ItemProductionNoteModel.tenant_id == DEFAULT_TENANT_ID,
            ItemProductionNoteModel.event_id == event_id,
            ItemProductionNoteModel.parent_sku == norm_parent_sku,
            ItemProductionNoteModel.is_parent.is_(False),
        ]
        if bling_order_id is not None:
            filters.append(ItemProductionNoteModel.bling_order_id == bling_order_id)
        
        return db.query(ItemProductionNoteModel).filter(*filters).all()

    @staticmethod
    def get_parent_child_hierarchy(
        db: Session,
        event_id: UUID,
        sku: str,
        bling_order_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Get complete parent-child hierarchy for a given SKU.
        If SKU is parent, returns parent + all children.
        If SKU is child, returns parent + all siblings.
        
        Args:
            db: Database session
            event_id: Event/campaign ID
            sku: SKU to search for (parent or child)
            bling_order_id: Optional order ID for filtering
            
        Returns:
            Dict with structure:
            {
                "parent": {...},
                "children": [{...}, ...],
                "is_parent": bool
            }
        """
        norm_sku = sku.strip().upper()
        
        # Check if this SKU is a parent
        parent = StatusPropagationService.get_parent_item(db, event_id, norm_sku, bling_order_id)
        
        if parent:
            # It's a parent - get all its children
            children = StatusPropagationService.get_child_items(db, event_id, norm_sku, bling_order_id)
            return {
                "is_parent": True,
                "parent": parent,
                "children": children,
            }
        
        # Check if it's a child
        filters = [
            ItemProductionNoteModel.tenant_id == DEFAULT_TENANT_ID,
            ItemProductionNoteModel.event_id == event_id,
            ItemProductionNoteModel.sku == norm_sku,
            ItemProductionNoteModel.is_parent.is_(False),
        ]
        if bling_order_id is not None:
            filters.append(ItemProductionNoteModel.bling_order_id == bling_order_id)
        
        child = db.query(ItemProductionNoteModel).filter(*filters).first()
        
        if child and child.parent_sku:
            # It's a child - get parent and siblings
            parent = StatusPropagationService.get_parent_item(db, event_id, child.parent_sku, bling_order_id)
            children = StatusPropagationService.get_child_items(db, event_id, child.parent_sku, bling_order_id)
            return {
                "is_parent": False,
                "parent": parent,
                "children": children,
            }
        
        # Not in a hierarchy
        return {
            "is_parent": False,
            "parent": None,
            "children": [],
        }

    @staticmethod
    def mark_item_as_parent(
        db: Session,
        event_id: UUID,
        sku: str,
        bling_order_id: Optional[int] = None,
    ) -> ItemProductionNoteModel:
        """Mark an item as a parent product."""
        norm_sku = sku.strip().upper()
        filters = [
            ItemProductionNoteModel.tenant_id == DEFAULT_TENANT_ID,
            ItemProductionNoteModel.event_id == event_id,
            ItemProductionNoteModel.sku == norm_sku,
        ]
        if bling_order_id is not None:
            filters.append(ItemProductionNoteModel.bling_order_id == bling_order_id)
        
        item = db.query(ItemProductionNoteModel).filter(*filters).first()
        if item:
            item.is_parent = True
            db.commit()
        return item

    @staticmethod
    def link_child_to_parent(
        db: Session,
        event_id: UUID,
        child_sku: str,
        parent_sku: str,
        bling_order_id: Optional[int] = None,
    ) -> ItemProductionNoteModel:
        """Link a child item to a parent item."""
        norm_child_sku = child_sku.strip().upper()
        norm_parent_sku = parent_sku.strip().upper()
        
        filters = [
            ItemProductionNoteModel.tenant_id == DEFAULT_TENANT_ID,
            ItemProductionNoteModel.event_id == event_id,
            ItemProductionNoteModel.sku == norm_child_sku,
        ]
        if bling_order_id is not None:
            filters.append(ItemProductionNoteModel.bling_order_id == bling_order_id)
        
        child = db.query(ItemProductionNoteModel).filter(*filters).first()
        if child:
            child.parent_sku = norm_parent_sku
            child.is_parent = False
            db.commit()
        return child
