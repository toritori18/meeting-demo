---
description: 画面一覧・機能一覧のExcelをDBから再生成して開く
allowed-tools: Bash, Read
---

```bash
python scripts/export_excel.py --open
```

引数に `--no-open` 相当の指示があれば `--open` を外してください。

## 生成されるもの

`docs/画面一覧・機能一覧.xlsx`（4シート）

| シート | 中身 |
|---|---|
| **画面一覧** | 画面ID・画面名・機能区分・概要・主な項目・設計者・承認状態・承認会議・未解消指摘・備考 |
| **機能一覧** | 機能ID・機能名・機能区分・対応画面・概要・優先度・判定・判定会議・備考 |
| **画面項目定義** | **承認済みの画面のみ**（承認ゲート）。項目名・型・桁・必須・初期値・バリデーション |
| **改訂履歴** | 版・日付・会議・変更内容 |

承認状態と判定は色分けされます（承認済/採用は緑、差戻し/保留は赤、次期は黄）。

## 中身を増やすには

Excelは**DBから生成されるだけ**です。中身を増やすには `sys-staff` / `sys-junior` がDBに登録します。

```bash
python scripts/record.py screen --code SC-01 --name "..." --area マッチング --designer sys-staff
python scripts/record.py screen-item --code SC-01 --item "受付番号" --datatype 文字 --length 10
python scripts/record.py feature --code F-01 --name "..." --area マッチング --screens SC-01
```

エージェントに xlsx バイナリは書けないため、**中身はシステム担当者が決め、体裁はスクリプトが作る**という分担です。

生成したら、画面数・機能数・承認済み画面数を報告してください。承認会議ではこのExcelを見せながら進めます。
