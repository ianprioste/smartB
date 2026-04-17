"""Product-related Pydantic schemas."""
from pydantic import BaseModel, Field
from typing import Optional, Any, Dict, List


class ProdutoCreate(BaseModel):
    """Create product request."""
    nome: str = Field(min_length=1, max_length=255)
    sku: Optional[str] = None
    descricao: Optional[str] = None
    preco: Optional[float] = None


class ProdutoUpdate(BaseModel):
    """Update product request."""
    nome: Optional[str] = None
    sku: Optional[str] = None
    descricao: Optional[str] = None
    preco: Optional[float] = None


class ProdutoResponse(BaseModel):
    """Product response."""
    id: Optional[int] = None
    codigo: Optional[str] = None
    nome: str
    descricao: Optional[str] = None
    preco: Optional[float] = None


class BulkOperation(BaseModel):
    """Bulk operation request."""
    operation: str = Field(description="Operation: create, update, delete")
    produtos: List[Dict[str, Any]] = Field(default_factory=list)


class AtualizacaoEstoque(BaseModel):
    """Stock update request."""
    sku: str
    quantidade: float


class AtualizacaoSKU(BaseModel):
    """SKU update request."""
    sku_antigo: str
    sku_novo: str


class ComposicaoRequest(BaseModel):
    """Product composition request."""
    principal_sku: str
    itens: List[Dict[str, Any]] = Field(default_factory=list)


class ProcessingResult(BaseModel):
    """Processing result response."""
    status: str = Field(description="Processing status: success, error, pending")
    mensagem: Optional[str] = None
    total_processados: int = 0
    sucesso: int = 0
    erro: int = 0
