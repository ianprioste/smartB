# 🎬 PRIMEIRA EXECUÇÃO - SmartBling

## Pré-requisitos Instalados ✓

- [ ] Python 3.8+ instalado
- [ ] Node.js 16+ instalado
- [ ] Git instalado

---

## 🚀 WINDOWS - Procedimento Recomendado

### 1. Executar Setup (Automático)

```bash
cd smartBling
setup.bat
```

Aguarde a conclusão. Será criado:
- Ambiente virtual Python
- node_modules
- .env

---

## 🐧 LINUX / MAC - Procedimento Recomendado

### 1. Executar Setup (Automático)

```bash
cd smartBling
bash setup.sh
```

---

## 📋 PROCEDIMENTO MANUAL (Se Setup Falhar)

### Backend Setup

```bash
# 1. Navegar
cd backend

# 2. Criar ambiente virtual
python -m venv venv

# 3. Ativar ambiente
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# 4. Instalar dependências
pip install -r requirements.txt

# 5. Copiar variáveis de ambiente
# Windows:
copy .env.example .env
# Linux/Mac:
cp .env.example .env

# 6. Testar
python main.py --help
```

### Frontend Setup

```bash
# 1. Navegar
cd frontend

# 2. Instalar dependências
npm install

# 3. Testar
npm run dev
```

---

## 🔐 CONFIGURAR CHAVE BLING

### Via CLI (Recomendado)

```bash
cd backend
# Ativar venv se não estiver ativado
python main.py configurar
```

Siga as instruções. Digite sua chave de API Bling quando solicitado.

### Via Arquivo .env

```bash
# Editar backend/.env
BLING_API_KEY=sua_chave_aqui
```

---

## ▶️ INICIAR APLICAÇÃO

### Terminal 1 - Backend

```bash
cd backend

# Ativar venv
venv\Scripts\activate  # Windows
source venv/bin/activate  # Linux/Mac

# Iniciar servidor
python main.py run
```

Deverá ver:
```
INFO: Application startup complete
INFO: Uvicorn running on http://0.0.0.0:8000
```

### Terminal 2 - Frontend

```bash
cd frontend
npm run dev
```

Deverá ver:
```
VITE v5.0.0 ready in XXX ms
Local: http://localhost:3000/
```

---

## ✅ VERIFICAÇÃO

### 1. Verificar Backend
```
Acesse: http://localhost:8000
Veja página de boas-vindas
```

### 2. Verificar Frontend
```
Acesse: http://localhost:3000
Login na aplicação
```

### 3. Verificar Conexão Bling
```
Vá para: Configurações
Status Bling API deve mostrar "Conectado"
Se não, verifique chave de API
```

### 4. Testar Funcionalidades

#### Adicionar Produto
1. Vá para: Importar/Exportar
2. Selecione: "Adicionar Produtos"
3. Download Template
4. Preencha 1 produto teste
5. Upload e Importar
6. Vá para Produtos - deve aparecer

#### Exportar Dados
1. Vá para: Importar/Exportar → Exportar
2. Clique: "Exportar Estoque"
3. Arquivo deve ser baixado

---

## 🐛 TROUBLESHOOTING

### Erro: "ModuleNotFoundError: No module named 'fastapi'"
```
Solução: pip install -r requirements.txt
```

### Erro: "command not found: python" (Linux/Mac)
```
Solução: Usar python3 em vez de python
Ou: export PYTHON=python3
```

### Erro: "npm: command not found"
```
Solução: Instalar Node.js de https://nodejs.org
```

### Erro: "Port 8000 already in use"
```
Solução: python main.py run --port 8001
```

### Erro: "Port 3000 already in use"
```
Solução: npm run dev -- --port 3001
```

### Erro: "CORS error" no frontend
```
Solução: Verificar se backend está rodando
Backend deve estar em http://localhost:8000
```

### Erro: "Chave de API inválida"
```
Solução:
1. Verificar chave em https://www.bling.com.br
2. Copiar exatamente (sem espaços)
3. Configurar em backend/.env
4. Restart do backend
```

### Erro: "ImportError" no backend
```
Solução: Verificar ambiente virtual ativado
Rodar: pip install -r requirements.txt
```

---

## 🎯 PRÓXIMOS PASSOS

### Depois de Verificar Tudo Funciona:

1. **Explore Dashboard**
   - Veja estatísticas
   - Verifique status Bling

2. **Teste Gerenciador de Produtos**
   - Adicione um produto de teste
   - Edite o produto
   - Delete o produto

3. **Teste Importar/Exportar**
   - Exporte dados atuais
   - Crie CSV novo
   - Importe dados

4. **Teste com Dados Reais**
   - Use seus dados de verdade
   - Crie backup antes
   - Valide cada operação

---

## 📊 OPERAÇÕES SUPORTADAS

### Pelo Interface
- [x] Adicionar produtos
- [x] Editar produtos
- [x] Deletar produtos
- [x] Atualizar estoque
- [x] Importar em massa
- [x] Exportar dados
- [x] Gerenciar componentes

### Pelo API (curl/Postman)
```bash
# Listar
curl http://localhost:8000/api/produtos

# Criar em massa
curl -X POST http://localhost:8000/api/produtos/em-massa/criar \
  -H "Content-Type: application/json" \
  -d '{"tipo_operacao":"adicionar","produtos":[...]}'
```

---

## 📚 DOCUMENTAÇÃO RÁPIDA

Se tiver dúvidas, consulte:

1. **Início Rápido**: [QUICK_START.md](QUICK_START.md)
2. **Documentação Completa**: [README.md](README.md)
3. **Exemplos Práticos**: [EXEMPLOS.md](EXEMPLOS.md)
4. **Arquitetura**: [DESENVOLVIMENTO.md](DESENVOLVIMENTO.md)
5. **Resumo do Projeto**: [RESUMO.md](RESUMO.md)

---

## 💡 DICAS

### Logs
Para ver logs em tempo real do backend:
```bash
# Já está ativado por padrão
# Vê tudo no console do terminal
```

### Dados de Teste
Use os templates fornecidos em:
Importar/Exportar → Templates

### Backup
Antes de testar com dados reais:
```bash
# Ir para Exportar
# Clicar "Exportar Estoque"
# Guardar arquivo em local seguro
```

### Performance
Para operações em massa:
- Use CSV com dados pré-validados
- Máximo 1000 itens por importação (recomendado)
- Divida em múltiplos arquivos se necessário

---

## 🎉 PRONTO!

Se tudo funcionou, você tem:
- ✅ Backend rodando em http://localhost:8000
- ✅ Frontend rodando em http://localhost:3000
- ✅ Conectado com API Bling
- ✅ Pronto para usar

**APROVEITE! 🚀**

---

## 📞 AJUDA

Se encontrar problemas:

1. Cheque logs no terminal
2. Consulte troubleshooting acima
3. Verifique documentação
4. Confira variáveis de ambiente

---

## 🌐 Ngrok para OAuth2 (Bling v3)
1. Com o backend rodando em 8000, inicie o túnel:
```bash
ngrok http 8000
```
2. Copie a URL pública (ex.: https://xxxxx.ngrok-free.app)
3. No arquivo backend/.env:
```env
BLING_REDIRECT_URI=https://xxxxx.ngrok-free.app/callback
```
4. Reinicie o backend e execute:
```bash
python main.py configurar
```
5. Abra o link de autorização, autorize e cole o code no terminal.

---

*Desenvolvido em 2024 - SmartBling v1.0.0*
