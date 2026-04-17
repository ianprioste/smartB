"""Rotas para produtos"""
from fastapi import APIRouter, HTTPException, UploadFile, File, BackgroundTasks
import logging
from typing import List
from app.models.schemas import (
    ProdutoCreate, ProdutoUpdate, ProdutoResponse, BulkOperation,
    AtualizacaoEstoque, AtualizacaoSKU, ComposicaoRequest, ProcessingResult
)
from app.services.produto_service import ProdutoService
from app.services.csv_service import CSVService
from app.core.exceptions import ProductNotFoundError

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/produtos", tags=["Produtos"])

produto_service = ProdutoService()
csv_service = CSVService()


@router.get("/", response_model=List[ProdutoResponse])
async def listar_produtos(pagina: int = 1, limite: int = 100):
    """Lista todos os produtos"""
    try:
        resultado = produto_service.bling.listar_produtos(pagina, limite)
        return resultado.get("data", [])
    except Exception as e:
        logger.error(f"Erro ao listar produtos: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{identificador}", response_model=ProdutoResponse)
async def obter_produto(identificador: str):
    """Obtém um produto por SKU ou ID"""
    try:
        resultado = produto_service.obter_produto(identificador)
        return resultado.get("data", {})
    except ProductNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Erro ao obter produto: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/", response_model=ProdutoResponse)
async def criar_produto(produto: ProdutoCreate):
    """Cria um novo produto"""
    try:
        dados = produto.dict()
        resultado = produto_service.bling.criar_produto(dados)
        return resultado.get("data", {})
    except Exception as e:
        logger.error(f"Erro ao criar produto: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{identificador}", response_model=ProdutoResponse)
async def atualizar_produto(identificador: str, produto: ProdutoUpdate):
    """Atualiza um produto existente"""
    try:
        produto_atual = produto_service.obter_produto(identificador)
        produto_id = produto_atual.get("data", {}).get("id")
        
        if not produto_id:
            raise ProductNotFoundError(f"Produto não encontrado: {identificador}")
        
        dados = produto.dict(exclude_unset=True)
        resultado = produto_service.bling.atualizar_produto(produto_id, dados)
        return resultado.get("data", {})
    except ProductNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Erro ao atualizar produto: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{identificador}")
async def deletar_produto(identificador: str):
    """Deleta um produto"""
    try:
        produto = produto_service.obter_produto(identificador)
        produto_id = produto.get("data", {}).get("id")
        
        if not produto_id:
            raise ProductNotFoundError(f"Produto não encontrado: {identificador}")
        
        resultado = produto_service.bling.deletar_produto(produto_id)
        return {"status": "sucesso", "mensagem": "Produto deletado"}
    except ProductNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Erro ao deletar produto: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/em-massa/criar", response_model=ProcessingResult)
async def criar_produtos_em_massa(operacao: BulkOperation):
    """Cria múltiplos produtos em massa"""
    try:
        resultado = produto_service.criar_produto_em_massa(operacao.produtos)
        return ProcessingResult(
            status="sucesso",
            total_processado=resultado["total"],
            sucesso=resultado["sucesso"],
            erro=resultado["erro"],
            detalhes=resultado["detalhes"]
        )
    except Exception as e:
        logger.error(f"Erro ao criar produtos em massa: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/em-massa/editar", response_model=ProcessingResult)
async def editar_produtos_em_massa(operacao: BulkOperation):
    """Edita múltiplos produtos em massa"""
    try:
        resultado = produto_service.editar_produto_em_massa(operacao.produtos)
        return ProcessingResult(
            status="sucesso",
            total_processado=resultado["total"],
            sucesso=resultado["sucesso"],
            erro=resultado["erro"],
            detalhes=resultado["detalhes"]
        )
    except Exception as e:
        logger.error(f"Erro ao editar produtos em massa: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/em-massa/deletar", response_model=ProcessingResult)
async def deletar_produtos_em_massa(skus: List[str]):
    """Deleta múltiplos produtos"""
    try:
        resultado = produto_service.deletar_produto_em_massa(skus)
        return ProcessingResult(
            status="sucesso",
            total_processado=resultado["total"],
            sucesso=resultado["sucesso"],
            erro=resultado["erro"],
            detalhes=resultado["detalhes"]
        )
    except Exception as e:
        logger.error(f"Erro ao deletar produtos em massa: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/estoque/atualizar-em-massa", response_model=ProcessingResult)
async def atualizar_estoque_em_massa(atualizacoes: List[AtualizacaoEstoque]):
    """Atualiza estoque de múltiplos produtos"""
    try:
        dados = [a.dict() for a in atualizacoes]
        resultado = produto_service.atualizar_estoque_em_massa(dados)
        return ProcessingResult(
            status="sucesso",
            total_processado=resultado["total"],
            sucesso=resultado["sucesso"],
            erro=resultado["erro"],
            detalhes=resultado["detalhes"]
        )
    except Exception as e:
        logger.error(f"Erro ao atualizar estoque em massa: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sku/atualizar-em-massa", response_model=ProcessingResult)
async def atualizar_sku_em_massa(atualizacoes: List[AtualizacaoSKU]):
    """Atualiza SKU de múltiplos produtos"""
    try:
        dados = [a.dict() for a in atualizacoes]
        resultado = produto_service.atualizar_sku_em_massa(dados)
        return ProcessingResult(
            status="sucesso",
            total_processado=resultado["total"],
            sucesso=resultado["sucesso"],
            erro=resultado["erro"],
            detalhes=resultado["detalhes"]
        )
    except Exception as e:
        logger.error(f"Erro ao atualizar SKU em massa: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{sku}/componentes")
async def gerenciar_componentes(sku: str, composicao: ComposicaoRequest):
    """Gerencia componentes (composição) de um produto"""
    try:
        componentes = [c.dict() for c in composicao.componentes]
        resultado = produto_service.gerenciar_componentes(
            sku, 
            componentes, 
            composicao.tipo_operacao
        )
        return resultado
    except Exception as e:
        logger.error(f"Erro ao gerenciar componentes: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/estoque/{sku}")
async def obter_estoque(sku: str):
    """Obtém informação de estoque de um produto"""
    try:
        produto = produto_service.obter_produto(sku)
        estoque = produto.get("data", {}).get("estoque", 0)
        return {"sku": sku, "estoque": estoque}
    except ProductNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Erro ao obter estoque: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
