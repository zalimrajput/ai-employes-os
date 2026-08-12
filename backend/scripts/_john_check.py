import os

def load_env(path):
    if not os.path.exists(path): return
    with open(path, encoding='utf-8') as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line: continue
            k, _, v = line.partition('=')
            os.environ.setdefault(k.strip(), v.strip().strip(chr(34)).strip(chr(39)))

load_env('.env')
from sqlalchemy import create_engine, text
url = os.environ.get('DATABASE_URL') or os.environ.get('SUPABASE_DB_URL')
e = create_engine(url)
oid = '88f45e8f-73f3-4b9a-b247-a1c826c08311'
with e.connect() as c:
    print('=== Customer: John Smith ===')
    rows = c.execute(text('''SELECT id, name, email, phone, company, status, notes FROM customers WHERE organization_id = :o AND lower(name) LIKE '%%john%%' '''), {'o': oid}).fetchall()
    for r in rows:
        print(' id:', r.id)
        print(' name:', r.name)
        print(' email:', r.email)
        print(' phone:', r.phone)
        print(' company:', r.company)
        print(' status:', r.status)
        print(' notes:', (r.notes or '')[:200])
    print()
    print('=== Quotation QUO-2026-001 ===')
    rows = c.execute(text('''SELECT q.quotation_number, q.status, q.total, q.customer_id, c.name, c.company
        FROM quotations q LEFT JOIN customers c ON c.id = q.customer_id
        WHERE q.organization_id = :o AND q.quotation_number = 'QUO-2026-001' '''), {'o': oid}).fetchall()
    for r in rows:
        print(' quotation:', r.quotation_number, '| status:', r.status, '| total:', r.total)
        print(' customer:', r.name, '| company:', r.company)
    print()
    print('=== Any customer named Nove/Nova Tech? ===')
    rows = c.execute(text('''SELECT name, company, email FROM customers WHERE organization_id = :o AND (lower(company) LIKE '%%nove%%' OR lower(company) LIKE '%%nova%%' OR lower(company) LIKE '%%technova%%') '''), {'o': oid}).fetchall()
    for r in rows:
        print(' -', r.name, '|', r.company, '|', r.email)
    if not rows:
        print(' (none)')
