"""
SmartBling - Aplicação para gerenciamento de produtos Bling
Versão: 1.0.0
"""
import os
import sys
import logging
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
from urllib.parse import urlparse, quote_plus
import secrets
# + imports para callback server
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs
# + imports ngrok
import subprocess
import time
import requests
from contextlib import asynccontextmanager

# Adicionar backend ao path
sys.path.insert(0, str(Path(__file__).parent))

# Carregar variáveis de ambiente
load_dotenv()

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Importar configurações e rotas
from app.core.config import settings
from app.routes import config

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("SmartBling iniciando...")
    logger.info(f"Debug mode: {settings.DEBUG}")
    logger.info(f"CORS Origins: {settings.CORS_ORIGINS}")
    yield
    # Shutdown
    logger.info("SmartBling encerrando...")

# Criar aplicação FastAPI
app = FastAPI(
    title="SmartBling API",
    description="API para gerenciamento avançado de produtos Bling",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Ajustar CORS para incluir origem do REDIRECT_URI (ngrok)
origins = list(settings.CORS_ORIGINS)
try:
    parsed = urlparse(settings.BLING_REDIRECT_URI)
    redirect_origin = f"{parsed.scheme}://{parsed.hostname}"
    if parsed.port:
        redirect_origin = f"{redirect_origin}:{parsed.port}"
    if redirect_origin not in origins:
        origins.append(redirect_origin)
except Exception:
    logger.warning("Não foi possível derivar origem do BLING_REDIRECT_URI")

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Incluir rotas
app.include_router(config.router)

# Criar diretórios necessários
Path(settings.UPLOAD_FOLDER).mkdir(exist_ok=True)
Path(settings.EXPORT_FOLDER).mkdir(exist_ok=True)

# Rota raiz
@app.get("/")
async def root():
    """Rota raiz da aplicação"""
    return {
        "nome": "SmartBling",
        "versao": "1.0.0",
        "descricao": "API para gerenciamento de produtos Bling",
        "documentacao": "/docs"
    }


def _upsert_env_var(key: str, value: str):
    """Atualiza/adiciona uma variável no .env."""
    conteudo = ""
    if Path(".env").exists():
        with open(".env", "r", encoding="utf-8") as f:
            conteudo = f.read()
    linhas = [] if not conteudo else conteudo.splitlines()
    found = False
    for i, linha in enumerate(linhas):
        if linha.startswith(f"{key}="):
            linhas[i] = f"{key}={value}"
            found = True
            break
    if not found:
        linhas.append(f"{key}={value}")
    novo = "\n".join(linhas) + ("\n" if not linhas or not conteudo.endswith("\n") else "")
    with open(".env", "w", encoding="utf-8") as f:
        f.write(novo)

def _start_ngrok(port: int) -> tuple:
    """Inicia ngrok para a porta informada e retorna (processo, public_url)."""
    try:
        # Configurar authtoken se fornecido
        if settings.NGROK_AUTHTOKEN:
            subprocess.run(
                [settings.NGROK_BIN, "config", "add-authtoken", settings.NGROK_AUTHTOKEN],
                check=False, 
                capture_output=True
            )

        # Iniciar ngrok em background
        cmd = [settings.NGROK_BIN, "http", str(port), "--log=stdout"]
        if settings.NGROK_REGION:
            cmd.extend(["--region", settings.NGROK_REGION])
        
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Aguardar ngrok iniciar e obter URL
        public_url = None
        print(f"Iniciando ngrok na porta {port}...")
        
        for attempt in range(30):  # 15 segundos
            try:
                resp = requests.get("http://127.0.0.1:4040/api/tunnels", timeout=2)
                if resp.ok:
                    data = resp.json()
                    tunnels = data.get("tunnels", [])
                    for tunnel in tunnels:
                        if tunnel.get("proto") == "https":
                            public_url = tunnel.get("public_url")
                            print(f"✓ ngrok iniciado: {public_url}")
                            return proc, public_url
            except Exception:
                pass
            time.sleep(0.5)
        
        print("⚠ ngrok iniciado mas URL não obtida via API")
        return proc, None
        
    except FileNotFoundError:
        print(f"✗ ngrok não encontrado. Certifique-se que está instalado e acessível.")
        print(f"  Procurando em: {settings.NGROK_BIN}")
        return None, None
    except Exception as e:
        print(f"✗ Erro ao iniciar ngrok: {e}")
        return None, None

def _stop_ngrok(proc: subprocess.Popen | None):
    """Finaliza o processo do ngrok."""
    if proc:
        try:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except Exception:
                proc.kill()
        except Exception:
            pass

def configurar():
    """Função para configuração inicial da aplicação"""
    logger.info("Iniciando configuração...")

    # Garantir .env
    if not Path(".env").exists():
        logger.warning(".env não encontrado, criando a partir de .env.example")
        if Path(".env.example").exists():
            with open(".env.example", "r", encoding="utf-8") as src, open(".env", "w", encoding="utf-8") as dst:
                dst.write(src.read())

    print("\n=== Configuração do SmartBling ===\n")

    # Fluxo OAuth2 v3 (client_id/secret)
    if settings.BLING_CLIENT_ID and settings.BLING_CLIENT_SECRET:
        print("Fluxo OAuth2 - Bling API v3")
        print("\nAbra um NOVO terminal e execute:")
        print("  ngrok http 8000")
        print("\nCopie a URL pública do ngrok (ex.: https://xxxxx.ngrok-free.app)")
        print("Atualize no backend/.env a variável:")
        print("  BLING_REDIRECT_URI=https://xxxxx.ngrok-free.app/callback")
        input("\nPressione Enter quando o BLING_REDIRECT_URI estiver correto no .env... ")

        # Carregar REDIRECT_URI atualizado (se alterado no .env)
        try:
            os.environ["BLING_REDIRECT_URI"] = os.getenv("BLING_REDIRECT_URI", settings.BLING_REDIRECT_URI)
            from importlib import reload
            import app.core.config as cfg
            reload(cfg)
            from app.core.config import settings as s2
            settings.BLING_REDIRECT_URI = s2.BLING_REDIRECT_URI
        except Exception:
            pass

        state = secrets.token_hex(16)
        oauth_base = "https://api.bling.com.br/Api/v3/oauth"
        authorize_url = (
            f"{oauth_base}/authorize"
            f"?response_type=code"
            f"&client_id={settings.BLING_CLIENT_ID}"
            f"&redirect_uri={quote_plus(settings.BLING_REDIRECT_URI)}"
            f"&state={state}"
        )

        print("\nAbra o link de autorização abaixo, faça login e autorize:")
        print(authorize_url)
        try:
            abrir = input("\nAbrir automaticamente no navegador? (S/n): ").strip().lower()
            if abrir != "n":
                import webbrowser
                webbrowser.open(authorize_url)
        except Exception:
            pass

        print("\nApós autorizar, você será redirecionado para o seu /callback do ngrok.")
        print("Copie a URL completa OU somente o valor de 'code' e cole abaixo.")
        manual = input("\nCole aqui a URL completa do callback OU apenas o 'code': ").strip()

        # Extrair code se recebeu URL
        code = None
        if manual:
            if "code=" in manual:
                try:
                    parsed = urlparse(manual)
                    qs = parse_qs(parsed.query)
                    code = qs.get("code", [None])[0]
                except Exception:
                    code = None
            else:
                code = manual

        if not code:
            print("✗ Código não recebido. Tente novamente.")
            return

        print(f"\n✓ Código recebido: {code[:10]}...")

        # Trocar code por tokens
        print("\n🔄 Trocando código por tokens...")
        import requests
        from requests.auth import HTTPBasicAuth

        token_url = f"{oauth_base}/token"
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": settings.BLING_REDIRECT_URI,
        }
        resp = requests.post(
            token_url,
            data=data,
            headers=headers,
            auth=HTTPBasicAuth(settings.BLING_CLIENT_ID, settings.BLING_CLIENT_SECRET),
            timeout=30,
        )
        if not resp.ok:
            data_alt = dict(data)
            data_alt["client_id"] = settings.BLING_CLIENT_ID
            data_alt["client_secret"] = settings.BLING_CLIENT_SECRET
            print(f"⚠ Tentativa com Basic falhou ({resp.status_code}). Fallback com client no corpo...")
            resp = requests.post(token_url, data=data_alt, headers=headers, timeout=30)

        if not resp.ok:
            print(f"\n✗ Falha ao obter tokens (HTTP {resp.status_code})")
            try:
                print("Resposta:", resp.json())
            except Exception:
                print("Resposta:", resp.text)
            print("\nVerifique redirect_uri, code e credenciais.")
            return

        tk = resp.json() or {}
        access_token = tk.get("access_token")
        refresh_token = tk.get("refresh_token")
        token_type = tk.get("token_type", "Bearer")
        expires_in = tk.get("expires_in")

        if not access_token:
            print("✗ access_token ausente na resposta:", tk)
            return

        # Salvar no .env
        def _upsert_env_var_local(k: str, v: str):
            conteudo = ""
            if Path(".env").exists():
                with open(".env", "r", encoding="utf-8") as f:
                    conteudo = f.read()
            linhas = [] if not conteudo else conteudo.splitlines()
            found = False
            for i, linha in enumerate(linhas):
                if linha.startswith(f"{k}="):
                    linhas[i] = f"{k}={v}"
                    found = True
                    break
            if not found:
                linhas.append(f"{k}={v}")
            novo = "\n".join(linhas) + ("\n" if not linhas or not conteudo.endswith("\n") else "")
            with open(".env", "w", encoding="utf-8") as f:
                f.write(novo)

        _upsert_env_var_local("BLING_ACCESS_TOKEN", access_token)
        if refresh_token:
            _upsert_env_var_local("BLING_REFRESH_TOKEN", refresh_token)
        _upsert_env_var_local("BLING_TOKEN_TYPE", token_type or "Bearer")
        if expires_in is not None:
            _upsert_env_var_local("BLING_EXPIRES_IN", str(expires_in))

        print("✓ Tokens salvos no .env")
        print("\n🎉 Autenticação OAuth2 concluída!")
        print("\n=== Configuração concluída ===\n")
        return

    # Fluxo API Key (v2) como fallback
    login_url = "https://www.bling.com.br/login"
    ajuda_url = "https://ajuda.bling.com.br/hc/pt-br/articles/360026837774"
    print("Para obter sua API Key (API v2):")
    print(f"1) Acesse: {login_url}")
    print("2) Preferências > Sistema > Usuários > Integrações > Chaves de API")
    print(f"Ajuda: {ajuda_url}")
    try:
        abrir = input("\nAbrir o link no navegador? (s/N): ").strip().lower()
        if abrir == "s":
            import webbrowser
            webbrowser.open(login_url)
    except Exception:
        pass

    api_key = input("\nCole sua chave de API Bling: ").strip()
    if api_key:
        settings.BLING_API_KEY = api_key
        _upsert_env_var("BLING_API_KEY", api_key)
        logger.info("API Key configurada")
    else:
        print("Nenhuma chave informada. Usando valor do .env (se existir).")

    from app.services.bling_service import BlingAPIService
    bling = BlingAPIService()
    if bling.validar_conexao():
        print("\n✓ Conexão com Bling validada com sucesso!")
    else:
        print("\n✗ Falha ao conectar com Bling. Verifique a chave de API.")
    print("\n=== Configuração concluída ===\n")

# Compatibility bridge: if this module is used as ASGI target (e.g. backend.main:app),
# expose the modern application that contains access/auth and all current routers.
try:
    from app.main import app as modern_app
    app = modern_app
except Exception as exc:
    logger.warning("Não foi possível carregar app.main: %s", exc)

# --- CLI (mantido simples, sem ngrok automático) ---
if __name__ == "__main__":
    import uvicorn
    import argparse

    parser = argparse.ArgumentParser(description="SmartBling - Gerenciador de Produtos Bling")
    parser.add_argument("comando", nargs="?", default="run", help="Comando a executar (run, configurar)")
    parser.add_argument("--host", default=settings.SERVER_HOST, help=f"Host do servidor (padrão: {settings.SERVER_HOST})")
    parser.add_argument("--port", type=int, default=settings.SERVER_PORT, help=f"Porta do servidor (padrão: {settings.SERVER_PORT})")
    parser.add_argument("--reload", action="store_true", help="Recarregar servidor em mudanças de código")
    args = parser.parse_args()

    if args.comando == "configurar":
        configurar()
    elif args.comando == "run":
        logger.info(f"Iniciando servidor em {args.host}:{args.port}")
        uvicorn.run(
            "app.main:app",
            host=args.host,
            port=args.port,
            reload=args.reload or settings.DEBUG,
            log_level="info"
        )
    else:
        print(f"Comando desconhecido: {args.comando}")
        print("Comandos disponíveis: run, configurar")
