"""Script to expire Bling token for testing auto-renewal."""
from datetime import datetime, timedelta
from uuid import UUID
from sqlalchemy.orm import Session
from app.infra.db import get_db
from app.repositories.bling_token_repo import BlingTokenRepository

# Default tenant ID
TENANT_ID = UUID("00000000-0000-0000-0000-000000000001")

def expire_token():
    """Mark token as expired to test auto-renewal."""
    db = next(get_db())
    
    try:
        token = BlingTokenRepository.get_by_tenant(db, TENANT_ID)
        
        if not token:
            print("❌ Nenhum token encontrado para o tenant.")
            return
        
        # Set token expiration to 10 minutes ago
        old_expiry = token.expires_at
        new_expiry = datetime.utcnow() - timedelta(minutes=10)
        
        token.expires_at = new_expiry
        db.commit()
        
        print("✅ Token marcado como expirado!")
        print(f"   Expirava em: {old_expiry}")
        print(f"   Expirou em:  {new_expiry}")
        print(f"   Agora:       {datetime.utcnow()}")
        print()
        print("🔄 O sistema tentará renovar automaticamente na próxima requisição.")
        print("   Se o refresh_token também estiver expirado, você verá o modal de re-autenticação.")
        
    except Exception as e:
        print(f"❌ Erro ao expirar token: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    expire_token()
