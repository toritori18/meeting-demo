"""DB から Markdown ビューを再生成する。

エージェントが毎回読むのはこのビュー（軽い）。DBが正。
    python scripts/views.py            # 全部再生成
    python scripts/views.py --only decisions   # 一部だけ
    （指定できるキー: sessions / decisions / issues / facts / screens）
"""
from __future__ import annotations

import argparse

from db_init import DOCS, connect, get_state, now

HEADER = "<!-- このファイルは scripts/views.py が DB から自動生成します。直接編集しないでください。 -->\n"


def _table(headers, rows):
    out = ["| " + " | ".join(headers) + " |",
           "|" + "|".join(["---"] * len(headers)) + "|"]
    for r in rows:
        cells = ["" if c is None else str(c).replace("\n", " ").replace("|", "\\|")
                 for c in r]
        out.append("| " + " | ".join(cells) + " |")
    return "\n".join(out)


def _meeting_label(con, mid):
    if not mid:
        return ""
    row = con.execute("SELECT seq FROM meeting WHERE id=?", (mid,)).fetchone()
    return "第{}回".format(row["seq"]) if row else ""


def view_decision(con):
    rows = con.execute(
        "SELECT d.id, d.meeting_id, d.body, d.status, d.decided_by, d.rationale, "
        "d.utterance_id, d.decided_at FROM decision d ORDER BY d.id"
    ).fetchall()
    body = [HEADER, "# 決定事項\n"]
    prov = [r for r in rows if r["status"] == "仮"]
    body.append("決定 {} 件（うち **仮決め {} 件**）\n".format(len(rows), len(prov)))
    if prov:
        body.append("## 仮決めのまま残っている項目\n")
        body.append("会議の冒頭で必ずリマインドし、本決めへの昇格を促すこと。\n")
        body.append(_table(
            ["#", "決定日", "決定事項", "決めた人"],
            [(r["id"], _meeting_label(con, r["meeting_id"]), r["body"], r["decided_by"])
             for r in prov]))
        body.append("")
    body.append("## 全決定\n")
    if rows:
        body.append(_table(
            ["#", "会議", "決定事項", "仮/本", "決めた人", "根拠", "根拠発言"],
            [(r["id"], _meeting_label(con, r["meeting_id"]), r["body"], r["status"],
              r["decided_by"], r["rationale"],
              "u#{}".format(r["utterance_id"]) if r["utterance_id"] else "")
             for r in rows]))
    else:
        body.append("_まだ決定はありません。_")
    body.append("")
    return "\n".join(body)


def view_issues(con):
    rows = con.execute("SELECT * FROM issue ORDER BY state DESC, id").fetchall()
    open_rows = [r for r in rows if r["state"] == "open"]
    body = [HEADER, "# 宿題・未決事項\n"]
    body.append("未消化 **{} 件** / 全 {} 件\n".format(len(open_rows), len(rows)))
    body.append("## 枠の残り\n")
    body.append("- 部長への即時確認: 残り {} / 2".format(get_state(con, "boss_confirm_quota", "2")))
    body.append("- 管理者への緊急相談: 残り {} / 2\n".format(get_state(con, "escalate_quota", "2")))
    body.append("## 未消化\n")
    if open_rows:
        body.append(_table(
            ["#", "起票", "内容", "担当", "期限"],
            [(r["id"], _meeting_label(con, r["meeting_id"]), r["body"],
              r["owner"], r["due"]) for r in open_rows]))
    else:
        body.append("_未消化の宿題はありません。_")
    closed = [r for r in rows if r["state"] != "open"]
    if closed:
        body.append("\n## 消化済み\n")
        body.append(_table(
            ["#", "起票", "内容", "担当", "消化"],
            [(r["id"], _meeting_label(con, r["meeting_id"]), r["body"], r["owner"],
              _meeting_label(con, r["closed_meeting_id"])) for r in closed]))
    body.append("")
    return "\n".join(body)


def view_sessions(con):
    rows = con.execute("SELECT * FROM meeting ORDER BY seq").fetchall()
    body = [HEADER, "# 開催履歴\n"]
    if not rows:
        body.append("_まだ会議は開かれていません。_\n")
        return "\n".join(body)
    for m in rows:
        parts = con.execute(
            "SELECT agent, mode FROM participant WHERE meeting_id=? ORDER BY id",
            (m["id"],)).fetchall()
        n_utt = con.execute(
            "SELECT COUNT(*) AS n FROM utterance WHERE meeting_id=?",
            (m["id"],)).fetchone()["n"]
        n_dec = con.execute(
            "SELECT COUNT(*) AS n FROM decision WHERE meeting_id=?",
            (m["id"],)).fetchone()["n"]
        body.append("## 第{}回 — {}\n".format(m["seq"], m["purpose"]))
        body.append("- 開始: {} / 終了: {}".format(m["opened_at"], m["closed_at"] or "（進行中）"))
        body.append("- 参加: " + ", ".join(
            "{}({})".format(p["agent"], p["mode"]) for p in parts))
        body.append("- 発言 {} 件 / 決定 {} 件".format(n_utt, n_dec))
        if m["summary"]:
            body.append("- 総括: {}".format(m["summary"]))
        body.append("")
    return "\n".join(body)


def view_screens(con):
    rows = con.execute("SELECT * FROM screen ORDER BY code").fetchall()
    body = [HEADER, "# 画面設計\n"]
    body.append("承認フロー: 未着手 → 設計中 → 社内レビュー中 → 社内OK → "
                "業務担当者レビュー中 → (差戻し) → 承認済\n")
    body.append("**新人が設計した画面は、社内レビューを通さずに業務担当者へ出さないこと。**\n")
    body.append("**承認済みでない画面の詳細仕様は書かないこと。**\n")
    if not rows:
        body.append("## 画面一覧\n")
        body.append("_まだ画面は登録されていません。sys-staff / sys-junior が設計して登録します。_\n")
        return "\n".join(body)
    body.append("## 画面一覧\n")
    body.append(_table(
        ["コード", "画面名", "機能区分", "設計者", "状態", "承認", "概要"],
        [(r["code"], r["name"], r["area"], r["designer"], r["status"],
          _meeting_label(con, r["approved_meeting_id"]), r["summary"]) for r in rows]))
    for r in rows:
        reviews = con.execute(
            "SELECT * FROM screen_review WHERE screen_id=? ORDER BY id",
            (r["id"],)).fetchall()
        if not r["wireframe"] and not reviews:
            continue
        body.append("\n## {} {}\n".format(r["code"], r["name"]))
        if r["wireframe"]:
            body.append("```\n" + r["wireframe"] + "\n```\n")
        if reviews:
            body.append("### 指摘\n")
            body.append(_table(
                ["#", "段階", "指摘者", "内容", "解消"],
                [(v["id"], v["stage"], v["reviewer"], v["comment"],
                  "済" if v["resolved"] else "未") for v in reviews]))
    body.append("")
    return "\n".join(body)


def view_facts(con):
    auth = get_state(con, "decision_authority", "未確認")
    rows = con.execute("SELECT * FROM fact ORDER BY id").fetchall()
    body = [HEADER, "# 確定事実\n"]
    body.append("## 決定権ステータス\n")
    body.append("**{}**\n".format(auth))
    body.append({
        "未確認": "部下は判断を伴う質問に「部長に確認します」と答える。"
                  "sys-staff が業務担当者に明示的に確認するまでこのまま。",
        "委譲済み": "部下は分かる範囲で自分で決めてよい。仮決めにも応じる。",
        "部長のみ": "部下は事実は答えるが一切決めない。",
    }.get(auth, ""))
    body.append("\n## エージェントが述べた具体値\n")
    body.append("各エージェントは発言前にここを読み、過去の自分の発言と矛盾しないこと。\n")
    if rows:
        body.append(_table(
            ["#", "会議", "話題", "内容", "述べた人", "根拠発言"],
            [(r["id"], _meeting_label(con, r["meeting_id"]), r["topic"], r["body"],
              r["stated_by"], "u#{}".format(r["utterance_id"]) if r["utterance_id"] else "")
             for r in rows]))
    else:
        body.append("_まだ確定事実はありません。_")
    body.append("")
    return "\n".join(body)


# キーは番号ではなく名前にしてある。docs の採番を変えても壊れないため。
VIEWS = {
    "sessions":  ("01_session-log.md", view_sessions),
    "decisions": ("02_decision-log.md", view_decision),
    "issues":    ("03_open-issues.md", view_issues),
    "facts":     ("04_established-facts.md", view_facts),
    "screens":   ("21_screen-design.md", view_screens),
}


def main() -> None:
    ap = argparse.ArgumentParser(description="DB から Markdown ビューを再生成")
    ap.add_argument("--only", choices=sorted(VIEWS), action="append",
                    help="再生成するビューを絞る（複数指定可）")
    args = ap.parse_args()

    DOCS.mkdir(parents=True, exist_ok=True)
    con = connect()
    try:
        targets = args.only or sorted(VIEWS)
        for key in targets:
            filename, fn = VIEWS[key]
            (DOCS / filename).write_text(fn(con), encoding="utf-8")
            print("生成: docs/{}".format(filename))
    finally:
        con.close()
    print("({})".format(now()))


if __name__ == "__main__":
    main()
