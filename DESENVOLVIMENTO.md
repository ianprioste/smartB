# SmartBling - Guia de Desenvolvimento

## 🛠️ Setup Inicial

### 1. Clonar o Repositório
```bash
git clone <repo-url>
cd smartBling
```

### 2. Backend Setup

```bash
cd backend

# Criar ambiente virtual
python -m venv venv

# Ativar (Windows)
venv\Scripts\activate

# Ativar (Linux/Mac)
source venv/bin/activate

# Instalar dependências
pip install -r requirements.txt

# Copiar variáveis de ambiente
copy .env.example .env

# Configurar
python main.py configurar

# Executar
python main.py run
```

### 3. Frontend Setup

```bash
cd frontend

# Instalar dependências
npm install

# Executar em desenvolvimento
npm run dev

# Build para produção
npm run build
```

## 📝 Arquitetura

### Backend (FastAPI)

```
main.py (entry point)
├── app/
│   ├── core/
│   │   ├── config.py (Settings)
│   │   ├── constants.py (Constantes)
│   │   └── exceptions.py (Custom exceptions)
│   ├── models/
│   │   └── schemas.py (Pydantic models)
│   ├── services/
│   │   ├── bling_service.py (Integração API Bling)
│   │   ├── csv_service.py (Manipulação CSV)
│   │   └── produto_service.py (Lógica de negócio)
│   └── routes/
│       ├── produtos.py (Endpoints de produtos)
│       ├── csv.py (Endpoints CSV)
│       └── config.py (Endpoints de configuração)
```

### Frontend (React)

```
App.jsx (entry point)
├── pages/
│   ├── Dashboard.jsx
│   ├── Produtos.jsx
│   ├── ImportarExportar.jsx
│   └── Configuracoes.jsx
├── components/
├── services/
│   └── api.js (Cliente axios)
└── hooks/
```

## 🔄 Fluxo de Dados

### Importação de CSV
1. Usuário faz upload do arquivo → `POST /api/csv/upload`
2. Arquivo é salvo em `backend/uploads/`
3. Usuário seleciona tipo de operação
4. Sistema importa e valida dados → `POST /api/csv/importar`
5. Dados validados são processados via serviço apropriado
6. Resultado é retornado ao frontend

### Operações em Massa
1. Dados são enviados para rota apropriada
2. `ProdutoService` processa cada item
3. Erros são capturados individualmente
4. Resultado consolidado é retornado com sucesso/erro por item

### Integração Bling
1. `BlingAPIService` faz requisições para API Bling
2. Respostas são parseadas e tratadas
3. Erros específicos (401, 404, 500) são mapeados para exceções
4. Dados são transformados para formato local

## 🧪 Testando a API

### Com curl

```bash
# Listar produtos
curl http://localhost:8000/api/produtos

# Validar Bling
curl -X POST http://localhost:8000/api/bling/validar

# Criar produto em massa
curl -X POST http://localhost:8000/api/produtos/em-massa/criar \
  -H "Content-Type: application/json" \
  -d '{
    "tipo_operacao": "adicionar",
    "produtos": [
      {"sku": "SKU001", "nome": "Produto 1", "preco": 99.90}
    ],
    "ignorar_erros": false
  }'
```

### Com Postman
1. Importe a coleção de endpoints
2. Configure as variáveis de ambiente
3. Execute os testes

## 📊 Modelos de Dados

### Produto
```python
{
  "sku": "SKU001",
  "nome": "Nome do Produto",
  "descricao": "Descrição completa",
  "preco": 99.90,
  "estoque": 100,
  "categoria": "Eletrônicos",
  "componentes": [
    {
      "id": "COMP001",
      "quantidade": 2,
      "valor_unitario": 50.00
    }
  ]
}
```

### Resultado de Processamento
```python
{
  "status": "sucesso",
  "total_processado": 10,
  "sucesso": 8,
  "erro": 2,
  "detalhes": [
    {
      "indice": 1,
      "sku": "SKU001",
      "status": "sucesso"
    },
    {
      "indice": 2,
      "sku": "SKU002",
      "status": "erro",
      "mensagem": "SKU duplicado"
    }
  ]
}
```

## 🐛 Debug

### Backend
```python
# Adicionar logs
import logging
logger = logging.getLogger(__name__)
logger.info("Mensagem de debug")
```

### Frontend
```javascript
// Console do browser
console.log(data)

// React DevTools
// Extension: React Developer Tools
```

## 🚀 Deploy

### Preparação para Produção

```bash
# Backend
# 1. Criar .env com dados de produção
# 2. Instalar dependências
pip install -r requirements.txt

# 3. Usar servidor ASGI como gunicorn
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:8000 main:app

# Frontend
# 1. Build
npm run build

# 2. Servir com nginx ou S3
# Arquivo estático em dist/
```

### Dockerfile (Exemplo)

```dockerfile
FROM python:3.11

WORKDIR /app

COPY backend/requirements.txt .
RUN pip install -r requirements.txt

COPY backend .

CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:8000", "main:app"]
```

## 📚 Recursos Úteis

- [FastAPI Docs](https://fastapi.tiangolo.com/)
- [React Docs](https://react.dev/)
- [Ant Design](https://ant.design/)
- [Bling API](https://bling.com.br/api)

## ✅ Checklist de Desenvolvimento

- [ ] Configurar ambiente local
- [ ] Testar conexão Bling
- [ ] Implementar autenticação de usuários
- [ ] Adicionar testes automatizados
- [ ] Implementar paginação no frontend
- [ ] Adicionar cache de dados
- [ ] Configurar logs centralizados
- [ ] Implementar rate limiting
- [ ] Adicionar validação mais rigorosa
- [ ] Documentar endpoints com Swagger
- [ ] Deploy em ambiente de teste
- [ ] Deploy em produção

## 🤝 Commits Recomendados

```
feat: Adicionar suporte a importação CSV
fix: Corrigir validação de estoque negativo
refactor: Melhorar tratamento de erros
docs: Atualizar README
test: Adicionar testes de integração
```

---

**Última atualização**: 2024
