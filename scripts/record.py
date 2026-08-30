"""決定・宿題・画面・機能・事実・会議そのものをDBに記録する。

司会コマンドから呼ばれる。サブコマンド方式。

  meeting-open  会議を開始し、参加者を登録する
  meeting-close 会議を閉じる
  decision      決定を記録（--status 仮|本）
  promote       仮決めを本決めに昇格
  issue         宿題を起票
  close-issue   宿題を消化
  screen        画面を登録・更新
  screen-item   画面の項目定義を登録
  review        画面へのレビュー指摘を登録
  resolve       指摘を解消済みにする
  feature       機能を登録・更新
  fact          確定事実を登録
  state         状態キーの取得・設定
"""
from __future__ import annotations

import argparse
import sys

from db_init import connect, current_meeting_id, get_state, now, set_state

SCREEN_STATUSES = [
    "未着手", "設計中", "社内レビュー中", "社内OK",
    "業務担当者レビュー中", "差戻し", "承認済",
]
AUTHORITY = ["未確認", "委譲済み", "部長のみ"]
JUDGMENTS = ["採用", "次期", "対象外", "保留"]


def cmd_meeting_open(con, a):
    seq = con.execute("SELECT COALESCE(MAX(seq),0)+1 AS n FROM meeting").fetchone()["n"]
    cur = con.execute(
        "INSERT INTO meeting(seq,purpose,opened_at,budget_min) VALUES(?,?,?,?)",
        (seq, a.purpose, now(), a.minutes),
    )
    mid = cur.lastrowid
    for spec in a.participant or []:
        agent, _, mode = spec.partition(":")
        con.execute(
            "INSERT INTO participant(meeting_id,agent,mode) VALUES(?,?,?)",
            (mid, agent.strip(), (mode or "full").strip()),
        )
    set_state(con, "current_meeting", mid)
    # 枠は会議ごとにリセット
    set_state(con, "boss_confirm_quota", "2")
    set_state(con, "escalate_quota", "2")
    print("第{}回を開始 (meeting_id={}, 持ち時間{}分): {}".format(
        seq, mid, a.minutes, a.purpose))


def cmd_meeting_close(con, a):
    mid = a.meeting_id or current_meeting_id(con)
    if not mid:
        sys.exit("進行中の会議がありません")
    con.execute(
        "UPDATE meeting SET closed_at=?, summary=? WHERE id=?",
        (now(), a.summary, mid),
    )
    set_state(con, "current_meeting", "")
    print("meeting_id={} を閉会".format(mid))


def cmd_decision(con, a):
    mid = a.meeting_id or current_meeting_id(con)
    cur = con.execute(
        "INSERT INTO decision(meeting_id,body,status,decided_by,rationale,"
        "utterance_id,decided_at) VALUES(?,?,?,?,?,?,?)",
        (mid, a.body, a.status, a.by, a.rationale, a.utterance, now()),
    )
    print("decision #{} ({}) 記録".format(cur.lastrowid, a.status))


def cmd_promote(con, a):
    con.execute("UPDATE decision SET status='本' WHERE id=?", (a.id,))
    print("decision #{} を本決めに昇格".format(a.id))


def cmd_issue(con, a):
    mid = a.meeting_id or current_meeting_id(con)
    cur = con.execute(
        "INSERT INTO issue(meeting_id,body,owner,due,created_at) VALUES(?,?,?,?,?)",
        (mid, a.body, a.owner, a.due, now()),
    )
    print("issue #{} 起票".format(cur.lastrowid))


def cmd_close_issue(con, a):
    mid = a.meeting_id or current_meeting_id(con)
    con.execute(
        "UPDATE issue SET state='closed', closed_meeting_id=?, closed_at=? WHERE id=?",
        (mid, now(), a.id),
    )
    print("issue #{} を消化".format(a.id))


def cmd_screen(con, a):
    row = con.execute("SELECT id FROM screen WHERE code=?", (a.code,)).fetchone()
    if row is None:
        status = a.status or "設計中"
        # 新規登録でいきなり承認済にする場合も承認情報を残す
        approved = (None, None)
        if status == "承認済":
            approved = (a.meeting_id or current_meeting_id(con), now())
        cur = con.execute(
            "INSERT INTO screen(code,name,area,designer,status,summary,wireframe,note,"
            "approved_meeting_id,approved_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (a.code, a.name or a.code, a.area, a.designer,
             status, a.summary, a.wireframe, a.note, approved[0], approved[1]),
        )
        print("screen {} を新規登録 (id={})".format(a.code, cur.lastrowid))
        return
    sets, vals = [], []
    for col, val in [("name", a.name), ("area", a.area), ("designer", a.designer),
                     ("status", a.status), ("summary", a.summary),
                     ("wireframe", a.wireframe), ("note", a.note)]:
        if val is not None:
            sets.append(col + "=?")
            vals.append(val)
    if a.status == "承認済":
        sets += ["approved_meeting_id=?", "approved_at=?"]
        vals += [a.meeting_id or current_meeting_id(con), now()]
    if not sets:
        sys.exit("更新する項目がありません")
    vals.append(a.code)
    con.execute("UPDATE screen SET " + ",".join(sets) + " WHERE code=?", vals)
    print("screen {} を更新".format(a.code))


def cmd_screen_item(con, a):
    row = con.execute("SELECT id FROM screen WHERE code=?", (a.code,)).fetchone()
    if row is None:
        sys.exit("画面 {} が未登録です".format(a.code))
    seq = con.execute(
        "SELECT COALESCE(MAX(seq),0)+1 AS n FROM screen_item WHERE screen_id=?",
        (row["id"],),
    ).fetchone()["n"]
    con.execute(
        "INSERT INTO screen_item(screen_id,seq,name,datatype,length,required,"
        "default_value,validation,note) VALUES(?,?,?,?,?,?,?,?,?)",
        (row["id"], seq, a.item, a.datatype, a.length, a.required,
         a.default, a.validation, a.note),
    )
    print("{} に項目 {} を追加".format(a.code, a.item))


def cmd_review(con, a):
    row = con.execute("SELECT id FROM screen WHERE code=?", (a.code,)).fetchone()
    if row is None:
        sys.exit("画面 {} が未登録です".format(a.code))
    cur = con.execute(
        "INSERT INTO screen_review(screen_id,meeting_id,utterance_id,reviewer,"
        "stage,comment,created_at) VALUES(?,?,?,?,?,?,?)",
        (row["id"], a.meeting_id or current_meeting_id(con), a.utterance,
         a.reviewer, a.stage, a.comment, now()),
    )
    print("screen_review #{} ({}) 登録".format(cur.lastrowid, a.stage))


def cmd_resolve(con, a):
    con.execute("UPDATE screen_review SET resolved=1 WHERE id=?", (a.id,))
    print("screen_review #{} を解消済みに".format(a.id))


def cmd_feature(con, a):
    row = con.execute("SELECT id FROM feature WHERE code=?", (a.code,)).fetchone()
    if row is None:
        judgment = a.judgment or "保留"
        # 保留以外の判定を最初から付ける場合は、いつ誰が裁いたかも残す
        judged = (None, None)
        if a.judgment:
            judged = (a.meeting_id or current_meeting_id(con), now())
        cur = con.execute(
            "INSERT INTO feature(code,name,area,screens,summary,priority,judgment,note,"
            "judged_meeting_id,judged_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (a.code, a.name or a.code, a.area, a.screens, a.summary,
             a.priority, judgment, a.note, judged[0], judged[1]),
        )
        print("feature {} を新規登録 (id={})".format(a.code, cur.lastrowid))
        return
    sets, vals = [], []
    for col, val in [("name", a.name), ("area", a.area), ("screens", a.screens),
                     ("summary", a.summary), ("priority", a.priority),
                     ("judgment", a.judgment), ("note", a.note)]:
        if val is not None:
            sets.append(col + "=?")
            vals.append(val)
    if a.judgment:
        sets += ["judged_meeting_id=?", "judged_at=?"]
        vals += [a.meeting_id or current_meeting_id(con), now()]
    if not sets:
        sys.exit("更新する項目がありません")
    vals.append(a.code)
    con.execute("UPDATE feature SET " + ",".join(sets) + " WHERE code=?", vals)
    print("feature {} を更新".format(a.code))


def cmd_fact(con, a):
    mid = a.meeting_id or current_meeting_id(con)
    cur = con.execute(
        "INSERT INTO fact(meeting_id,utterance_id,topic,body,stated_by,created_at) "
        "VALUES(?,?,?,?,?,?)",
        (mid, a.utterance, a.topic, a.body, a.by, now()),
    )
    print("fact #{} 記録: {}".format(cur.lastrowid, a.topic))


def cmd_state(con, a):
    if a.value is None:
        print(get_state(con, a.key, "(未設定)"))
        return
    if a.key == "decision_authority" and a.value not in AUTHORITY:
        sys.exit("decision_authority は " + "/".join(AUTHORITY) + " のいずれか")
    set_state(con, a.key, a.value)
    print("{} = {}".format(a.key, a.value))


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="会議の記録をDBに書く")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("meeting-open")
    p.add_argument("--purpose", required=True)
    p.add_argument("--participant", action="append",
                   help="agent:mode 形式。例 client-boss:opening")
    p.add_argument("--minutes", type=int, default=30,
                   help="会議の持ち時間（分）。既定30")
    p.set_defaults(fn=cmd_meeting_open)

    p = sub.add_parser("meeting-close")
    p.add_argument("--summary")
    p.add_argument("--meeting-id", type=int)
    p.set_defaults(fn=cmd_meeting_close)

    p = sub.add_parser("decision")
    p.add_argument("--body", required=True)
    p.add_argument("--status", choices=["仮", "本"], default="仮")
    p.add_argument("--by")
    p.add_argument("--rationale")
    p.add_argument("--utterance", type=int)
    p.add_argument("--meeting-id", type=int)
    p.set_defaults(fn=cmd_decision)

    p = sub.add_parser("promote")
    p.add_argument("--id", type=int, required=True)
    p.set_defaults(fn=cmd_promote)

    p = sub.add_parser("issue")
    p.add_argument("--body", required=True)
    p.add_argument("--owner")
    p.add_argument("--due")
    p.add_argument("--meeting-id", type=int)
    p.set_defaults(fn=cmd_issue)

    p = sub.add_parser("close-issue")
    p.add_argument("--id", type=int, required=True)
    p.add_argument("--meeting-id", type=int)
    p.set_defaults(fn=cmd_close_issue)

    p = sub.add_parser("screen")
    p.add_argument("--code", required=True)
    p.add_argument("--name")
    p.add_argument("--area")
    p.add_argument("--designer", choices=["sys-staff", "sys-junior"])
    p.add_argument("--status", choices=SCREEN_STATUSES)
    p.add_argument("--summary")
    p.add_argument("--wireframe")
    p.add_argument("--note")
    p.add_argument("--meeting-id", type=int)
    p.set_defaults(fn=cmd_screen)

    p = sub.add_parser("screen-item")
    p.add_argument("--code", required=True)
    p.add_argument("--item", required=True)
    p.add_argument("--datatype")
    p.add_argument("--length")
    p.add_argument("--required")
    p.add_argument("--default")
    p.add_argument("--validation")
    p.add_argument("--note")
    p.set_defaults(fn=cmd_screen_item)

    p = sub.add_parser("review")
    p.add_argument("--code", required=True)
    p.add_argument("--comment", required=True)
    p.add_argument("--stage", choices=["社内", "業務担当者"], default="業務担当者")
    p.add_argument("--reviewer")
    p.add_argument("--utterance", type=int)
    p.add_argument("--meeting-id", type=int)
    p.set_defaults(fn=cmd_review)

    p = sub.add_parser("resolve")
    p.add_argument("--id", type=int, required=True)
    p.set_defaults(fn=cmd_resolve)

    p = sub.add_parser("feature")
    p.add_argument("--code", required=True)
    p.add_argument("--name")
    p.add_argument("--area")
    p.add_argument("--screens")
    p.add_argument("--summary")
    p.add_argument("--priority")
    p.add_argument("--judgment", choices=JUDGMENTS)
    p.add_argument("--note")
    p.add_argument("--meeting-id", type=int)
    p.set_defaults(fn=cmd_feature)

    p = sub.add_parser("fact")
    p.add_argument("--topic", required=True)
    p.add_argument("--body", required=True)
    p.add_argument("--by")
    p.add_argument("--utterance", type=int)
    p.add_argument("--meeting-id", type=int)
    p.set_defaults(fn=cmd_fact)

    p = sub.add_parser("state")
    p.add_argument("--key", required=True)
    p.add_argument("--value")
    p.set_defaults(fn=cmd_state)

    return ap


def main() -> None:
    args = build_parser().parse_args()
    con = connect()
    try:
        args.fn(con, args)
        con.commit()
    finally:
        con.close()


if __name__ == "__main__":
    main()
