import sqlite3
from services.vocab_runtime.service import get_next_question

conn = sqlite3.connect("data/lingua_staging.db")
conn.row_factory = sqlite3.Row

user_id = 999001

cur = conn.execute(
    "INSERT INTO mode_runs (mode,user_id,status,source) VALUES (?,?,?,?)",
    ("vocab", user_id, "started", "runtime_smoke")
)
mode_run_id = cur.lastrowid

conn.execute(
    "INSERT INTO vocab_attempts (mode_run_id,user_id,status) VALUES (?,?,?)",
    (mode_run_id, user_id, "started")
)

conn.commit()

for i in range(10):
    q = get_next_question(conn, user_id=user_id)
    if not q:
        print("EMPTY")
        break
    print(i+1, q["item_id"], q["lemma"], q["pos"])

conn.close()
