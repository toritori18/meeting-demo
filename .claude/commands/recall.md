---
description: 過去の発言・決定・宿題・確定事実を横断検索する。「言った言わない」を原文で制するための道具
argument-hint: <キーワード> [--speaker client-boss] [--decision N] [--utterance N]
allowed-tools: Bash, Read
---

検索: **$ARGUMENTS**

```bash
python scripts/query.py $ARGUMENTS
```

を実行して結果を提示してください。

## 使い分け

| やりたいこと | コマンド |
|---|---|
| ある論点について過去に誰が何を言ったか | `python scripts/query.py 監査ログ` |
| 特定の人の発言だけ | `python scripts/query.py 保存 --speaker client-boss` |
| **決定の根拠となった発言を辿る** | `python scripts/query.py --decision 3` |
| ある発言の前後の文脈を見る | `python scripts/query.py --utterance 42` |
| 発言だけに絞る | `--utterances-only` |

## 日本語検索の注意

部分一致なので、**発言中の表現と検索語が一致しないと当たりません**。「件数」で検索しても発言が「何件くらい」なら発言本文にはヒットしません。

そのため決定・宿題・**確定事実**も併せて検索しています。確定事実には整理された話題語が入っているので、この取りこぼしの橋渡しになります。空振りしたら別の語で試してください。

## 蒸し返しへの対抗

業務担当者が過去の決定や承認を否定してきたら、これで原文を引いて提示します。

1. `python scripts/query.py --decision <番号>` で決定と根拠発言を出す
2. 「第◯回のこのご発言でこう仰っています」と原文を示す
3. 記録を示されれば部長は引き下がります（渋々でも）

**記録が無い、または根拠発言が紐づいていない決定は守れません。** そういう決定が見つかったら、その場で発言IDを紐づけ直してください。
