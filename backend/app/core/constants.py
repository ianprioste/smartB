"""Constantes da aplicação"""

# Tipos de operação
OPERATION_TYPES = {
    "ADD": "adicionar",
    "EDIT": "editar",
    "DELETE": "deletar",
    "UPDATE_SKU": "atualizar_sku",
    "UPDATE_STOCK": "atualizar_estoque"
}

# Status de processamento
PROCESSING_STATUS = {
    "PENDING": "pendente",
    "PROCESSING": "processando",
    "SUCCESS": "sucesso",
    "ERROR": "erro"
}

# Campos obrigatórios por operação
REQUIRED_FIELDS = {
    "ADD": ["nome", "sku", "preco"],
    "EDIT": ["sku", "nome", "preco"],
    "DELETE": ["sku"],
    "UPDATE_SKU": ["id", "novo_sku"],
    "UPDATE_STOCK": ["sku", "quantidade"]
}

# Campos de composição de produtos
COMPOSITION_FIELDS = ["item_id", "quantidade", "valor_unitario"]

# Formato de retorno da API Bling
BLING_RESPONSE_FORMAT = "json"
