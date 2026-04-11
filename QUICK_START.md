# 🚀 SmartBling - Quick Start

## 5 MINUTOS PARA COMEÇAR

### Pré-requisitos
- Python 3.8+
- Node.js 16+
- Git

### Passo 1: Clonar/Navegar para o Projeto
```bash
cd smartBling
```

### Passo 2: Setup Automático (RECOMENDADO)

#### Windows
```bash
setup.bat
```

#### Linux/Mac
```bash
bash setup.sh
```

### Passo 3: Configurar API Bling

**Terminal 1 - Backend:**
```bash
cd backend
venv\Scripts\activate  # Windows: venv\Scripts\activate
python main.py configurar
```

Digite sua chave de API Bling quando solicitado.

### Passo 4: Iniciar Serviços

**Terminal 1:**
```bash
cd backend
python main.py run
# Acesse: http://localhost:8000
# Docs: http://localhost:8000/docs
```

**Terminal 2:**
```bash
cd frontend
npm run dev
# Acesse: http://localhost:3000
```

### Pronto! 🎉

Acesse **http://localhost:3000** e comece a usar!

---

## 📋 PRIMEIROS PASSOS NA INTERFACE

### 1. Dashboard
- Veja estatísticas gerais
- Verifique status da conexão Bling

### 2. Produtos
- Visualize seus produtos
- Clique em "Novo Produto" para adicionar
- Use "Editar" e "Deletar" para gerenciar

### 3. Importar/Exportar
- **Importar**: Upload de CSV com suas operações
- **Exportar**: Download dos dados atuais
- **Templates**: Use templates pré-formatados

### 4. Configurações
- Configure sua chave de API Bling
- Verifique status da conexão
- Valide configurações

---

## 💡 EXEMPLOS RÁPIDOS

### Adicionar 10 Produtos
1. Vá para "Importar/Exportar" → "Importar"
2. Selecione "Adicionar Produtos"
3. Download o template
4. Preencha os dados
5. Upload e clique "Importar"

### Atualizar Estoque
1. Use o template "Atualizar Estoque"
2. Preencha SKU, quantidade e tipo
3. Upload e importar
4. ✅ Estoque atualizado!

### Exportar Dados
1. Vá para "Importar/Exportar" → "Exportar"
2. Clique "Exportar Estoque" ou "Exportar Produtos"
3. Arquivo é salvo automaticamente
4. Download e use em Excel/BI

---

## 🔧 TROUBLESHOOTING

### Porta 8000/3000 em Uso?
```bash
# Mudar porta backend
python main.py run --port 8001

# Mudar porta frontend
npm run dev -- --port 3001
```

### Erro de Conexão Bling?
1. Verificar chave de API em Configurações
2. Testar em: http://localhost:8000/api/bling/validar
3. Verificar se chave está correta

### CSV não Importa?
1. Usar templates fornecidos
2. Verificar se todos campos obrigatórios estão preenchidos
3. Verificar tipos de dados (número, texto, etc.)

---

## 📱 PRÓXIMAS AÇÕES

### Para Desenvolvimento
```bash
# Ver logs em tempo real
tail -f backend.log

# Executar testes (futura adição)
pytest backend/

# Code formatting
black backend/
```

### Para Produção
```bash
# Build frontend
cd frontend
npm run build

# Deploy com Docker
docker-compose up -d
```

---

## 📞 Precisa de Help?

1. **Documentação Completa**: [README.md](README.md)
2. **Arquitetura**: [DESENVOLVIMENTO.md](DESENVOLVIMENTO.md)
3. **Exemplos**: [EXEMPLOS.md](EXEMPLOS.md)
4. **Swagger API**: http://localhost:8000/docs

---

## ✨ Recursos Principais

| Recurso | Status |
|---------|--------|
| Dashboard | ✅ |
| Gerenciar Produtos | ✅ |
| Importar CSV | ✅ |
| Exportar CSV | ✅ |
| Atualizar Estoque | ✅ |
| Gerenciar Componentes | ✅ |
| Integração Bling | ✅ |
| Interface Web | ✅ |

---

## 🔌 Configuração do ngrok para OAuth2

### Expor o backend com ngrok (OAuth2 Bling v3)
- Se ainda não autenticou o ngrok: ngrok config add-authtoken SEU_AUTHTOKEN
- Inicie o backend (porta 8000) e, em outro terminal:
```bash
ngrok http 8000
```
- Copie a URL pública gerada (ex.: https://xxxxx.ngrok-free.app)
- Defina no backend/.env:
```env
BLING_REDIRECT_URI=https://xxxxx.ngrok-free.app/callback
```
- Reinicie o backend e rode:
```bash
python main.py configurar
```
- Abra o link de autorização exibido, autorize e cole o code no terminal.

---

**Bom uso! 🎉**

*SmartBling v1.0.0 - 2024*
