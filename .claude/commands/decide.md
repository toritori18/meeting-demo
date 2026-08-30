---
description: 決定を記録する。仮決めか本決めかを区別し、根拠となった発言に紐づける
argument-hint: <決定内容> [--本] [--仮決めID を昇格させる場合は番号]
allowed-tools: Bash, Read
---

決定: **$ARGUMENTS**

## 仮決めの昇格の場合

引数が番号だけ、または「#3を本決めに」のような形なら昇格です。

```bash
python scripts/record.py promote --id <ID>
python scripts/views.py --only decisions
```

## 新規の決定の場合

司会として「今のは決定ですね」と確認してから記録します。

1. **根拠となった発言のIDを特定する。** 直近のやり取りから、誰のどの発言が根拠かを見つける
   ```bash
   python scripts/query.py <キーワード> --limit 5
   ```
2. 記録する
   ```bash
   python scripts/record.py decision --body "<決定内容>" \
     --status 仮 --by <決めた人> --rationale "<根拠>" --utterance <発言ID>
   python scripts/views.py --only decisions
   ```

**`--utterance` は必ず付けてください。** 後で業務担当者が「そんなことは言っていない」と蒸し返したとき、これがあれば原文を引けます。これが無い決定は守れません。

## 仮と本の使い分け

| | いつ |
|---|---|
| **仮** | 業務側が確信を持っていない、後で変わりうる。新規案件では**こちらが基本** |
| **本** | 業務担当者本人が明言した、または委譲済みの部下が確定させた |

未決を全部宿題にすると宿題だけが増えて何も決まりません。**仮決めして前に進むこと。** ただし仮決めは `/meeting-open` のたびにリマインドされ、放置すると運用テストで突かれます。

記録したら、決定内容と仮/本、根拠発言IDを1行で報告してください。
