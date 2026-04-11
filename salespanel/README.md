# SalesPanel

SalesPanel e uma camada de interface amigavel para o ERP Bling, focada em consulta de vendas, produtos e estoque, com classificacao de pedidos por tags.

## Stack

- Frontend: Next.js + React + TypeScript + TailwindCSS + TanStack Query
- Backend: NestJS + Prisma + OAuth2 Bling API v3
- Banco: PostgreSQL

## Estrutura

- apps/web: dashboard e telas operacionais
- apps/api: API intermediaria, sincronizacao e regras de negocio
- infra: apoio de infraestrutura

## Como rodar

1. Garanta um PostgreSQL local em execucao.

2. Instale dependencias na raiz:

```bash
cd ..
npm install
```

3. Configure variaveis de ambiente:

- Copie `apps/api/.env.example` para `apps/api/.env`
- Copie `apps/web/.env.example` para `apps/web/.env.local`

4. Gere o cliente Prisma e aplique schema:

```bash
npm run db:push
npm run db:seed
```

5. Rode frontend e backend:

```bash
npm run dev
```

## Release 1 implementada

- Dashboard com indicadores e ultimos pedidos
- Tela de pedidos com filtros, paginacao e tags
- Tela de produtos
- Tela de estoque com alerta visual
- CRUD de tags
- Exportacao CSV de pedidos detalhados e vendas por produto
- OAuth2 com Bling (estrutura) + sincronizacao manual
- Logs de sincronizacao
- Perfis: Administrador e Operador
