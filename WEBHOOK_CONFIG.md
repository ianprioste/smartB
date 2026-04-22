# Configuração Manual de Webhooks no Bling

## Informações Rápidas

### 1. Pedidos de Vendas (Orders)
```
URL: http://localhost:8000/webhooks/bling/orders
Nome: SmartBling Order Sync
Evento: pedido.atualizado
Módulo: 98310 (Pedidos de Vendas)
```

### 2. Produtos (Products)
```
URL: http://localhost:8000/webhooks/bling/products
Nome: SmartBling Product Sync
Evento: produto.atualizado
```

### 3. Estoque (Stock)
```
URL: http://localhost:8000/webhooks/bling/stock
Nome: SmartBling Stock Sync
Evento: estoque.atualizado
```

### 4. Fornecedores (Suppliers)
```
URL: http://localhost:8000/webhooks/bling/suppliers
Nome: SmartBling Supplier Sync
Evento: fornecedor.atualizado
```

---

## Tabela de Configuração Completa

| Recurso | URL | Nome | Evento | Módulo |
|---------|-----|------|--------|--------|
| **Pedidos** | http://localhost:8000/webhooks/bling/orders | SmartBling Order Sync | pedido.atualizado | 98310 |
| **Produtos** | http://localhost:8000/webhooks/bling/products | SmartBling Product Sync | produto.atualizado | - |
| **Estoque** | http://localhost:8000/webhooks/bling/stock | SmartBling Stock Sync | estoque.atualizado | - |
| **Fornecedores** | http://localhost:8000/webhooks/bling/suppliers | SmartBling Supplier Sync | fornecedor.atualizado | - |

---

## Passo a Passo no Bling

### Para cada webhook:

1. **Acesse a conta Bling**
2. Vá para **Configurações → Integrações → Webhooks**
3. Clique em **+ Novo Webhook**
4. Preencha com os dados da tabela acima
5. **Salve** o webhook

---

## Para Produção

Se estiver em um servidor remoto, substitua `http://localhost:8000` por:
```
https://seu-dominio.com
```

Exemplo:
```
https://seu-dominio.com/webhooks/bling/orders
https://seu-dominio.com/webhooks/bling/products
https://seu-dominio.com/webhooks/bling/stock
https://seu-dominio.com/webhooks/bling/suppliers
```

Certifique-se de que:
- O firewall permite conexões de entrada
- As URLs são acessíveis publicamente
- Configure `PUBLIC_API_URL` no `.env`

---

## Registrando via API (Recomendado)

Se preferir registrar todos de uma vez:

```bash
curl -X POST http://localhost:8000/webhooks/bling/register-all-webhooks
```

Ou registrar um por um:

```bash
# Pedidos
curl -X POST http://localhost:8000/webhooks/bling/register-order-webhook

# Produtos
curl -X POST http://localhost:8000/webhooks/bling/register-product-webhook

# Estoque
curl -X POST http://localhost:8000/webhooks/bling/register-stock-webhook

# Fornecedores
curl -X POST http://localhost:8000/webhooks/bling/register-supplier-webhook
```

---

## Verificando Webhooks Registrados

```powershell
.\register-bling-webhook.ps1 -Command list
```

Ou via curl:
```bash
curl http://localhost:8000/webhooks/bling/list-webhooks
```

---

## Como Funciona

```
Bling → App (Webhook POST)
   ↓
App recebe a notificação
   ↓
App sincroniza localmente
   ↓
Status/Dados atualizados em tempo real
```

Cada webhook funciona de forma independente. Quando dados mudam no Bling, a notificação é enviada para seu app.
