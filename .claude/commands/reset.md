---
description: 会議の記録をリセットして最初からやり直す。DBはアーカイブされるので過去の回と比較できる
argument-hint: [理由やラベル]
allowed-tools: Bash, Read
---

リセット: **$ARGUMENTS**

## 何のためにあるか

同じ条件で会議をもう一度回し、**エージェントの挙動が毎回同じでないこと**を確かめるために使います。介入が脚本化されていれば毎回同じ順で同じ台詞が出ます。そうなっていないかを見るのがこのコマンドの主目的です。

リハーサル（本番前に冒頭だけ回して部長の圧の強度を調整する）にも使います。

## 手順

**破壊的な操作なので、必ず監督に確認してから実行してください。** 何が消えて何が残るかを先に提示します。

1. 現状を要約する（会議数・発言数・決定数・画面数）
2. アーカイブする
   ```bash
   mkdir -p db/archive
   cp db/meeting.db "db/archive/meeting_$(date +%Y%m%d_%H%M%S).db"
   ```
3. 消える／残るものを提示して確認を取る

| 消える | 残る |
|---|---|
| 会議・発言・決定・宿題・画面・機能・確定事実 | `docs/90_ground-truth.md`（業務側の設定） |
| 決定権ステータス（未確認に戻る） | `docs/10_tobe-flow.md` / `12_briefing.md` |
| 各種枠 | エージェント定義・コマンド・スキル |
| 自動生成のMarkdownビュー | `docs/20_requirements-draft.md` / `22_detail-spec.md`（**手動で消す判断が要る**） |

4. 実行する
   ```bash
   rm -f db/meeting.db
   python scripts/db_init.py
   python scripts/views.py
   python scripts/export_excel.py
   ```

5. `docs/00_question-list.md` `20_requirements-draft.md` `22_detail-spec.md` は `sys-staff` の執筆物でDBから再生成されません。**前回の内容を残すか消すかを監督に確認してください。**
   - 残す → 前回の成果を引き継いで2周目をやる
   - 消す → まっさらな状態で比較する（挙動の違いを見るならこちら）

## アーカイブの参照

過去の回を見るには一時的に差し替えます。

```bash
cp db/archive/meeting_YYYYMMDD_HHMMSS.db /tmp/old.db
python -c "import sys;sys.path.insert(0,'scripts');import sqlite3;c=sqlite3.connect('/tmp/old.db');c.row_factory=sqlite3.Row;[print(r['speaker'],'|',r['body'][:60]) for r in c.execute('SELECT speaker,body FROM utterance ORDER BY id')]"
```

リセット後、アーカイブのパスと現在の状態を報告してください。
