"""会議の持ち時間を管理する。

実時間ではなく**シミュレート上の会議時間**を扱う。発言1件ごとに想定所要時間
（司会1分／エージェント3分／監督0分）を積み上げ、持ち時間に対する残りを出す。

これがあると「1回30分の実会議」に相当する分量で区切れる。区切ると:
  - 現実の進行に近くなる（1回で全部は決まらない）
  - エージェント呼び出しが 8〜12 回に収まり、コストが下がる
  - 何を今日話すかの優先順位づけが練習になる

    python scripts/clock.py              # 残り時間を出す
    python scripts/clock.py --detail     # 何に時間を使ったかの内訳
    python scripts/clock.py --budget 45  # 進行中の会議の持ち時間を変更
"""
from __future__ import annotations

import argparse

from db_init import connect, current_meeting_id

BAR_WIDTH = 40


def _bar(used: int, budget: int) -> str:
    if budget <= 0:
        return ""
    filled = min(BAR_WIDTH, round(BAR_WIDTH * used / budget))
    over = used > budget
    ch = "!" if over else "#"
    return "[" + ch * filled + "." * (BAR_WIDTH - filled) + "]"


def status(con, mid: int) -> dict:
    m = con.execute("SELECT * FROM meeting WHERE id=?", (mid,)).fetchone()
    used = con.execute(
        "SELECT COALESCE(SUM(minutes),0) AS n FROM utterance WHERE meeting_id=?",
        (mid,),
    ).fetchone()["n"]
    budget = m["budget_min"] or 30
    return {
        "seq": m["seq"], "purpose": m["purpose"],
        "budget": budget, "used": used, "left": budget - used,
    }


def advice(left: int, budget: int) -> str:
    if left <= 0:
        return ("★時間切れ。新しい論点には入らないこと。決まったことを記録し、"
                "残りは宿題にして閉会する（/meeting-close）")
    if left <= 5:
        return ("★残りわずか。着地に入る。いま議論中の論点だけ片付け、"
                "新しい議題は開かない。決めきれないものは仮決めか宿題に")
    if left <= budget // 3:
        return "終盤。あと1〜2論点。広げずに絞ること"
    return "まだ余裕あり"


def main() -> None:
    ap = argparse.ArgumentParser(description="会議の持ち時間を見る")
    ap.add_argument("--detail", action="store_true", help="時間の内訳を出す")
    ap.add_argument("--budget", type=int, help="持ち時間を変更する（分）")
    args = ap.parse_args()

    con = connect()
    try:
        mid = current_meeting_id(con)
        if not mid:
            print("進行中の会議はありません。")
            return

        if args.budget:
            con.execute("UPDATE meeting SET budget_min=? WHERE id=?", (args.budget, mid))
            con.commit()
            print("持ち時間を {} 分に変更しました。".format(args.budget))

        st = status(con, mid)
        print("第{}回 — {}".format(st["seq"], st["purpose"]))
        print("{}  {} / {} 分 使用、残り {} 分".format(
            _bar(st["used"], st["budget"]), st["used"], st["budget"], st["left"]))
        print(advice(st["left"], st["budget"]))

        if args.detail:
            print("\n内訳（話者別）")
            rows = con.execute(
                "SELECT speaker, COUNT(*) c, COALESCE(SUM(minutes),0) m "
                "FROM utterance WHERE meeting_id=? GROUP BY speaker ORDER BY m DESC",
                (mid,)).fetchall()
            for r in rows:
                print("  {:<14} {:>2}件  {:>3}分".format(r["speaker"], r["c"], r["m"]))
            print("\n内訳（議題別）")
            rows = con.execute(
                "SELECT COALESCE(topic,'(未設定)') t, COUNT(*) c, COALESCE(SUM(minutes),0) m "
                "FROM utterance WHERE meeting_id=? GROUP BY t ORDER BY m DESC",
                (mid,)).fetchall()
            for r in rows:
                print("  {:<20} {:>2}件  {:>3}分".format(r["t"], r["c"], r["m"]))
    finally:
        con.close()


if __name__ == "__main__":
    main()
