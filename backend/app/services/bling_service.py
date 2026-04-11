"""Serviço de integração com API Bling"""
import requests
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from app.core.config import settings
from app.core.exceptions import (
    BlingAuthenticationError,
    BlingValidationError,
    BlingNotFoundError,
    BlingServerError
)

logger = logging.getLogger(__name__)


class BlingAPIService:
    """Serviço para integração com API Bling"""
    
    def __init__(self):
        self.base_url = settings.BLING_API_BASE_URL
        self.api_key = settings.BLING_API_KEY
        self.timeout = 30
        
    def _get_headers(self) -> Dict[str, str]:
        """Retorna headers padrão para requisições"""
        return {
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
    
    def _handle_response(self, response: requests.Response) -> Dict[str, Any]:
        """Trata resposta da API Bling"""
        try:
            if response.status_code == 401:
                raise BlingAuthenticationError("Chave de API inválida ou expirada")
            elif response.status_code == 400:
                raise BlingValidationError(f"Erro de validação: {response.text}")
            elif response.status_code == 404:
                raise BlingNotFoundError("Recurso não encontrado")
            elif response.status_code >= 500:
                raise BlingServerError(f"Erro no servidor Bling: {response.status_code}")
            
            response.raise_for_status()
            return response.json() if response.content else {}
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Erro na requisição Bling: {str(e)}")
            raise BlingServerError(f"Erro ao comunicar com Bling: {str(e)}")
    
    def obter_produto_por_sku(self, sku: str) -> Dict[str, Any]:
        """Obtém dados de um produto pelo SKU"""
        url = f"{self.base_url}/produto/{sku}/json"
        params = {"apikey": self.api_key}
        
        try:
            response = requests.get(url, params=params, headers=self._get_headers(), timeout=self.timeout)
            return self._handle_response(response)
        except Exception as e:
            logger.error(f"Erro ao obter produto {sku}: {str(e)}")
            raise
    
    def obter_produto_por_id(self, produto_id: str) -> Dict[str, Any]:
        """Obtém dados de um produto pelo ID"""
        url = f"{self.base_url}/produto/{produto_id}/json"
        params = {"apikey": self.api_key}
        
        try:
            response = requests.get(url, params=params, headers=self._get_headers(), timeout=self.timeout)
            return self._handle_response(response)
        except Exception as e:
            logger.error(f"Erro ao obter produto {produto_id}: {str(e)}")
            raise
    
    def listar_produtos(self, pagina: int = 1, limite: int = 100) -> Dict[str, Any]:
        """Lista todos os produtos com paginação"""
        url = f"{self.base_url}/produtos/json"
        params = {
            "apikey": self.api_key,
            "pagina": pagina,
            "limite": limite
        }
        
        try:
            response = requests.get(url, params=params, headers=self._get_headers(), timeout=self.timeout)
            return self._handle_response(response)
        except Exception as e:
            logger.error(f"Erro ao listar produtos: {str(e)}")
            raise
    
    def criar_produto(self, dados_produto: Dict[str, Any]) -> Dict[str, Any]:
        """Cria um novo produto na Bling"""
        url = f"{self.base_url}/produto/json"
        params = {"apikey": self.api_key}
        
        try:
            response = requests.post(
                url, 
                json=dados_produto, 
                params=params, 
                headers=self._get_headers(), 
                timeout=self.timeout
            )
            return self._handle_response(response)
        except Exception as e:
            logger.error(f"Erro ao criar produto: {str(e)}")
            raise
    
    def atualizar_produto(self, produto_id: str, dados_produto: Dict[str, Any]) -> Dict[str, Any]:
        """Atualiza um produto existente"""
        url = f"{self.base_url}/produto/{produto_id}/json"
        params = {"apikey": self.api_key}
        
        try:
            response = requests.put(
                url, 
                json=dados_produto, 
                params=params, 
                headers=self._get_headers(), 
                timeout=self.timeout
            )
            return self._handle_response(response)
        except Exception as e:
            logger.error(f"Erro ao atualizar produto {produto_id}: {str(e)}")
            raise
    
    def deletar_produto(self, produto_id: str) -> Dict[str, Any]:
        """Deleta um produto"""
        url = f"{self.base_url}/produto/{produto_id}/json"
        params = {"apikey": self.api_key}
        
        try:
            response = requests.delete(url, params=params, headers=self._get_headers(), timeout=self.timeout)
            return self._handle_response(response)
        except Exception as e:
            logger.error(f"Erro ao deletar produto {produto_id}: {str(e)}")
            raise
    
    def atualizar_estoque(self, produto_id: str, quantidade: int) -> Dict[str, Any]:
        """Atualiza o estoque de um produto"""
        dados = {"estoque": quantidade}
        return self.atualizar_produto(produto_id, dados)
    
    def obter_estoque(self, produto_id: str) -> int:
        """Obtém informação de estoque de um produto"""
        try:
            produto = self.obter_produto_por_id(produto_id)
            return produto.get("data", {}).get("estoque", 0)
        except Exception as e:
            logger.error(f"Erro ao obter estoque do produto {produto_id}: {str(e)}")
            raise
    
    def adicionar_componentes(self, produto_id: str, componentes: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Adiciona componentes a um produto (Composição)"""
        dados = {
            "componentes": componentes
        }
        return self.atualizar_produto(produto_id, dados)
    
    def remover_componente(self, produto_id: str, componente_id: str) -> Dict[str, Any]:
        """Remove um componente de um produto"""
        url = f"{self.base_url}/produto/{produto_id}/componente/{componente_id}/json"
        params = {"apikey": self.api_key}
        
        try:
            response = requests.delete(url, params=params, headers=self._get_headers(), timeout=self.timeout)
            return self._handle_response(response)
        except Exception as e:
            logger.error(f"Erro ao remover componente: {str(e)}")
            raise
    
    def validar_conexao(self) -> bool:
        """Valida se a conexão com Bling está funcionando"""
        try:
            url = f"{self.base_url}/contatos/json"
            params = {"apikey": self.api_key, "limite": 1}
            response = requests.get(url, params=params, headers=self._get_headers(), timeout=self.timeout)
            response.raise_for_status()
            return True
        except Exception as e:
            logger.error(f"Erro ao validar conexão Bling: {str(e)}")
            return False
