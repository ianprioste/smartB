"""Rotas para CSV import/export"""
from fastapi import APIRouter, HTTPException, UploadFile, File
import logging
from typing import List
from app.models.schemas import CSVImportRequest, ExportRequest
from app.services.csv_service import CSVService
from app.services.produto_service import ProdutoService
from app.core.exceptions import CSVImportError, CSVExportError

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/csv", tags=["CSV"])

csv_service = CSVService()
produto_service = ProdutoService()


@router.post("/importar")
async def importar_csv(tipo_operacao: str, ignorar_erros: bool = False):
    """Importa dados do CSV e processa"""
    try:
        # Listar arquivos disponíveis
        uploads = csv_service.listar_uploads()
        if not uploads:
            raise CSVImportError("Nenhum arquivo de upload disponível")
        
        # Usar o arquivo mais recente
        arquivo = uploads[0]["nome"]
        
        # Importar e validar
        resultado_import = csv_service.importar_csv(arquivo, tipo_operacao, ignorar_erros)
        
        if resultado_import["validado"] > 0:
            # Processar os dados validados
            if tipo_operacao == "adicionar":
                resultado = produto_service.criar_produto_em_massa(resultado_import["dados"])
            elif tipo_operacao == "editar":
                resultado = produto_service.editar_produto_em_massa(resultado_import["dados"])
            elif tipo_operacao == "deletar":
                skus = [p.get("sku") for p in resultado_import["dados"]]
                resultado = produto_service.deletar_produto_em_massa(skus)
            elif tipo_operacao == "atualizar_estoque":
                resultado = produto_service.atualizar_estoque_em_massa(resultado_import["dados"])
            elif tipo_operacao == "atualizar_sku":
                resultado = produto_service.atualizar_sku_em_massa(resultado_import["dados"])
            else:
                raise CSVImportError(f"Tipo de operação inválido: {tipo_operacao}")
            
            return {
                "status": "sucesso",
                "arquivo": arquivo,
                "total_validado": resultado_import["validado"],
                "resultado_processamento": resultado,
                "erros_validacao": resultado_import["detalhes_erro"]
            }
        else:
            raise CSVImportError(f"Nenhuma linha válida para processar. Erros: {resultado_import['detalhes_erro']}")
    
    except CSVImportError as e:
        logger.error(f"Erro ao importar CSV: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Erro ao processar CSV: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/upload")
async def upload_csv(file: UploadFile = File(...)):
    """Faz upload de arquivo CSV"""
    try:
        if not file.filename.endswith('.csv'):
            raise CSVImportError("Apenas arquivos CSV são permitidos")
        
        conteudo = await file.read()
        csv_service.salvar_arquivo_csv(conteudo, file.filename)
        
        return {
            "status": "sucesso",
            "arquivo": file.filename,
            "tamanho": len(conteudo)
        }
    except CSVImportError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Erro ao fazer upload: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/uploads")
async def listar_uploads():
    """Lista todos os arquivos de upload"""
    try:
        arquivos = csv_service.listar_uploads()
        return {"arquivos": arquivos, "total": len(arquivos)}
    except Exception as e:
        logger.error(f"Erro ao listar uploads: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/exports")
async def listar_exports():
    """Lista todos os arquivos de export"""
    try:
        arquivos = csv_service.listar_exports()
        return {"arquivos": arquivos, "total": len(arquivos)}
    except Exception as e:
        logger.error(f"Erro ao listar exports: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/exportar")
async def exportar_dados(request: ExportRequest):
    """Exporta dados para CSV"""
    try:
        # Obter dados baseado no tipo
        if request.tipo == "estoque":
            # Listar todos os produtos e pegar estoque
            resultado = produto_service.bling.listar_produtos()
            produtos = resultado.get("data", [])
            
            dados = []
            for p in produtos:
                dados.append({
                    "sku": p.get("numero"),
                    "nome": p.get("descricao"),
                    "estoque": p.get("estoque", 0)
                })
        elif request.tipo == "produtos":
            resultado = produto_service.bling.listar_produtos()
            dados = resultado.get("data", [])
        else:
            raise CSVExportError(f"Tipo de export inválido: {request.tipo}")
        
        # Gerar arquivo
        nome_arquivo = f"export_{request.tipo}_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}"
        caminho = csv_service.exportar_para_csv(dados, nome_arquivo)
        
        return {
            "status": "sucesso",
            "arquivo": caminho,
            "total_registros": len(dados)
        }
    
    except CSVExportError as e:
        logger.error(f"Erro ao exportar: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Erro ao processar export: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/template/{tipo_operacao}")
async def gerar_template(tipo_operacao: str):
    """Gera um template CSV para importação"""
    try:
        caminho = csv_service.gerar_template_csv(tipo_operacao)
        return {
            "status": "sucesso",
            "arquivo": caminho,
            "tipo": tipo_operacao
        }
    except Exception as e:
        logger.error(f"Erro ao gerar template: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/upload/{nome_arquivo}")
async def deletar_upload(nome_arquivo: str):
    """Deleta um arquivo de upload"""
    try:
        csv_service.deletar_arquivo(nome_arquivo, "upload")
        return {"status": "sucesso", "mensagem": f"Arquivo {nome_arquivo} deletado"}
    except CSVExportError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Erro ao deletar arquivo: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/export/{nome_arquivo}")
async def deletar_export(nome_arquivo: str):
    """Deleta um arquivo de export"""
    try:
        csv_service.deletar_arquivo(nome_arquivo, "export")
        return {"status": "sucesso", "mensagem": f"Arquivo {nome_arquivo} deletado"}
    except CSVExportError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Erro ao deletar arquivo: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# Importar pandas para timestamp
import pandas as pd
