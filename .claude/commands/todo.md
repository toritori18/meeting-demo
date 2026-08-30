---
description: 宿題を起票する、または消化済みにする
argument-hint: <宿題の内容> / <番号> 完了
allowed-tools: Bash, Read
---

**$ARGUMENTS**

## 消化の場合（「#3 完了」のような形）

```bash
python scripts/record.py close-issue --id <ID>
python scripts/views.py --only issues
```

## 起票の場合

**担当と期限を必ず入れてください。** どちらも無い宿題は放置されます。不明なら会議の場で確認します。

```bash
python scripts/record.py issue --body "<内容>" --owner "<担当>" --due "<期限>"
python scripts/views.py --only issues
```

担当の候補: `client-boss`（部長判断が要る） / `client-staff`（業務側が調べる） / `sys-staff`（こちらで検討する） / `sys-manager`（管理者判断）

期限の書き方: 「次回まで」「9/5」など。曖昧なら「次回まで」。

## 宿題にすべきか、仮決めにすべきか

新規案件では未決が大量に出ます。**全部を宿題にしないこと。**

| | どちらにするか |
|---|---|
| **宿題** | 事実を調べれば分かること（実績件数、現物の書式）／部長の判断が要ること |
| **仮決め** | こちらで案を出せば決められること。後で変えられる |

起票したら、現在の未消化件数と、期限切れがあればそれを報告してください。
