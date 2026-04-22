# Sincronização de Status via Webhook

## Visão Geral

O app agora pode receber atualizações de status diretamente do Bling via webhook. Quando você altera um status no Bling, a mudança é automaticamente sincronizada para o app.

## Como Funciona

1. **Webhook Registrado**: O app registra um webhook no Bling
2. **Mudança no Bling**: Você atualiza o status de um pedido no Bling
3. **Notificação**: Bling envia uma requisição POST para `/webhooks/bling/orders`
4. **Sincronização**: O app recebe a notificação e atualiza o status localmente

## Configuração

### 1. Configure a URL Pública (Importante!)

Para que o Bling possa enviar webhooks para seu app, você precisa configurar a URL pública onde o backend está acessível.

No arquivo `.env` (ou variáveis de ambiente), adicione:

```bash
PUBLIC_API_URL=http://seu-dominio.com
# Exemplo para desenvolvimento local:
PUBLIC_API_URL=http://localhost:8000
```

### 2. Registre o Webhook

Depois de reiniciar o backend, use um dos métodos abaixo para registrar o webhook:

#### Opção A: Script PowerShell (Recomendado)

```powershell
.\register-bling-webhook.ps1 -Command list      # Listar webhooks
.\register-bling-webhook.ps1 -Command register  # Registrar novo webhook
.\register-bling-webhook.ps1 -Command test      # Testar webhook
```

#### Opção B: curl

```bash
# Listar webhooks
curl -X GET http://localhost:8000/webhooks/bling/list-webhooks

# Registrar webhook
curl -X POST http://localhost:8000/webhooks/bling/register-order-webhook

# Testar webhook
curl -X POST http://localhost:8000/webhooks/bling/orders \
  -H "Content-Type: application/json" \
  -d '{
    "data": {
      "id": 1128,
      "numero": "1128",
      "situacao": {"id": 6, "nome": "Em aberto"},
      "totalVenda": 100.00
    }
  }'
```

#### Opção C: Postman

1. Importe as rotas de webhook na coleção do Postman
2. Use a rota `[POST] /webhooks/bling/register-order-webhook`
3. Envie a requisição

### 3. Verifique se está Funcionando

```powershell
.\register-bling-webhook.ps1 -Command test
```

Você deve receber a resposta: `HTTP 202 - Accepted`

## Fluxo de Sincronização

### Quando você atualiza no App

```
App → Bling (POST status)
Atualiza localmente (sempre sucesso)
```

### Quando você atualiza no Bling

```
Bling → App (Webhook POST)
App recebe a mudança
App atualiza o banco de dados
Status sincronizado!
```

## Limitações Conhecidas

- A sincronização é **apenas em um sentido** (Bling → App)
- Não é possível sincronizar do app para o Bling para o status "Em Aberto" no momento
- Use o webhook para receber atualizações do Bling

## Troubleshooting

### "PUBLIC_API_URL not configured"

**Solução**: Configure `PUBLIC_API_URL` no `.env` com a URL onde seu backend é acessível externamente.

### Webhook não recebe notificações

1. Verifique se o webhook foi registrado:
   ```powershell
   .\register-bling-webhook.ps1 -Command list
   ```

2. Verifique se a URL pública está correta e acessível:
   ```bash
   curl $PUBLIC_API_URL/webhooks/health
   ```

3. Veja os logs do webhook:
   - Acesse `POST /webhooks/health` para ver o status

### Erro ao registrar webhook

Se receber erro ao registrar:

```powershell
.\register-bling-webhook.ps1 -Command register
```

Possíveis causas:
- Token Bling expirado (reconecte na tela de configurações)
- URL pública inválida ou inacessível
- Bling API indisponível

## Monitoramento

### Ver status do webhook

```bash
curl http://localhost:8000/webhooks/health
```

Resposta exemplo:
```json
{
  "ok": true,
  "webhooks_enabled": true,
  "pending": 0,
  "processing": 0,
  "processed": 15,
  "failed": 0
}
```

## Exemplo: Fluxo Completo

1. **No Bling**: Você muda o pedido 1128 para "Atendido"
2. **Bling envia webhook**: POST `/webhooks/bling/orders` com dados do pedido
3. **App recebe**: O endpoint webhook processa a notificação
4. **App sincroniza**: Atualiza o status local para "Atendido"
5. **Você vê no App**: Ao recarregar a página, o status está "Atendido"

## Próximos Passos

- [ ] Registrar webhook (via script ou API)
- [ ] Testar webhook
- [ ] Fazer uma mudança no Bling
- [ ] Verificar se o app atualizou

---

**Nota**: Se você estiver em um servidor de produção, certifique-se de que a URL pública está correta e que o firewall permite conexões de entrada em `POST /webhooks/bling/orders`.
