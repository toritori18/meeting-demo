"""発言・決定・宿題・確定事実の横断検索。/recall の実体。

「言った言わない」を制するための道具。

日本語なので FTS5 ではなく LIKE の部分一致。ただし発言本文だけを引くと
「件数」で検索しても「何件くらい」にヒットしない、という取りこぼしが起きる。
そこで decision / issue / fact も併せて検索する。fact は topic に整理された
話題語が入っているので、この取りこぼしの橋渡しになる。

    python scripts/query.py 監査ログ
    python scripts/query.py 保存 --speaker client-boss
    python scripts/query.py 件数 --utterances-only
    python scripts/query.py --decision 3        # 決定 #3 の根拠発言を辿る
    python scripts/query.py --utterance 42      # 発言 #42 の前後を見る
"""
from __future__ import annotations

import argparse
import textwrap

from db_init import connect

WIDTH = 100
RULE = "─" * WIDTH


def _label(con, mid):
    if not mid:
        return "(会議外)"
    row = con.execute("SELECT seq, purpose FROM meeting WHERE id=?", (mid,)).fetchone()
    return "第{}回({})".format(row["seq"], row["purpose"]) if row else "(不明)"


def _print_utterances(con, rows, snippet_for=None):
    for r in rows:
        print(RULE)
        print("u#{}  {}  [{}]  {}".format(
            r["id"], r["spoken_at"], r["speaker"], _label(con, r["meeting_id"])))
        if r["topic"]:
            print("議題: {}".format(r["topic"]))
        body = r["body"]
        if snippet_for and len(body) > 600:
            pos = body.find(snippet_for)
            if pos >= 0:
                start = max(0, pos - 200)
                body = ("…" if start else "") + body[start:pos + 400] + "…"
        for line in body.splitlines():
            print(textwrap.fill(line, WIDTH) if line.strip() else "")
    print(RULE)


def _like_clause(column, keywords, params):
    for kw in keywords:
        params.append("%{}%".format(kw))
    return " AND ".join(["{} LIKE ?".format(column)] * len(keywords))


def search_utterances(con, kws, speaker, meeting, limit):
    sql = "SELECT u.* FROM utterance u"
    where, params = [], []
    if meeting:
        sql += " JOIN meeting m ON m.id = u.meeting_id"
        where.append("m.seq = ?")
        params.append(meeting)
    if kws:
        where.append("(" + _like_clause("u.body", kws, params) + ")")
    if speaker:
        where.append("u.speaker = ?")
        params.append(speaker)
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY u.id LIMIT ?"
    params.append(limit)
    return con.execute(sql, params).fetchall()


def search_related(con, kws, limit):
    """決定・宿題・確定事実からもキーワードを探す。"""
    out = {}
    if not kws:
        return out

    params = []
    clause = _like_clause("body", kws, params)
    params.append(limit)
    out["決定"] = con.execute(
        "SELECT id, meeting_id, body, status, decided_by, utterance_id "
        "FROM decision WHERE {} ORDER BY id LIMIT ?".format(clause), params).fetchall()

    params = []
    clause = _like_clause("body", kws, params)
    params.append(limit)
    out["宿題"] = con.execute(
        "SELECT id, meeting_id, body, owner, due, state "
        "FROM issue WHERE {} ORDER BY id LIMIT ?".format(clause), params).fetchall()

    # fact は topic と body の両方を対象にする（話題語での取りこぼし対策）
    params = []
    clause = "(" + _like_clause("topic", kws, params) + ") OR (" \
             + _like_clause("body", kws, params) + ")"
    params.append(limit)
    out["確定事実"] = con.execute(
        "SELECT id, meeting_id, topic, body, stated_by, utterance_id "
        "FROM fact WHERE {} ORDER BY id LIMIT ?".format(clause), params).fetchall()

    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="発言・決定・宿題・事実を横断検索する")
    ap.add_argument("keyword", nargs="*", help="全部含むものを探す（AND）")
    ap.add_argument("--speaker", help="話者で絞る（発言のみ）")
    ap.add_argument("--meeting", type=int, help="会議の第N回で絞る（発言のみ）")
    ap.add_argument("--decision", type=int, help="決定IDから根拠発言を辿る")
    ap.add_argument("--utterance", type=int, help="発言IDとその前後2件を見る")
    ap.add_argument("--utterances-only", action="store_true", help="発言だけ検索する")
    ap.add_argument("--limit", type=int, default=30)
    args = ap.parse_args()

    con = connect()
    try:
        if args.decision:
            d = con.execute("SELECT * FROM decision WHERE id=?",
                            (args.decision,)).fetchone()
            if not d:
                print("決定 #{} は存在しません".format(args.decision))
                return
            print("決定 #{} [{}] {}".format(d["id"], d["status"], d["body"]))
            print("決めた人: {} / 根拠: {}".format(d["decided_by"] or "-",
                                                  d["rationale"] or "-"))
            print("会議: {}\n".format(_label(con, d["meeting_id"])))
            if d["utterance_id"]:
                _print_utterances(con, con.execute(
                    "SELECT * FROM utterance WHERE id=?",
                    (d["utterance_id"],)).fetchall())
            else:
                print("根拠発言が紐づいていません。")
            return

        if args.utterance:
            row = con.execute("SELECT * FROM utterance WHERE id=?",
                              (args.utterance,)).fetchone()
            if not row:
                print("発言 #{} は存在しません".format(args.utterance))
                return
            _print_utterances(con, con.execute(
                "SELECT * FROM utterance WHERE meeting_id IS ? AND seq BETWEEN ? AND ? "
                "ORDER BY seq",
                (row["meeting_id"], row["seq"] - 2, row["seq"] + 2)).fetchall())
            return

        kws = args.keyword
        utts = search_utterances(con, kws, args.speaker, args.meeting, args.limit)
        print("■ 発言 {} 件".format(len(utts)))
        if utts:
            _print_utterances(con, utts, snippet_for=kws[0] if kws else None)
        else:
            print("（該当なし）")

        if args.utterances_only or not kws:
            return

        related = search_related(con, kws, args.limit)
        for kind, rows in related.items():
            if not rows:
                continue
            print("\n■ {} {} 件".format(kind, len(rows)))
            for r in rows:
                keys = r.keys()
                head = "#{}  {}".format(r["id"], _label(con, r["meeting_id"]))
                if "status" in keys:
                    head += "  [{}]".format(r["status"])
                if "state" in keys:
                    head += "  [{}]".format(r["state"])
                if "topic" in keys:
                    head += "  話題:{}".format(r["topic"])
                print("  " + head)
                print("    " + r["body"])
                if "utterance_id" in keys and r["utterance_id"]:
                    print("    → 根拠発言 u#{} （query.py --utterance {} で参照）".format(
                        r["utterance_id"], r["utterance_id"]))

        if not utts and not any(related.values()):
            print("\nどこにも該当しませんでした。別の語で試してください。")
    finally:
        con.close()


if __name__ == "__main__":
    main()
