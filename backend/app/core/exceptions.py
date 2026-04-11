"""Exceções customizadas da aplicação"""


class BlingException(Exception):
    """Exceção base para erros da API Bling"""
    pass


class BlingAuthenticationError(BlingException):
    """Erro de autenticação com API Bling"""
    pass


class BlingValidationError(BlingException):
    """Erro de validação de dados"""
    pass


class BlingNotFoundError(BlingException):
    """Recurso não encontrado"""
    pass


class BlingServerError(BlingException):
    """Erro no servidor Bling"""
    pass


class CSVImportError(Exception):
    """Erro ao importar arquivo CSV"""
    pass


class CSVExportError(Exception):
    """Erro ao exportar para CSV"""
    pass


class ProductNotFoundError(Exception):
    """Produto não encontrado"""
    pass


class InvalidOperationError(Exception):
    """Operação inválida"""
    pass
