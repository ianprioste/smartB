"""Rotas de configuração e saúde"""
from fastapi import APIRouter, HTTPException
import logging
from app.core.config import settings
from app.services.bling_service import BlingAPIService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["Config"])

bling_service = BlingAPIService()


@router.get("/health")
async def health_check():
    """Verifica saúde da API"""
    return {
        "status": "ok",
        "versao": "1.0.0"
    }


@router.get("/config")
async def obter_configuracao():
    """Obtém configurações da aplicação (sem dados sensíveis)"""
    return {
        "debug": settings.DEBUG,
        "cors_origins": settings.CORS_ORIGINS,
        "bling_api_base_url": settings.BLING_API_BASE_URL
    }


@router.post("/bling/validar")
async def validar_conexao_bling():
    """Valida conexão com API Bling"""
    try:
        if not settings.BLING_API_KEY:
            raise HTTPException(
                status_code=400,
                detail="BLING_API_KEY não configurada"
            )
        
        conexao_ok = bling_service.validar_conexao()
        
        if conexao_ok:
            return {
                "status": "sucesso",
                "mensagem": "Conexão com Bling validada com sucesso",
                "conectado": True
            }
        else:
            return {
                "status": "erro",
                "mensagem": "Falha ao conectar com Bling",
                "conectado": False
            }
    except Exception as e:
        logger.error(f"Erro ao validar conexão: {str(e)}")
        return {
            "status": "erro",
            "mensagem": str(e),
            "conectado": False
        }


@router.post("/bling/configurar")
async def configurar_bling(api_key: str):
    """Configura a chave de API Bling"""
    try:
        # Atualizar settings
        settings.BLING_API_KEY = api_key
        
        # Validar
        bling_service_temp = BlingAPIService()
        if bling_service_temp.validar_conexao():
            return {
                "status": "sucesso",
                "mensagem": "API Key configurada com sucesso"
            }
        else:
            return {
                "status": "erro",
                "mensagem": "API Key inválida"
            }
    except Exception as e:
        logger.error(f"Erro ao configurar Bling: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
