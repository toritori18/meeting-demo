"""会議シミュレーションDBのスキーマ作成と共通ヘルパ。

他のスクリプトはここから connect() / now() / ROOT を import する。
冪等: 何度実行してもよい。
"""
from __future__ import annotations

import sqlite3
import sys
from datetime import datetime
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "db" / "meeting.db"
DOCS = ROOT / "docs"

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS meeting(
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    seq         INTEGER NOT NULL,              -- 第N回
    purpose     TEXT    NOT NULL,              -- 監督が伝えた目的（自由文）
    opened_at   TEXT    NOT NULL,
    closed_at   TEXT,
    summary     TEXT
);

CREATE TABLE IF NOT EXISTS participant(
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    meeting_id  INTEGER NOT NULL REFERENCES meeting(id),
    agent       TEXT    NOT NULL,              -- sys-manager / client-boss / ...
    mode        TEXT    NOT NULL               -- full / opening / bookend / oneonone
);

-- 全発言。話者には 司会 と supervisor(監督) も含む
CREATE TABLE IF NOT EXISTS utterance(
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    meeting_id  INTEGER REFERENCES meeting(id),
    seq         INTEGER NOT NULL,
    speaker     TEXT    NOT NULL,
    topic       TEXT,
    body        TEXT    NOT NULL,
    spoken_at   TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_utt_meeting ON utterance(meeting_id, seq);
CREATE INDEX IF NOT EXISTS idx_utt_speaker ON utterance(speaker);

CREATE TABLE IF NOT EXISTS decision(
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    meeting_id    INTEGER REFERENCES meeting(id),
    body          TEXT    NOT NULL,
    status        TEXT    NOT NULL DEFAULT '仮',   -- 仮 / 本
    decided_by    TEXT,
    rationale     TEXT,
    utterance_id  INTEGER REFERENCES utterance(id), -- 根拠となった発言
    decided_at    TEXT    NOT NULL,
    superseded_by INTEGER REFERENCES decision(id)
);

CREATE TABLE IF NOT EXISTS issue(
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    meeting_id        INTEGER REFERENCES meeting(id),
    body              TEXT    NOT NULL,
    owner             TEXT,
    due               TEXT,
    state             TEXT    NOT NULL DEFAULT 'open',
    closed_meeting_id INTEGER REFERENCES meeting(id),
    closed_at         TEXT,
    created_at        TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS screen(
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    code                TEXT    NOT NULL UNIQUE,
    name                TEXT    NOT NULL,
    area                TEXT,                          -- 取込/マッチング/修正/出力/横断
    designer            TEXT,                          -- sys-staff / sys-junior
    status              TEXT    NOT NULL DEFAULT '未着手',
    summary             TEXT,
    wireframe           TEXT,
    approved_meeting_id INTEGER REFERENCES meeting(id),
    approved_at         TEXT,
    note                TEXT
);

CREATE TABLE IF NOT EXISTS screen_item(
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    screen_id     INTEGER NOT NULL REFERENCES screen(id),
    seq           INTEGER,
    name          TEXT    NOT NULL,
    datatype      TEXT,
    length        TEXT,
    required      TEXT,
    default_value TEXT,
    validation    TEXT,
    note          TEXT
);

CREATE TABLE IF NOT EXISTS screen_review(
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    screen_id    INTEGER NOT NULL REFERENCES screen(id),
    meeting_id   INTEGER REFERENCES meeting(id),
    utterance_id INTEGER REFERENCES utterance(id),
    reviewer     TEXT,
    stage        TEXT,                                 -- 社内 / 業務担当者
    comment      TEXT    NOT NULL,
    resolved     INTEGER NOT NULL DEFAULT 0,
    created_at   TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS feature(
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    code              TEXT    NOT NULL UNIQUE,
    name              TEXT    NOT NULL,
    area              TEXT,
    screens           TEXT,
    summary           TEXT,
    priority          TEXT,
    judgment          TEXT    NOT NULL DEFAULT '保留',  -- 採用/次期/対象外/保留
    judged_meeting_id INTEGER REFERENCES meeting(id),
    judged_at         TEXT,
    note              TEXT
);

-- エージェントが口にした具体値。会議をまたいだ一貫性の根拠
CREATE TABLE IF NOT EXISTS fact(
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    meeting_id   INTEGER REFERENCES meeting(id),
    utterance_id INTEGER REFERENCES utterance(id),
    topic        TEXT    NOT NULL,
    body         TEXT    NOT NULL,
    stated_by    TEXT,
    created_at   TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS revision(
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    version    TEXT,
    dated      TEXT,
    meeting_id INTEGER REFERENCES meeting(id),
    body       TEXT
);

-- 業務側の正解ファイルへのアクセス記録。情報の非対称が守られているかの監査
CREATE TABLE IF NOT EXISTS access_log(
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    meeting_id INTEGER,
    tool       TEXT,
    target     TEXT,
    detail     TEXT,
    accessed_at TEXT NOT NULL
);

-- 単純なキーバリュー状態（決定権ステータス、各種枠、進行中の会議など）
CREATE TABLE IF NOT EXISTS state(
    key   TEXT PRIMARY KEY,
    value TEXT
);
"""

# 既存DBに後から足した列。CREATE TABLE IF NOT EXISTS では追加されないので
# 起動時に不足分だけ ALTER TABLE する（冪等）。
MIGRATIONS = [
    ("meeting", "budget_min", "INTEGER DEFAULT 60"),   # 会議の持ち時間（分）
    ("utterance", "minutes", "INTEGER DEFAULT 0"),     # その発言が費やした想定時間
    ("meeting", "goal", "TEXT"),                       # 開会時に宣言したゴール（2本立て）
    ("meeting", "next_step", "TEXT"),                  # 閉会時に提案した次回の会議
]

# 発言1件あたりの想定所要時間（分）。実会議の体感に合わせた見積もり
SPEAKER_MINUTES = {
    "司会": 1,          # 開会・議題切替・閉会の定型
    "supervisor": 0,    # 監督の介入は会議時間に含めない
}
DEFAULT_MINUTES = 3     # エージェントの発言（質問のまとめ、回答、指摘）

INITIAL_STATE = {
    "decision_authority": "未確認",   # 未確認 / 委譲済み / 部長のみ
    "boss_confirm_quota": "2",        # 部長への即時確認枠（会議ごとにリセット）
    "escalate_quota": "2",            # 管理者への緊急相談枠（会議ごとにリセット）
    "current_meeting": "",
    "auto": "on",                     # 既定で自走。会議中は監督に判断を戻さない
}


def now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con


def get_state(con: sqlite3.Connection, key: str, default: str = "") -> str:
    row = con.execute("SELECT value FROM state WHERE key=?", (key,)).fetchone()
    return row["value"] if row else default


def set_state(con: sqlite3.Connection, key: str, value: str) -> None:
    con.execute(
        "INSERT INTO state(key,value) VALUES(?,?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, str(value)),
    )


def estimate_minutes(speaker: str) -> int:
    """話者からその発言の想定所要時間（分）を返す。"""
    return SPEAKER_MINUTES.get(speaker, DEFAULT_MINUTES)


def current_meeting_id(con: sqlite3.Connection) -> int | None:
    raw = get_state(con, "current_meeting", "")
    return int(raw) if raw else None


def main() -> None:
    con = connect()
    con.executescript(SCHEMA)
    for table, column, ddl in MIGRATIONS:
        cols = {r["name"] for r in con.execute("PRAGMA table_info({})".format(table))}
        if column not in cols:
            con.execute("ALTER TABLE {} ADD COLUMN {} {}".format(table, column, ddl))
            print("列を追加: {}.{}".format(table, column))
    for key, value in INITIAL_STATE.items():
        if con.execute("SELECT 1 FROM state WHERE key=?", (key,)).fetchone() is None:
            con.execute("INSERT INTO state(key,value) VALUES(?,?)", (key, value))
    con.commit()
    tables = [
        r["name"]
        for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
    ]
    con.close()
    print(f"DB: {DB_PATH}")
    print(f"テーブル({len(tables)}): {', '.join(tables)}")


if __name__ == "__main__":
    main()
