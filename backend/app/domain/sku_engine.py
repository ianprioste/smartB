"""SKU Engine - Deterministic and canonical SKU generation.

This module is the core logic for generating SKUs based on business rules.
It is ISOLATED and TESTABLE - no database or Bling access.
Receives only normalized data.

Business Rules:
- Parent Printed: {MODEL_CODE}{PRINT_CODE}
- Variation Printed: {MODEL_CODE}{PRINT_CODE}{COLOR_CODE}{SIZE}
- Base Plain: {MODEL_CODE}{COLOR_CODE}{SIZE}
- Stamp: STM{MODEL_CODE}{PRINT_CODE}
"""


class SkuEngine:
    """
    Deterministic SKU generator.
    
    All methods are static and pure functions.
    No side effects, no external dependencies.
    """
    
    @staticmethod
    def parent_printed(model: str, print_code: str) -> str:
        """
        Generate SKU for printed parent product.
        
        Format: {MODEL_CODE}{PRINT_CODE}
        Example: CAM + STPV = CAMSTPV
        
        Args:
            model: Model code (e.g., CAM, BL)
            print_code: Print/stamp code (e.g., STPV)
            
        Returns:
            Canonical parent SKU
        """
        return f"{model.upper()}{print_code.upper()}"
    
    @staticmethod
    def variation_printed(model: str, print_code: str, color: str, size: str) -> str:
        """
        Generate SKU for printed variation product.
        
        Format: {MODEL_CODE}{PRINT_CODE}{COLOR_CODE}{SIZE}
        Example: CAM + STPV + BR + P = CAMSTPVBRP
        
        Args:
            model: Model code (e.g., CAM, BL)
            print_code: Print/stamp code (e.g., STPV)
            color: Color code (e.g., BR, OW)
            size: Size code (e.g., P, M, G)
            
        Returns:
            Canonical variation SKU
        """
        return f"{model.upper()}{print_code.upper()}{color.upper()}{size.upper()}"
    
    @staticmethod
    def base_plain(model: str, color: str, size: str) -> str:
        """
        Generate SKU for plain base product.
        
        Format: {MODEL_CODE}{COLOR_CODE}{SIZE}
        Example: CAM + BR + P = CAMBRP
        
        Args:
            model: Model code (e.g., CAM, BL)
            color: Color code (e.g., BR, OW)
            size: Size code (e.g., P, M, G)
            
        Returns:
            Canonical base SKU
        """
        return f"{model.upper()}{color.upper()}{size.upper()}"
    
    @staticmethod
    def stamp(model: str, print_code: str) -> str:
        """
        Generate SKU for stamp product.
        
        Format: STM{MODEL_CODE}{PRINT_CODE}
        Example: CAM + STPV = STMCAMSTPV
        
        Args:
            model: Model code (e.g., CAM, BL)
            print_code: Print/stamp code (e.g., STPV)
            
        Returns:
            Canonical stamp SKU
        """
        return f"STM{model.upper()}{print_code.upper()}"
    
    @staticmethod
    def validate_components(model: str, print_code: str, color: str = None, size: str = None) -> None:
        """
        Validate SKU components before generation.
        
        Args:
            model: Model code
            print_code: Print code
            color: Color code (optional)
            size: Size code (optional)
            
        Raises:
            ValueError: If any component is invalid
        """
        if not model or not model.strip():
            raise ValueError("Model code cannot be empty")
        if not print_code or not print_code.strip():
            raise ValueError("Print code cannot be empty")
        if color is not None and (not color or not color.strip()):
            raise ValueError("Color code cannot be empty when provided")
        if size is not None and (not size or not size.strip()):
            raise ValueError("Size code cannot be empty when provided")
