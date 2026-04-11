# SmartBling - Exemplos de Uso

## 📌 Casos de Uso Práticos

### Caso 1: Importar 100 Produtos Novos

**Arquivo CSV (adicionar_produtos.csv):**
```csv
sku,nome,descricao,preco,categoria,imagem_url
SKU-001-001,Produto Eletrônico 1,Descrição completa do produto,299.90,Eletrônicos,https://...
SKU-001-002,Produto Eletrônico 2,Descrição completa do produto,399.90,Eletrônicos,https://...
SKU-002-001,Produto de Casa 1,Descrição completa do produto,49.90,Casa,https://...
```

**Procedimento:**
1. Vá para "Importar/Exportar" → "Importar"
2. Selecione "Adicionar Produtos"
3. Upload do arquivo CSV
4. Clique em "Importar"
5. Sistema valida e insere na Bling
6. Retorna relatório com sucesso/erro

### Caso 2: Atualizar Estoque em Lote

**Arquivo CSV (atualizar_estoque.csv):**
```csv
sku,quantidade,tipo_operacao
SKU-001-001,150,substituir
SKU-001-002,75,somar
SKU-002-001,30,subtrair
SKU-002-002,0,substituir
```

**Resultado esperado:**
- SKU-001-001: Estoque = 150
- SKU-001-002: Estoque = Anterior + 75
- SKU-002-001: Estoque = Anterior - 30
- SKU-002-002: Estoque = 0 (descontinuado)

### Caso 3: Editar Descrição e Preço de Produtos

**Arquivo CSV (editar_produtos.csv):**
```csv
sku,nome,descricao,preco
SKU-001-001,Produto Eletrônico 1,Nova descrição melhorada,349.90
SKU-001-002,Produto Eletrônico 2,Descrição atualizada,449.90
SKU-002-001,Produto de Casa 1,Descrição revisada,59.90
```

**Procedimento:**
1. Selecionar "Editar Produtos"
2. Upload do CSV
3. Importar
4. Produtos são atualizados mantendo outros campos

### Caso 4: Referenciar Produtos em Composição

**Adicionar Componentes a um Produto:**

```json
{
  "sku": "COMBO-001",
  "componentes": [
    {
      "item_id": "SKU-001-001",
      "quantidade": 2,
      "valor_unitario": 299.90
    },
    {
      "item_id": "SKU-001-002",
      "quantidade": 1,
      "valor_unitario": 399.90
    }
  ],
  "tipo_operacao": "editar"
}
```

Resultado: Produto COMBO-001 é composto por 2x SKU-001-001 e 1x SKU-001-002

### Caso 5: Migração de SKU

**Arquivo CSV (migrar_sku.csv):**
```csv
id,novo_sku
12345,SKU-NOVO-001
12346,SKU-NOVO-002
12347,SKU-NOVO-003
```

**Resultado:** Todos os IDs são renumerados com novos SKUs

### Caso 6: Deletar Produtos Descontinuados

**Arquivo CSV (deletar_produtos.csv):**
```csv
sku
SKU-DESCONTINUADO-001
SKU-DESCONTINUADO-002
SKU-DESCONTINUADO-003
```

**Procedimento:**
1. Selecionar "Deletar Produtos"
2. Upload do CSV
3. Importar
4. Produtos são deletados da Bling

## 🔄 Integração via API

### Exemplo com Python

```python
import requests

BASE_URL = "http://localhost:8000/api"
API_KEY_HEADER = {"Authorization": "Bearer sua_api_key"}

# Criar múltiplos produtos
def criar_produtos_em_massa():
    url = f"{BASE_URL}/produtos/em-massa/criar"
    dados = {
        "tipo_operacao": "adicionar",
        "produtos": [
            {
                "sku": "SKU-001",
                "nome": "Produto 1",
                "descricao": "Descrição",
                "preco": 99.90,
                "estoque": 100
            },
            {
                "sku": "SKU-002",
                "nome": "Produto 2",
                "descricao": "Descrição",
                "preco": 149.90,
                "estoque": 50
            }
        ],
        "ignorar_erros": False
    }
    
    response = requests.post(url, json=dados)
    print(response.json())

# Atualizar estoque em massa
def atualizar_estoque():
    url = f"{BASE_URL}/produtos/estoque/atualizar-em-massa"
    dados = [
        {"sku": "SKU-001", "quantidade": 150, "tipo_operacao": "substituir"},
        {"sku": "SKU-002", "quantidade": 50, "tipo_operacao": "somar"}
    ]
    
    response = requests.post(url, json=dados)
    print(response.json())

# Exportar dados
def exportar_estoque():
    url = f"{BASE_URL}/csv/exportar"
    dados = {"tipo": "estoque"}
    
    response = requests.post(url, json=dados)
    print(response.json())

if __name__ == "__main__":
    criar_produtos_em_massa()
    atualizar_estoque()
    exportar_estoque()
```

### Exemplo com Node.js

```javascript
const axios = require('axios');

const api = axios.create({
  baseURL: 'http://localhost:8000/api'
});

// Criar produtos em massa
async function criarProdutosEmMassa() {
  try {
    const response = await api.post('/produtos/em-massa/criar', {
      tipo_operacao: 'adicionar',
      produtos: [
        {
          sku: 'SKU-001',
          nome: 'Produto 1',
          descricao: 'Descrição',
          preco: 99.90,
          estoque: 100
        }
      ],
      ignorar_erros: false
    });
    
    console.log(response.data);
  } catch (error) {
    console.error('Erro:', error.response.data);
  }
}

// Upload de arquivo
async function uploadCSV(file) {
  try {
    const formData = new FormData();
    formData.append('file', file);
    
    const response = await api.post('/csv/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    });
    
    console.log(response.data);
  } catch (error) {
    console.error('Erro:', error.response.data);
  }
}

criarProdutosEmMassa();
```

## 📊 Relatórios e Analytics

### Exportar para Análise

```bash
# Exportar estoque atual
# Salva em exports/export_estoque_YYYYMMDD_HHMMSS.csv

# Exportar todos os produtos
# Salva em exports/export_produtos_YYYYMMDD_HHMMSS.csv
```

**Usar os dados exportados para:**
- Análise em Excel/Power BI
- Backup de dados
- Sincronização com outros sistemas
- Relatórios de inventário

## ⚠️ Tratamento de Erros

### Erro: SKU Duplicado
```
Solução: Verificar CSV para duplicatas e remover
```

### Erro: Preço Inválido
```
Solução: Verificar se o preço está em formato válido (número com até 2 casas decimais)
```

### Erro: Estoque Negativo
```
Solução: Não é permitido estoque negativo. Use tipo_operacao "subtrair" com cuidado
```

### Erro: Campo Obrigatório
```
Solução: Verificar template e adicionar campo faltante
```

## 🎯 Dicas de Produtividade

1. **Use Templates**: Baixe templates para cada tipo de operação
2. **Validação em Lote**: Sistema valida todos os dados antes de processar
3. **Ignorar Erros**: Use `ignorar_erros=True` para continuar mesmo com erros
4. **Backups**: Exporte dados regularmente
5. **Agendamento**: Crie scripts para automatizar operações recorrentes

---

**Última atualização**: 2024
