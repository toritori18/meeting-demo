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
| 決定権ステータス（初期値「委譲済み」に戻る） | `docs/10_tobe-flow.md` / `12_briefing.md` |
| 各種枠 | エージェント定義・コマンド・スキル |
| 自動生成のMarkdownビュー | `docs/20_requirements-draft.md` / `22_detail-spec.md`（**手動で消す判断が要る**） |

4. 実行する
   ```bash
   rm -f db/meeting.db
   python scripts/db_init.py

   # 案件開始時に確定済みの前提を戻す。
   # キックオフは会議の型から外してあるため、ここで初期値として与えないと
   # 決定権が「未確認」のままになり、「要件を詰める」が空転する。
   python scripts/record.py state --key decision_authority --value "委譲済み"
   python scripts/record.py decision --status 本 --by client-boss      --body "業務ルール（判定基準など）と画面の作りは client-staff の判断で決めてよい。部長（client-boss）の決定として扱う。ただし予算・納期・スコープが変わる話は必ず部長に上げること。"      --rationale "案件開始時に業務担当者（部長）から明示された前提。会議で決め直さない。"
   python scripts/record.py decision --status 本 --by client-boss      --body "成功基準は「速さより正確さ」。突合の見落としをなくすことを最優先し、判定に迷うものは機械的に流さず人の目に上げる。具体的な閾値・条件は client-staff と詰める。"      --rationale "案件開始時に業務担当者（部長）から明示された前提。会議で決め直さない。"
   python scripts/record.py fact --topic "決定権" --by client-boss      --body "業務ルール・画面＝部下（client-staff）に委譲。予算・納期・スコープ変更＝部長（client-boss）決裁。"

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
