"""Serviço para manipulação de arquivos CSV"""
import csv
import io
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path
import pandas as pd
from app.core.exceptions import CSVImportError, CSVExportError
from app.core.constants import REQUIRED_FIELDS, OPERATION_TYPES

logger = logging.getLogger(__name__)


class CSVService:
    """Serviço para importar e exportar dados em CSV"""
    
    def __init__(self, upload_folder: str = "uploads", export_folder: str = "exports"):
        self.upload_folder = Path(upload_folder)
        self.export_folder = Path(export_folder)
        self.upload_folder.mkdir(exist_ok=True)
        self.export_folder.mkdir(exist_ok=True)
    
    def validar_arquivo(self, arquivo: str) -> bool:
        """Valida se o arquivo CSV existe e é válido"""
        caminho = self.upload_folder / arquivo
        
        if not caminho.exists():
            raise CSVImportError(f"Arquivo não encontrado: {arquivo}")
        
        if not arquivo.lower().endswith('.csv'):
            raise CSVImportError("Apenas arquivos CSV são permitidos")
        
        return True
    
    def importar_csv(self, arquivo: str, tipo_operacao: str, ignorar_erros: bool = False) -> Dict[str, Any]:
        """Importa dados do CSV e retorna lista validada"""
        self.validar_arquivo(arquivo)
        
        try:
            df = pd.read_csv(self.upload_folder / arquivo)
            dados = df.to_dict('records')
            
            # Validar campos obrigatórios
            campos_obrigatorios = REQUIRED_FIELDS.get(tipo_operacao, [])
            dados_validados = []
            erros = []
            
            for idx, linha in enumerate(dados, 1):
                erro = self._validar_linha(linha, campos_obrigatorios, tipo_operacao)
                
                if erro:
                    if ignorar_erros:
                        erros.append(f"Linha {idx}: {erro}")
                        continue
                    else:
                        raise CSVImportError(f"Linha {idx}: {erro}")
                
                dados_validados.append(linha)
            
            return {
                "sucesso": True,
                "total": len(dados),
                "validado": len(dados_validados),
                "erros": len(erros),
                "dados": dados_validados,
                "detalhes_erro": erros
            }
            
        except pd.errors.ParserError as e:
            logger.error(f"Erro ao fazer parse do CSV: {str(e)}")
            raise CSVImportError(f"Erro ao ler arquivo CSV: {str(e)}")
        except Exception as e:
            logger.error(f"Erro ao importar CSV: {str(e)}")
            raise CSVImportError(f"Erro ao importar CSV: {str(e)}")
    
    def _validar_linha(self, linha: Dict[str, Any], campos_obrigatorios: List[str], tipo_operacao: str) -> Optional[str]:
        """Valida uma linha de CSV"""
        # Verificar campos obrigatórios
        for campo in campos_obrigatorios:
            if campo not in linha or pd.isna(linha[campo]) or linha[campo] == '':
                return f"Campo obrigatório '{campo}' está vazio"
        
        # Validações específicas por tipo
        if tipo_operacao == "ADD" or tipo_operacao == "EDIT":
            try:
                preco = float(linha.get("preco", 0))
                if preco < 0:
                    return "Preço não pode ser negativo"
            except (ValueError, TypeError):
                return "Preço deve ser um número válido"
        
        if tipo_operacao == "UPDATE_STOCK":
            try:
                quantidade = int(linha.get("quantidade", 0))
                if quantidade < 0:
                    return "Quantidade não pode ser negativa"
            except (ValueError, TypeError):
                return "Quantidade deve ser um número inteiro"
        
        return None
    
    def exportar_para_csv(self, dados: List[Dict[str, Any]], nome_arquivo: str, colunas: Optional[List[str]] = None) -> str:
        """Exporta dados para CSV"""
        try:
            if not dados:
                raise CSVExportError("Nenhum dado para exportar")
            
            # Sanitizar nome do arquivo
            nome_arquivo = nome_arquivo.replace(' ', '_').replace('/', '_')
            if not nome_arquivo.endswith('.csv'):
                nome_arquivo += '.csv'
            
            caminho = self.export_folder / nome_arquivo
            
            # Usar colunas especificadas ou todas as chaves do primeiro registro
            if colunas is None:
                colunas = list(dados[0].keys())
            
            df = pd.DataFrame(dados)
            df = df[[col for col in colunas if col in df.columns]]
            df.to_csv(caminho, index=False, encoding='utf-8')
            
            logger.info(f"Arquivo exportado: {nome_arquivo}")
            return str(caminho)
            
        except Exception as e:
            logger.error(f"Erro ao exportar CSV: {str(e)}")
            raise CSVExportError(f"Erro ao exportar para CSV: {str(e)}")
    
    def salvar_arquivo_csv(self, conteudo: bytes, nome_arquivo: str) -> str:
        """Salva arquivo CSV no diretório de upload"""
        try:
            if not nome_arquivo.endswith('.csv'):
                nome_arquivo += '.csv'
            
            caminho = self.upload_folder / nome_arquivo
            
            with open(caminho, 'wb') as f:
                f.write(conteudo)
            
            logger.info(f"Arquivo salvo: {nome_arquivo}")
            return str(caminho)
            
        except Exception as e:
            logger.error(f"Erro ao salvar arquivo CSV: {str(e)}")
            raise CSVImportError(f"Erro ao salvar arquivo: {str(e)}")
    
    def gerar_template_csv(self, tipo_operacao: str) -> str:
        """Gera um template CSV baseado no tipo de operação"""
        templates = {
            "ADD": ["sku", "nome", "descricao", "preco", "categoria", "imagem_url"],
            "EDIT": ["sku", "nome", "descricao", "preco"],
            "DELETE": ["sku"],
            "UPDATE_SKU": ["id", "novo_sku"],
            "UPDATE_STOCK": ["sku", "quantidade"]
        }
        
        colunas = templates.get(tipo_operacao, [])
        
        # Criar DataFrame com headers
        df = pd.DataFrame(columns=colunas)
        
        nome_arquivo = f"template_{tipo_operacao.lower()}.csv"
        caminho = self.export_folder / nome_arquivo
        
        df.to_csv(caminho, index=False, encoding='utf-8')
        
        return str(caminho)
    
    def listar_uploads(self) -> List[Dict[str, Any]]:
        """Lista todos os arquivos de upload"""
        arquivos = []
        
        for arquivo in self.upload_folder.glob('*.csv'):
            stat = arquivo.stat()
            arquivos.append({
                "nome": arquivo.name,
                "tamanho": stat.st_size,
                "modificado": stat.st_mtime
            })
        
        return sorted(arquivos, key=lambda x: x["modificado"], reverse=True)
    
    def listar_exports(self) -> List[Dict[str, Any]]:
        """Lista todos os arquivos de export"""
        arquivos = []
        
        for arquivo in self.export_folder.glob('*.csv'):
            stat = arquivo.stat()
            arquivos.append({
                "nome": arquivo.name,
                "tamanho": stat.st_size,
                "modificado": stat.st_mtime
            })
        
        return sorted(arquivos, key=lambda x: x["modificado"], reverse=True)
    
    def deletar_arquivo(self, nome_arquivo: str, tipo: str = "upload") -> bool:
        """Deleta um arquivo"""
        pasta = self.upload_folder if tipo == "upload" else self.export_folder
        caminho = pasta / nome_arquivo
        
        if not caminho.exists():
            raise CSVExportError(f"Arquivo não encontrado: {nome_arquivo}")
        
        try:
            caminho.unlink()
            logger.info(f"Arquivo deletado: {nome_arquivo}")
            return True
        except Exception as e:
            logger.error(f"Erro ao deletar arquivo: {str(e)}")
            raise CSVExportError(f"Erro ao deletar arquivo: {str(e)}")
