"""業務側の正解ファイルへのアクセスを記録する PreToolUse フック。

情報の非対称（`sys-staff` は `docs/90_ground-truth.md` を読まない）は
エージェントファイルに書かれた規律であって、技術的な強制ではない。
このフックは規律が守られているかを**検証可能**にする。

    python .claude/hooks/audit.py --hook

ブロックはしない（業務側ペルソナは正当に読む必要があるため、
呼び出し元をフックから判別できない以上、一律に止めると成立しなくなる）。
記録だけ残し、`/status` が件数を報告する。

フックはセッションを壊してはならないので、何があっても exit 0 で終わる。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

from pathlib import Path

# 共通ヘルパは scripts/ にある。このフックは .claude/hooks/ に置いてあるので、
# import パスに scripts/ を足してから読み込む。
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from db_init import connect, current_meeting_id, now

# 監視対象。読まれたことが分かるべきファイル
#   90_ground-truth       業務側の正解。読んでよいのは client-boss / client-staff だけ
#   99_supervisor-checklist 監督専用。エージェントは誰も読んではいけない
WATCHED = ("90_ground-truth", "99_supervisor-checklist")

WATCHED_TOOLS = ("Read", "Grep", "Glob", "Bash")

# **読まないために**ファイル名を書いた命令は、アクセスではない。
# `grep --exclude="90_ground-truth.md"` を「読んだ」と数えると、監査が誤検知で
# 埋まって本物が見えなくなる。走査の前にこの手の指定を落とす。
EXCLUSION_RE = re.compile(
    r"""--exclude(?:-dir|-from)?=\s*['"]?[^\s'"]+"""   # grep / rg の除外
    r"""|-g\s+['"]?![^\s'"]+"""                        # rg -g '!...'
)


def hit(text: str) -> str | None:
    """監視対象ファイルを**読もうとしている**なら、そのファイル名を返す。"""
    stripped = EXCLUSION_RE.sub(" ", text)
    for needle in WATCHED:
        if needle in stripped:
            return needle
    return None


def _collect_strings(obj, out, depth=0):
    if depth > 6:
        return
    if isinstance(obj, str):
        out.append(obj)
    elif isinstance(obj, dict):
        for v in obj.values():
            _collect_strings(v, out, depth + 1)
    elif isinstance(obj, list):
        for v in obj:
            _collect_strings(v, out, depth + 1)


def record(tool: str, target: str, detail: str) -> None:
    con = connect()
    try:
        con.execute(
            "INSERT INTO access_log(meeting_id,tool,target,detail,accessed_at) "
            "VALUES(?,?,?,?,?)",
            (current_meeting_id(con), tool, target, detail[:2000], now()),
        )
        con.commit()
    finally:
        con.close()


def run_hook() -> None:
    try:
        raw = sys.stdin.buffer.read().decode("utf-8", errors="replace")
        if not raw.strip():
            return
        payload = json.loads(raw)
        tool = payload.get("tool_name") or payload.get("toolName") or ""
        if tool not in WATCHED_TOOLS:
            return

        tin = payload.get("tool_input") or payload.get("toolInput") or {}
        strings: list[str] = []
        _collect_strings(tin, strings)
        joined = " ".join(strings)

        needle = hit(joined)
        if needle:
            record(tool, needle, joined)
    except Exception:
        if os.environ.get("MEETING_HOOK_DEBUG"):
            import traceback
            traceback.print_exc(file=sys.stderr)


def report() -> None:
    """アクセス記録を表示する（/status から呼ばれる）。"""
    con = connect()
    try:
        rows = con.execute(
            "SELECT a.*, m.seq AS mseq FROM access_log a "
            "LEFT JOIN meeting m ON m.id = a.meeting_id ORDER BY a.id"
        ).fetchall()
        if not rows:
            print("業務側正解ファイルへのアクセス: なし")
            return
        print("業務側正解ファイルへのアクセス: {} 件".format(len(rows)))
        print("（会議中は client-boss / client-staff だけが読むはず。"
              "会議外や不自然に多い場合は情報の非対称が崩れている疑い）")
        for r in rows:
            label = "第{}回".format(r["mseq"]) if r["mseq"] else "会議外"
            print("  #{} {} [{}] {} — {}".format(
                r["id"], r["accessed_at"], label, r["tool"], r["detail"][:90]))
    finally:
        con.close()


def main() -> None:
    ap = argparse.ArgumentParser(description="正解ファイルへのアクセス監査")
    ap.add_argument("--hook", action="store_true", help="stdin の JSON から記録")
    ap.add_argument("--report", action="store_true", help="記録を表示")
    args = ap.parse_args()

    if args.hook:
        run_hook()
        sys.exit(0)
    report()


if __name__ == "__main__":
    main()
