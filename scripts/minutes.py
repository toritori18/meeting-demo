"""会議1回分の備忘を output/備忘_NN.md に書き出す。

docs/ のビューは種類ごとの縦串（決定は決定、宿題は宿題）。備忘はその横串で、
**1回の会議を1枚で読む**ためのもの。閉会後にそのまま配れる体裁にしてある。

DBが正。直接編集しても次の実行で消える。

    python scripts/minutes.py              # 全回を再生成
    python scripts/minutes.py --meeting 2  # 第2回だけ
    python scripts/minutes.py --latest     # 直近の1回だけ
"""
from __future__ import annotations

import argparse
import sys

from db_init import ROOT, connect, get_state, now
from views import _meeting_label, _table

OUT = ROOT / "output"
HEADER = ("<!-- このファイルは scripts/minutes.py が DB から自動生成します。"
          "直接編集しないでください。 -->\n")

MODE_LABEL = {
    "full": "full",
    "opening": "opening（冒頭で退席）",
    "bookend": "bookend（冒頭と最後）",
    "oneonone": "oneonone（個別）",
}


def _col(row, key, default=None):
    """DBの列が古くて存在しない場合でも落ちないように読む。"""
    return row[key] if key in row.keys() else default


def _u(uid) -> str:
    # 根拠発言のない決定は蒸し返されたときに守れない。空欄にせず目立たせる
    return "u#{}".format(uid) if uid else "**なし**"


def build(con, m, latest: bool) -> str:
    mid = m["id"]
    b = [HEADER, "# 第{}回 備忘 — {}\n".format(m["seq"], m["purpose"])]

    used = con.execute(
        "SELECT COALESCE(SUM(minutes),0) AS n FROM utterance WHERE meeting_id=?",
        (mid,)).fetchone()["n"]
    budget = m["budget_min"] or 60
    b.append(_table(["項目", "内容"], [
        ("開催", "{} 〜 {}".format(m["opened_at"], m["closed_at"] or "**（進行中）**")),
        ("時間", "{} 分 / {} 分".format(used, budget)),
    ]))
    b.append("")

    goal = _col(m, "goal")
    if goal:
        b += ["## 本日のゴール\n", goal, ""]
    if m["summary"]:
        b += ["## 総括\n", m["summary"], ""]

    parts = con.execute(
        "SELECT agent, mode FROM participant WHERE meeting_id=? ORDER BY id",
        (mid,)).fetchall()
    if parts:
        prows = []
        for p in parts:
            n = con.execute(
                "SELECT COUNT(*) AS n FROM utterance WHERE meeting_id=? AND speaker=?",
                (mid, p["agent"])).fetchone()["n"]
            # full で呼んだのに黙っていた人は、招集を誤ったか司会が振り忘れたか
            note = "★一度も発言していない" if n == 0 and p["mode"] == "full" else ""
            prows.append((p["agent"], MODE_LABEL.get(p["mode"], p["mode"]),
                          "{} 件".format(n), note))
        b += ["## 参加者\n",
              _table(["エージェント", "参加形態", "発言", "備考"], prows), ""]

    decs = con.execute(
        "SELECT * FROM decision WHERE meeting_id=? ORDER BY id", (mid,)).fetchall()
    cols = ["#", "決定事項", "決めた人", "根拠", "根拠発言"]
    fixed = [d for d in decs if d["status"] == "本"]
    prov = [d for d in decs if d["status"] != "本"]
    if fixed:
        b += ["## 決まったこと（本決め）\n",
              _table(cols, [(d["id"], d["body"], d["decided_by"], d["rationale"],
                             _u(d["utterance_id"])) for d in fixed]), ""]
    if prov:
        b += ["## 決まったこと（仮決め）\n",
              "この前提で進めますが確定ではありません。次回の冒頭で本決めを諮ります。\n",
              _table(cols, [(d["id"], d["body"], d["decided_by"], d["rationale"],
                             _u(d["utterance_id"])) for d in prov]), ""]

    issues = con.execute(
        "SELECT * FROM issue WHERE meeting_id=? ORDER BY id", (mid,)).fetchall()
    if issues:
        b += ["## 持ち帰り（宿題）\n",
              _table(["#", "内容", "担当", "期限", "状態"],
                     [(i["id"], i["body"], i["owner"], i["due"],
                       "未消化" if i["state"] == "open" else "消化済")
                      for i in issues]), ""]

    closed_here = con.execute(
        "SELECT * FROM issue WHERE closed_meeting_id=? ORDER BY id", (mid,)).fetchall()
    if closed_here:
        b += ["## この回で消化した宿題\n",
              _table(["#", "内容", "担当", "起票"],
                     [(i["id"], i["body"], i["owner"],
                       _meeting_label(con, i["meeting_id"])) for i in closed_here]), ""]

    facts = con.execute(
        "SELECT * FROM fact WHERE meeting_id=? ORDER BY id", (mid,)).fetchall()
    if facts:
        b += ["## この回で確定した事実\n",
              _table(["#", "話題", "内容", "述べた人", "根拠発言"],
                     [(f["id"], f["topic"], f["body"], f["stated_by"],
                       _u(f["utterance_id"])) for f in facts]), ""]

    approved = con.execute(
        "SELECT * FROM screen WHERE approved_meeting_id=? ORDER BY code",
        (mid,)).fetchall()
    reviews = con.execute(
        "SELECT r.*, s.code AS scode, s.name AS sname FROM screen_review r "
        "JOIN screen s ON s.id=r.screen_id WHERE r.meeting_id=? ORDER BY r.id",
        (mid,)).fetchall()
    if approved or reviews:
        b.append("## 画面\n")
        if approved:
            b += ["この回で承認された画面\n",
                  _table(["コード", "画面名", "設計者", "状態"],
                         [(s["code"], s["name"], s["designer"], s["status"])
                          for s in approved]), ""]
        if reviews:
            b += ["この回に出た指摘\n",
                  _table(["#", "画面", "段階", "指摘者", "内容", "解消"],
                         [(r["id"], "{} {}".format(r["scode"], r["sname"]),
                           r["stage"], r["reviewer"], r["comment"],
                           "済" if r["resolved"] else "未") for r in reviews]), ""]

    feats = con.execute(
        "SELECT * FROM feature WHERE judged_meeting_id=? ORDER BY code",
        (mid,)).fetchall()
    if feats:
        b += ["## 機能追加の裁定\n",
              _table(["コード", "機能名", "判定", "備考"],
                     [(f["code"], f["name"], f["judgment"], f["note"])
                      for f in feats]), ""]

    # 決定権と枠は会議ごとにリセットされる現在値なので、直近の回にだけ載せる
    if latest:
        b += ["## 現時点の状態\n",
              "決定権 **{}** ／ 部長への即時確認 残り {} ／ 管理者への緊急相談 残り {}".format(
                  get_state(con, "decision_authority", "未確認"),
                  get_state(con, "boss_confirm_quota", "2"),
                  get_state(con, "escalate_quota", "2")), ""]

    nxt = _col(m, "next_step")
    if nxt:
        b += ["## 次に開くべき会議\n", nxt, ""]

    # 発言の原文は載せない（長くなるため）。u#NN は /recall で引ける
    b += ["---\n",
          "_根拠発言の原文は `python scripts/query.py --utterance NN`、"
          "決定から辿るなら `--decision NN` で引けます。_\n",
          "_生成: {}_".format(now())]
    return "\n".join(b)


def main() -> None:
    ap = argparse.ArgumentParser(description="会議1回分の備忘を output/ に書き出す")
    ap.add_argument("--meeting", type=int, help="第N回だけ生成する（省略時は全回）")
    ap.add_argument("--latest", action="store_true", help="直近の1回だけ生成する")
    args = ap.parse_args()

    con = connect()
    try:
        rows = con.execute("SELECT * FROM meeting ORDER BY seq").fetchall()
        if not rows:
            print("まだ会議は開かれていません。")
            return
        last_seq = rows[-1]["seq"]
        if args.meeting:
            rows = [r for r in rows if r["seq"] == args.meeting]
            if not rows:
                sys.exit("第{}回はありません".format(args.meeting))
        elif args.latest:
            rows = rows[-1:]

        OUT.mkdir(parents=True, exist_ok=True)
        for m in rows:
            path = OUT / "備忘_{:02d}.md".format(m["seq"])
            path.write_text(build(con, m, m["seq"] == last_seq), encoding="utf-8")
            print("生成: output/{}".format(path.name))
    finally:
        con.close()
    print("({})".format(now()))


if __name__ == "__main__":
    main()
