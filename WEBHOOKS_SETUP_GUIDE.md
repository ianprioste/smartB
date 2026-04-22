# 🎯 Webhooks Bling - Configuração Completa

Implementado suporte para sincronização automática de 4 recursos do Bling:

## 📦 Recursos Suportados

| Recurso | URL Webhook | Nome | Evento |
|---------|------------|------|--------|
| **Pedidos de Vendas** | `/webhooks/bling/orders` | SmartBling Order Sync | pedido.atualizado |
| **Produtos** | `/webhooks/bling/products` | SmartBling Product Sync | produto.atualizado |
| **Estoque** | `/webhooks/bling/stock` | SmartBling Stock Sync | estoque.atualizado |
| **Fornecedores** | `/webhooks/bling/suppliers` | SmartBling Supplier Sync | fornecedor.atualizado |

---

## 🚀 Forma Mais Rápida (Recomendado)

Use o endpoint para registrar todos os webhooks de uma vez:

```bash
curl -X POST http://localhost:8000/webhooks/bling/register-all-webhooks
```

Isso vai registrar automaticamente todos os 4 webhooks no Bling.

---

## 📋 Ou Configure Manualmente no Bling

Para cada webhook, siga este padrão no Bling:

1. Vá para: **Configurações → Integrações → Webhooks**
2. Clique em: **+ Novo Webhook**
3. Preencha:
   - **Nome**: Use o valor da coluna "Nome" acima
   - **URL**: Use `http://localhost:8000` + URL da coluna acima
   - **Evento**: Use o valor da coluna "Evento"
4. Clique em: **Salvar**

### Exemplo para Pedidos:
- Nome: `SmartBling Order Sync`
- URL: `http://localhost:8000/webhooks/bling/orders`
- Evento: `pedido.atualizado`

Repita o processo para Produtos, Estoque e Fornecedores.

---

## ✅ Verificação

Lista todos os webhooks registrados:

```bash
curl http://localhost:8000/webhooks/bling/list-webhooks
```

Ou via PowerShell:

```powershell
.\register-bling-webhook.ps1 -Command list
```

---

## 🔄 Como Funciona

Cada webhook funciona assim:

```
1. Dados mudam no Bling (ex: atualiza estoque)
   ↓
2. Bling envia POST para: http://localhost:8000/webhooks/bling/stock
   ↓
3. App recebe a notificação
   ↓
4. App sincroniza os dados localmente
   ↓
5. Dados aparecem atualizados em tempo real no app
```

---

## 🌐 Para Produção

Substitua `http://localhost:8000` pela URL pública do seu servidor:

```
https://seu-dominio.com/webhooks/bling/orders
https://seu-dominio.com/webhooks/bling/products
https://seu-dominio.com/webhooks/bling/stock
https://seu-dominio.com/webhooks/bling/suppliers
```

E configure no `.env`:
```bash
PUBLIC_API_URL=https://seu-dominio.com
```

---

## 📊 Endpoints Disponíveis

- `POST /webhooks/bling/register-all-webhooks` - Registra todos de uma vez
- `POST /webhooks/bling/register-order-webhook` - Registra webhook de pedidos
- `POST /webhooks/bling/register-product-webhook` - Registra webhook de produtos
- `POST /webhooks/bling/register-stock-webhook` - Registra webhook de estoque
- `POST /webhooks/bling/register-supplier-webhook` - Registra webhook de fornecedores
- `GET /webhooks/bling/list-webhooks` - Lista webhooks registrados
- `GET /webhooks/health` - Status dos webhooks

---

## 💡 Dica

Se algum webhook falhar ao registrar, você pode tentar registrar manualmente no Bling usando o método manual acima, ou verificar que:

1. O token Bling está ativo
2. A URL `PUBLIC_API_URL` está configurada corretamente
3. A URL é acessível publicamente (para produção)
