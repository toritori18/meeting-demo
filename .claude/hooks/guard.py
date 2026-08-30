"""自動生成ファイルへの直接書き込みを止める PreToolUse フック。

docs/01 02 03 04 21 は scripts/views.py が DB から生成する。直接編集しても
その場は成功して見え、次の views.py 実行で黙って消える。気づくのは書いた
本人ではないので、記録では間に合わない。誰がいつ書いても常に間違い＝判断の
余地がない禁止なので、audit.py と違ってここは**ブロックする**。

    python .claude/hooks/guard.py --hook

監視対象は views.py の VIEWS から取る。docs の採番を変えてもここは直さなくてよい。

止めるのは Edit / Write と、Bash の書き込み（リダイレクト・tee・sed -i）だけ。
読み取りは素通しする。フックはセッションを壊してはならないので、判断がつかない
ものは通し、何があっても exit 0 で終わる。
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

from views import VIEWS

# {"01_session-log.md", "02_decision-log.md", ...}
GENERATED = {filename for filename, _ in VIEWS.values()}

EDIT_TOOLS = ("Edit", "Write", "MultiEdit", "NotebookEdit")

REASON = (
    "{name} は scripts/views.py がDBから生成するビューです。直接編集しても"
    "次の views.py 実行で消えます。DBを scripts/record.py で更新し、"
    "python scripts/views.py で再生成してください。"
)


def _edit_hit(path: str) -> str | None:
    """Edit/Write の対象が自動生成ファイルなら、そのファイル名を返す。"""
    name = path.replace("\\", "/").rstrip("/").rsplit("/", 1)[-1]
    return name if name in GENERATED else None


def _bash_hit(command: str) -> str | None:
    """Bash が自動生成ファイルに**書こうとしている**ならファイル名を返す。

    `grep foo docs/02_decision-log.md > out.txt` のような読み取りを巻き込ま
    ないため、パスが書き込み側に現れる形だけを見る。
    """
    for name in GENERATED:
        esc = re.escape(name)
        patterns = (
            r">>?\s*['\"]?[^\s'\"|;&]*" + esc,   # > docs/02_...  >> docs/02_...
            r"\btee\b[^;|&]*" + esc,             # ... | tee docs/02_...
            r"\bsed\b[^;|&]*\s-i[^;|&]*" + esc,  # sed -i ... docs/02_...
        )
        if any(re.search(p, command) for p in patterns):
            return name
    return None


def deny(name: str) -> None:
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": REASON.format(name=name),
        }
    }, ensure_ascii=False))


def run_hook() -> None:
    try:
        raw = sys.stdin.buffer.read().decode("utf-8", errors="replace")
        if not raw.strip():
            return
        payload = json.loads(raw)
        tool = payload.get("tool_name") or payload.get("toolName") or ""
        tin = payload.get("tool_input") or payload.get("toolInput") or {}

        hit = None
        if tool in EDIT_TOOLS:
            target = tin.get("file_path") or tin.get("notebook_path") or ""
            hit = _edit_hit(str(target))
        elif tool == "Bash":
            hit = _bash_hit(str(tin.get("command") or ""))

        if hit:
            deny(hit)
    except Exception:
        # 判断がつかないものは通す。原因を追うときは MEETING_HOOK_DEBUG=1。
        if os.environ.get("MEETING_HOOK_DEBUG"):
            import traceback
            traceback.print_exc(file=sys.stderr)


def main() -> None:
    ap = argparse.ArgumentParser(description="自動生成ファイルへの直接書き込みを止める")
    ap.add_argument("--hook", action="store_true", help="stdin の JSON から判定")
    ap.add_argument("--list", action="store_true", help="監視対象を並べる")
    args = ap.parse_args()

    if args.list:
        for name in sorted(GENERATED):
            print("docs/{}".format(name))
        return
    if args.hook:
        run_hook()
    sys.exit(0)


if __name__ == "__main__":
    main()
