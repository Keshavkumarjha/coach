from django.db import connection
from django.utils import timezone

def _nextval(seq: str) -> int:
    with connection.cursor() as cur:
        cur.execute("SELECT nextval(%s)", [seq])
        return int(cur.fetchone()[0])

def _yy() -> str:
    return str(timezone.now().year)[-2:]

def make_public_id(prefix: str, seq: str, width: int = 7) -> str:
    n = _nextval(seq)
    return f"{prefix}-{_yy()}-{n:0{width}d}"

def org_public_id() -> str:
    return make_public_id("ORG", "seq_org_public", width=6)

def branch_public_id() -> str:
    return make_public_id("BR", "seq_branch_public", width=6)

def student_public_id() -> str:
    return make_public_id("STU", "seq_student_public", width=7)

def teacher_public_id() -> str:
    return make_public_id("TCH", "seq_teacher_public", width=7)

def invoice_public_id() -> str:
    return make_public_id("INV", "seq_invoice_public", width=8)

def txn_public_id() -> str:
    return make_public_id("TXN", "seq_txn_public", width=9)

def campaign_public_id() -> str:
    return make_public_id("CMP", "seq_campaign_public", width=7)

def announcement_public_id() -> str:
    return make_public_id("ANN", "seq_announcement_public", width=7)