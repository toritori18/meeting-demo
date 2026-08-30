"""発言を utterance テーブルに記録する。

2つの使い方がある:

1) 明示呼び出し（司会・監督の発言、フォールバック時のエージェント発言）
     python scripts/log.py --speaker 司会 --body "では次の議題に移ります" [--topic 出力機能]

2) PostToolUse フック（stdin に JSON）
     python scripts/log.py --hook
   Agent / SendMessage の応答を拾ってエージェント発言として記録する。
   フックはセッションを壊してはならないので、何があっても exit 0 で終わる。
"""
from __future__ import annotations

import argparse
import json
import os
import sys

from db_init import connect, current_meeting_id, estimate_minutes, now

# フック経由で拾った出力を、どのエージェントの発言として記録するか
AGENT_NAMES = {
    "sys-manager",
    "sys-staff",
    "client-boss",
    "client-staff",
    "sys-junior",
}

MAX_BODY = 20000


def _clean(text: str | None) -> str | None:
    """サロゲートを含む文字列は SQLite に書けないので落とす。"""
    if text is None:
        return None
    return text.encode("utf-8", errors="replace").decode("utf-8")


def insert(speaker: str, body: str, topic: str | None = None,
           meeting_id: int | None = None, minutes: int | None = None) -> int:
    speaker, body, topic = _clean(speaker), _clean(body), _clean(topic)
    if minutes is None:
        minutes = estimate_minutes(speaker)
    con = connect()
    try:
        if meeting_id is None:
            meeting_id = current_meeting_id(con)
        row = con.execute(
            "SELECT COALESCE(MAX(seq),0)+1 AS n FROM utterance WHERE meeting_id IS ?",
            (meeting_id,),
        ).fetchone()
        seq = row["n"]
        cur = con.execute(
            "INSERT INTO utterance(meeting_id,seq,speaker,topic,body,spoken_at,minutes) "
            "VALUES(?,?,?,?,?,?,?)",
            (meeting_id, seq, speaker, topic, body[:MAX_BODY], now(), minutes),
        )
        con.commit()
        return cur.lastrowid
    finally:
        con.close()


def _dig(obj, keys):
    """ネストした dict から最初に見つかった文字列を返す。"""
    if isinstance(obj, str):
        return obj
    if isinstance(obj, dict):
        for k in keys:
            if k in obj:
                found = _dig(obj[k], keys)
                if found:
                    return found
        for v in obj.values():
            found = _dig(v, keys)
            if found:
                return found
    if isinstance(obj, list):
        parts = [p for p in (_dig(v, keys) for v in obj) if p]
        if parts:
            return "\n".join(parts)
    return None


def run_hook() -> None:
    """PostToolUse フック本体。失敗しても静かに終わる。"""
    try:
        # stdin はロケール依存の text ではなく UTF-8 バイトとして読む。
        # Windows の既定コーデック(cp932)で読むとサロゲートが混入し、
        # SQLite への書き込みが UnicodeEncodeError で落ちる。
        raw = sys.stdin.buffer.read().decode("utf-8", errors="replace")
        if not raw.strip():
            return
        payload = json.loads(raw)
        tool = payload.get("tool_name") or payload.get("toolName") or ""
        if tool not in ("Agent", "SendMessage", "Task"):
            return

        tin = payload.get("tool_input") or payload.get("toolInput") or {}
        tout = payload.get("tool_response") or payload.get("toolResponse") or {}

        speaker = (
            tin.get("subagent_type")
            or tin.get("to")
            or tin.get("agent")
            or "agent"
        )
        speaker = str(speaker).strip()
        # ListAgents 由来の "name [ref]" 形式に備えて先頭語だけ採る
        speaker = speaker.split(" ")[0]
        if speaker not in AGENT_NAMES and speaker != "agent":
            # 未知の名前でも記録はする（後で追跡できるように）
            pass

        body = _dig(tout, ["content", "text", "result", "output", "report", "message"])
        if not body:
            body = json.dumps(tout, ensure_ascii=False)[:MAX_BODY]
        if not body.strip():
            return

        insert(speaker, body, topic=None)
    except Exception:
        # フックは絶対にセッションを止めない。
        # 原因を追いたいときは MEETING_HOOK_DEBUG=1 を立てる。
        if os.environ.get("MEETING_HOOK_DEBUG"):
            import traceback
            traceback.print_exc(file=sys.stderr)


def main() -> None:
    ap = argparse.ArgumentParser(description="発言をDBに記録する")
    ap.add_argument("--hook", action="store_true", help="stdin の JSON から記録")
    ap.add_argument("--speaker")
    ap.add_argument("--body")
    ap.add_argument("--topic")
    ap.add_argument("--meeting-id", type=int)
    ap.add_argument("--minutes", type=int,
                    help="この発言の想定所要時間（分）。省略時は話者から自動見積もり")
    args = ap.parse_args()

    if args.hook:
        run_hook()
        sys.exit(0)

    if not args.speaker or not args.body:
        ap.error("--speaker と --body は必須（--hook を使わない場合）")

    uid = insert(args.speaker, args.body, args.topic, args.meeting_id, args.minutes)
    print(f"utterance #{uid} 記録: {args.speaker}")


if __name__ == "__main__":
    main()
