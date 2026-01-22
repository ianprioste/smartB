# Sprint 2 - Governance Module

## 📋 O que foi entregue

Sprint 2 implementa a **base de governança** do sistema, habilitando as sprints seguintes (Products, Inventory, etc.) com uma estrutura limpa e validada.

### Backend (FastAPI)

#### 1. **Banco de Dados**
- Migrations Alembic para 3 novas tabelas:
  - `models`: Modelos com tamanhos permitidos
  - `colors`: Cores
  - `model_templates`: Templates de produtos Bling por modelo

#### 2. **APIs REST (8 endpoints)**

**Modelos** (`/config/models`)
- `GET /config/models` - Listar modelos (ativos por padrão)
- `POST /config/models` - Criar modelo
- `GET /config/models/{code}` - Detalhe
- `PUT /config/models/{code}` - Editar
- `DELETE /config/models/{code}` - Desativar

**Cores** (`/config/colors`)
- `GET /config/colors` - Listar
- `POST /config/colors` - Criar
- `GET /config/colors/{code}` - Detalhe
- `PUT /config/colors/{code}` - Editar
- `DELETE /config/colors/{code}` - Desativar

**Templates** (`/config/templates`)
- `GET /config/templates?model_code=CAM` - Listar templates
- `POST /config/templates` - Criar (valida produto no Bling)
- `GET /config/templates/{id}` - Detalhe
- `DELETE /config/templates/{id}` - Remover

**Busca Bling** (`/bling/products`)
- `GET /bling/products/search?q=...` - Buscar produtos
- `GET /bling/products/{id}` - Detalhe do produto

#### 3. **Validações**
- `allowed_sizes` não pode ser vazio, sem duplicados
- `size_order` deve ser subset de `allowed_sizes`
- `code` único por tenant
- Unicidade composta: `(tenant_id, model_code, template_kind)` para templates

#### 4. **Multi-tenant**
- Todos os repositories filtram por `tenant_id`
- Tenant padrão: `00000000-0000-0000-0000-000000000001` (Sprint 2)

#### 5. **Logs Estruturados**
- Request ID e tenant ID em todos os endpoints
- Erros padronizados com `code`, `message`, `details`

### Frontend (React)

#### 1. **Setup**
- Vite + React 18 com React Router
- CORS habilitado para localhost:8000

#### 2. **3 Páginas Admin**

**Modelos**
- Lista com filtro ativo/inativo
- Criar e editar modelo
- Interface de "chips" para adicionar/remover tamanhos
- Validação inline

**Cores**
- CRUD simples para código/nome
- Ativar/desativar

**Templates**
- Seletor de modelo
- Busca em tempo real de produtos Bling
- Seleção de tipo de template (BASE_PLAIN, STAMP, etc.)
- Exibe templates já configurados
- Ao salvar, backend valida produto no Bling

#### 3. **Layout Admin**
- Header com navegação entre páginas
- Dark theme para header (#333)
- Tabelas responsivas
- Formulários com validação

---

## 🚀 Como Usar

### Backend

#### 1. Aplicar Migrations
```bash
cd backend
alembic upgrade head
```

#### 2. Rodar Servidor
```bash
python run.py
# API em http://localhost:8000
# Swagger: http://localhost:8000/docs
```

#### 3. Testar Endpoints (exemplos)
```bash
# Criar modelo
curl -X POST http://localhost:8000/config/models \
  -H "Content-Type: application/json" \
  -d '{"code":"CAM","name":"Camiseta","allowed_sizes":["P","M","G","GG"]}'

# Criar cor
curl -X POST http://localhost:8000/config/colors \
  -H "Content-Type: application/json" \
  -d '{"code":"BR","name":"Branca"}'

# Listar modelos
curl http://localhost:8000/config/models

# Buscar produto Bling
curl "http://localhost:8000/bling/products/search?q=camiseta"

# Criar template
curl -X POST http://localhost:8000/config/templates \
  -H "Content-Type: application/json" \
  -d '{"model_code":"CAM","template_kind":"BASE_PLAIN","bling_product_id":12345}'
```

### Frontend

#### 1. Instalar Dependências
```bash
cd frontend
npm install
```

#### 2. Rodar Dev Server
```bash
npm run dev
# Acesse http://localhost:5173
```

#### 3. Build para Produção
```bash
npm run build
# Outputs: frontend/dist/
```

---

## 📚 Estrutura de Arquivo

```
backend/
  ├── app/
  │   ├── models/
  │   │   ├── database.py        # ModelModel, ColorModel, ModelTemplateModel
  │   │   ├── schemas.py         # Pydantic requests/responses
  │   │   └── enums.py          # TemplateKindEnum
  │   ├── api/
  │   │   ├── config_models.py
  │   │   ├── config_colors.py
  │   │   ├── config_templates.py
  │   │   └── bling_products.py
  │   ├── repositories/
  │   │   ├── model_repo.py
  │   │   ├── color_repo.py
  │   │   └── model_template_repo.py
  │   └── main.py               # Inclui novos routers
  └── alembic/versions/
      └── 002_sprint2_governance.py

frontend/
  ├── src/
  │   ├── pages/admin/
  │   │   └── AdminPages.jsx      # 3 componentes (Models, Colors, Templates)
  │   ├── styles/
  │   │   └── admin.css           # Estilos mínimos
  │   ├── App.jsx                 # Routing
  │   └── main.jsx
  ├── index.html
  ├── package.json
  └── vite.config.js
```

---

## ✅ Critérios de Aceite

- [x] Consigo cadastrar CAM com allowed_sizes ["P","M","G","GG","XG"]
- [x] Validação impede duplicados e size_order fora do allowed
- [x] Consigo inativar e listar modelos
- [x] Consigo cadastrar BR/PR/OW cores e editar
- [x] Consigo buscar produto no Bling pela UI
- [x] Backend valida bling_product_id e persiste bling_product_sku e name
- [x] Consigo ver templates já configurados
- [x] Todas as tabelas salvam e consultam por tenant_id
- [x] Migrations OK
- [x] Logs estruturados com request_id e tenant_id
- [x] Tokens **não** aparecem nos logs

---

## 🎯 Próximos Passos (Sprint 3+)

**Sprint 3: Products**
- Criar produtos no Bling usando template como base
- Validações SKU, nome, categoria
- Mapeamento de atributos (tamanho, cor → variações)

**Sprint 4: Inventory**
- Sincronizar estoque do Bling
- Webhooks para atualizações em tempo real
- Alertas de falta de estoque

**Sprint 5: Orders**
- Sincronizar pedidos do Bling
- Marcar como processado

**Sprint 6: UI Dashboard**
- React dashboard com charts
- Real-time logs
- Status de sincronizações

---

## 🔧 Troubleshooting

**Erro: "Model already exists"**
- Modelos têm chave única (tenant_id, code). Use PUT para editar, não POST.

**Erro: "Bling product not found"**
- Verifique que o product_id existe no Bling e token é válido.

**Frontend não consegue fazer requests**
- Verifique CORS em `app/main.py`: `allow_origins=["*"]` está habilitado.
- Se mudar para produção, configure origins específicas.

**Migration falha**
- Verifique se PostgreSQL está rodando: `docker-compose up -d`

---

**Status:** ✅ Sprint 2 Completa  
**Data:** 21 Jan 2026  
**Próxima:** Sprint 3 - Produtos
