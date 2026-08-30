---
description: 会議の途中で管理者に緊急相談する（1会議2回まで）
argument-hint: <相談内容>
allowed-tools: Bash, Read, Agent, SendMessage
---

相談内容: **$ARGUMENTS**

## 手順1: 枠を確認する

```bash
python scripts/record.py state --key escalate_quota
```

**0 なら相談できません。** その場合は「枠を使い切っているので、会議の最後の管理者パートで諮りましょう」と返し、保留事項として記録してください。

```bash
python scripts/record.py issue --body "【管理者に諮る】<内容>" --owner sys-manager --due "本会議の最後"
```

## 手順2: 本当に緊急か確認する

機能追加の判断は**会議の最後に一括で諮る**のが基本です。枠を使うのは、いま判断が出ないと会議が止まる場合だけ。

監督に「これは最後まで待てませんか」と一度確認してください。待てるなら手順1の保留に回します。

## 手順3: 相談する

`sys-manager` を呼び、`sys-staff` に相談させます。管理者は短く判断だけ返します。

管理者は理由なく却下せず、必ず「代わりに何を削るか」「運用で回避できないか」を問い返します。

## 手順4: 枠を減らして記録する

```bash
python scripts/record.py state --key escalate_quota --value <残り>
python scripts/log.py --speaker "sys-manager" --topic "緊急相談" --body "<判断内容>"
python scripts/record.py feature --code F-xx --judgment <採用|次期|対象外|保留>
python scripts/views.py
```

判断結果と、残りの枠数を報告してください。
