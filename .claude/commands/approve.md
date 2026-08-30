---
description: 画面の承認または差戻しを記録する
argument-hint: <画面コード> [差戻し]
allowed-tools: Bash, Read
---

対象: **$ARGUMENTS**

## 差戻しの場合

```bash
python scripts/record.py screen --code <コード> --status 差戻し
python scripts/record.py review --code <コード> --stage 業務担当者 --reviewer client-boss \
  --comment "<指摘内容>" --utterance <発言ID>
python scripts/views.py --only screens
```

未解消の指摘を一覧して、次に何を直すかを明示してください。

## 承認の場合

司会として、承認を**記録に残る形で**確認します。

1. 未解消の指摘が残っていないか確認する（`docs/21_screen-design.md`）
   - 残っていれば「この指摘が未解消ですが、承認でよろしいですか」と確認する
2. 承認を記録する
   ```bash
   python scripts/record.py screen --code <コード> --status 承認済
   python scripts/record.py decision --body "画面 <コード> <画面名> を承認" \
     --status 本 --by client-boss --utterance <承認発言のID>
   python scripts/views.py
   python scripts/export_excel.py
   ```

**承認は決定としても記録します。** これが後で「こんなの承認していない」と言われたときの防御になります。`--utterance` を必ず紐づけてください。

## 承認後にできるようになること

- `docs/22_detail-spec.md` に**この画面の詳細仕様を書いてよくなる**（承認ゲート）
- Excelの「画面項目定義」シートにこの画面の項目が出るようになる

承認したら、承認済み画面の数と、まだ承認されていない画面を報告してください。
