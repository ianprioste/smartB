import asyncio
from app.infra.db import SessionLocal
from app.models.database import BlingOrderSnapshotModel
from app.api.events import _make_client, _extract_contact_id, _fetch_contact_emails

async def main():
    db = SessionLocal()
    try:
        client = _make_client(db)
        if not client:
            print('no_bling_client')
            return
        rows = db.query(BlingOrderSnapshotModel).order_by(BlingOrderSnapshotModel.updated_at.desc()).limit(30).all()
        contact_ids = set()
        for row in rows:
            detail = row.raw_detail if isinstance(row.raw_detail, dict) else {}
            order = row.raw_order if isinstance(row.raw_order, dict) else {}
            cid = _extract_contact_id(detail, order)
            if cid is not None:
                contact_ids.add(int(cid))
        email_map = await _fetch_contact_emails(client, contact_ids)
        print('rows', len(rows), 'contact_ids', len(contact_ids), 'emails_resolved', len(email_map))
        for cid, email in list(email_map.items())[:8]:
            print('contact', cid, 'email', email)
    finally:
        db.close()

asyncio.run(main())
