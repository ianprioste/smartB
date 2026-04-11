"""Serviço de gerenciamento de produtos"""
import logging
from typing import Dict, List, Any, Optional
from app.services.bling_service import BlingAPIService
from app.models.schemas import (
    ProdutoCreate, ProdutoUpdate, AtualizacaoSKU, 
    AtualizacaoEstoque, ComponentoBase
)
from app.core.exceptions import ProductNotFoundError, InvalidOperationError

logger = logging.getLogger(__name__)


class ProdutoService:
    """Serviço para gerenciamento de produtos"""
    
    def __init__(self):
        self.bling = BlingAPIService()
    
    def obter_produto(self, identificador: str) -> Dict[str, Any]:
        """Obtém um produto por SKU ou ID"""
        try:
            # Tentar por SKU primeiro
            resultado = self.bling.obter_produto_por_sku(identificador)
            if resultado:
                return resultado
            
            # Se não encontrar, tentar por ID
            resultado = self.bling.obter_produto_por_id(identificador)
            return resultado
            
        except Exception as e:
            logger.error(f"Erro ao obter produto {identificador}: {str(e)}")
            raise ProductNotFoundError(f"Produto não encontrado: {identificador}")
    
    def criar_produto_em_massa(self, produtos: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Cria múltiplos produtos"""
        resultados = {
            "total": len(produtos),
            "sucesso": 0,
            "erro": 0,
            "detalhes": []
        }
        
        for idx, dados_produto in enumerate(produtos, 1):
            try:
                # Validar dados obrigatórios
                self._validar_produto_criar(dados_produto)
                
                # Preparar dados para API Bling
                produto_bling = self._preparar_dados_bling_create(dados_produto)
                
                # Criar produto
                resultado = self.bling.criar_produto(produto_bling)
                
                resultados["sucesso"] += 1
                resultados["detalhes"].append({
                    "indice": idx,
                    "sku": dados_produto.get("sku"),
                    "status": "sucesso",
                    "resposta": resultado
                })
                
            except Exception as e:
                resultados["erro"] += 1
                resultados["detalhes"].append({
                    "indice": idx,
                    "sku": dados_produto.get("sku"),
                    "status": "erro",
                    "mensagem": str(e)
                })
        
        return resultados
    
    def editar_produto_em_massa(self, produtos: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Edita múltiplos produtos"""
        resultados = {
            "total": len(produtos),
            "sucesso": 0,
            "erro": 0,
            "detalhes": []
        }
        
        for idx, dados_produto in enumerate(produtos, 1):
            try:
                # Validar dados
                if "sku" not in dados_produto:
                    raise InvalidOperationError("SKU é obrigatório para edição")
                
                sku = dados_produto.get("sku")
                
                # Obter produto existente
                produto_atual = self.obter_produto(sku)
                produto_id = produto_atual.get("data", {}).get("id")
                
                if not produto_id:
                    raise ProductNotFoundError(f"Produto com SKU {sku} não encontrado")
                
                # Preparar dados para atualização
                produto_bling = self._preparar_dados_bling_update(dados_produto)
                
                # Atualizar produto
                resultado = self.bling.atualizar_produto(produto_id, produto_bling)
                
                resultados["sucesso"] += 1
                resultados["detalhes"].append({
                    "indice": idx,
                    "sku": sku,
                    "status": "sucesso",
                    "resposta": resultado
                })
                
            except Exception as e:
                resultados["erro"] += 1
                resultados["detalhes"].append({
                    "indice": idx,
                    "sku": dados_produto.get("sku"),
                    "status": "erro",
                    "mensagem": str(e)
                })
        
        return resultados
    
    def deletar_produto_em_massa(self, skus: List[str]) -> Dict[str, Any]:
        """Deleta múltiplos produtos"""
        resultados = {
            "total": len(skus),
            "sucesso": 0,
            "erro": 0,
            "detalhes": []
        }
        
        for idx, sku in enumerate(skus, 1):
            try:
                # Obter produto
                produto = self.obter_produto(sku)
                produto_id = produto.get("data", {}).get("id")
                
                if not produto_id:
                    raise ProductNotFoundError(f"Produto com SKU {sku} não encontrado")
                
                # Deletar produto
                self.bling.deletar_produto(produto_id)
                
                resultados["sucesso"] += 1
                resultados["detalhes"].append({
                    "indice": idx,
                    "sku": sku,
                    "status": "sucesso"
                })
                
            except Exception as e:
                resultados["erro"] += 1
                resultados["detalhes"].append({
                    "indice": idx,
                    "sku": sku,
                    "status": "erro",
                    "mensagem": str(e)
                })
        
        return resultados
    
    def atualizar_estoque_em_massa(self, atualizacoes: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Atualiza estoque de múltiplos produtos"""
        resultados = {
            "total": len(atualizacoes),
            "sucesso": 0,
            "erro": 0,
            "detalhes": []
        }
        
        for idx, atualizacao in enumerate(atualizacoes, 1):
            try:
                sku = atualizacao.get("sku")
                quantidade = atualizacao.get("quantidade")
                tipo = atualizacao.get("tipo_operacao", "substituir")
                
                if not sku or quantidade is None:
                    raise InvalidOperationError("SKU e quantidade são obrigatórios")
                
                # Obter produto
                produto = self.obter_produto(sku)
                produto_id = produto.get("data", {}).get("id")
                estoque_atual = produto.get("data", {}).get("estoque", 0)
                
                if not produto_id:
                    raise ProductNotFoundError(f"Produto com SKU {sku} não encontrado")
                
                # Calcular nova quantidade
                if tipo == "somar":
                    nova_quantidade = estoque_atual + quantidade
                elif tipo == "subtrair":
                    nova_quantidade = estoque_atual - quantidade
                else:  # substituir
                    nova_quantidade = quantidade
                
                # Atualizar
                resultado = self.bling.atualizar_estoque(produto_id, nova_quantidade)
                
                resultados["sucesso"] += 1
                resultados["detalhes"].append({
                    "indice": idx,
                    "sku": sku,
                    "estoque_anterior": estoque_atual,
                    "estoque_novo": nova_quantidade,
                    "status": "sucesso"
                })
                
            except Exception as e:
                resultados["erro"] += 1
                resultados["detalhes"].append({
                    "indice": idx,
                    "sku": atualizacao.get("sku"),
                    "status": "erro",
                    "mensagem": str(e)
                })
        
        return resultados
    
    def atualizar_sku_em_massa(self, atualizacoes: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Atualiza SKU de múltiplos produtos"""
        resultados = {
            "total": len(atualizacoes),
            "sucesso": 0,
            "erro": 0,
            "detalhes": []
        }
        
        for idx, atualizacao in enumerate(atualizacoes, 1):
            try:
                produto_id = atualizacao.get("id")
                novo_sku = atualizacao.get("novo_sku")
                
                if not produto_id or not novo_sku:
                    raise InvalidOperationError("ID e novo_sku são obrigatórios")
                
                # Atualizar SKU
                resultado = self.bling.atualizar_produto(produto_id, {"sku": novo_sku})
                
                resultados["sucesso"] += 1
                resultados["detalhes"].append({
                    "indice": idx,
                    "id": produto_id,
                    "novo_sku": novo_sku,
                    "status": "sucesso"
                })
                
            except Exception as e:
                resultados["erro"] += 1
                resultados["detalhes"].append({
                    "indice": idx,
                    "id": atualizacao.get("id"),
                    "status": "erro",
                    "mensagem": str(e)
                })
        
        return resultados
    
    def gerenciar_componentes(self, sku: str, componentes: List[Dict[str, Any]], tipo_operacao: str = "editar") -> Dict[str, Any]:
        """Gerencia componentes (composição) de um produto"""
        try:
            # Obter produto
            produto = self.obter_produto(sku)
            produto_id = produto.get("data", {}).get("id")
            
            if not produto_id:
                raise ProductNotFoundError(f"Produto com SKU {sku} não encontrado")
            
            if tipo_operacao == "editar":
                resultado = self.bling.adicionar_componentes(produto_id, componentes)
            elif tipo_operacao == "deletar":
                # Deletar cada componente
                resultado = {"deletados": 0}
                for componente in componentes:
                    try:
                        self.bling.remover_componente(produto_id, componente.get("id"))
                        resultado["deletados"] += 1
                    except Exception as e:
                        logger.error(f"Erro ao deletar componente: {str(e)}")
            else:
                raise InvalidOperationError(f"Tipo de operação inválido: {tipo_operacao}")
            
            return {
                "status": "sucesso",
                "sku": sku,
                "operacao": tipo_operacao,
                "resultado": resultado
            }
            
        except Exception as e:
            logger.error(f"Erro ao gerenciar componentes: {str(e)}")
            raise
    
    def _validar_produto_criar(self, produto: Dict[str, Any]) -> None:
        """Valida dados obrigatórios para criar produto"""
        campos_obrigatorios = ["sku", "nome", "preco"]
        
        for campo in campos_obrigatorios:
            if campo not in produto or not produto[campo]:
                raise InvalidOperationError(f"Campo obrigatório ausente: {campo}")
    
    def _preparar_dados_bling_create(self, dados: Dict[str, Any]) -> Dict[str, Any]:
        """Prepara dados no formato esperado pela API Bling para criação"""
        return {
            "numero": dados.get("sku"),
            "descricao": dados.get("nome"),
            "descricaoComplementar": dados.get("descricao"),
            "preco": dados.get("preco"),
            "estoque": dados.get("estoque", 0)
        }
    
    def _preparar_dados_bling_update(self, dados: Dict[str, Any]) -> Dict[str, Any]:
        """Prepara dados no formato esperado pela API Bling para atualização"""
        resultado = {}
        
        if "nome" in dados:
            resultado["descricao"] = dados["nome"]
        if "descricao" in dados:
            resultado["descricaoComplementar"] = dados["descricao"]
        if "preco" in dados:
            resultado["preco"] = dados["preco"]
        if "estoque" in dados:
            resultado["estoque"] = dados["estoque"]
        
        return resultado
