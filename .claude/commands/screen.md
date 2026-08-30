---
description: 画面案を提示する。テキストワイヤーフレームが既定、--mockup でHTMLモックアップをArtifact公開
argument-hint: <画面コードまたは画面名> [--mockup]
allowed-tools: Bash, Read, Write, Edit, Agent, SendMessage, Artifact, Skill
---

提示する画面: **$ARGUMENTS**

## 手順1: 承認ゲートを確認する

```bash
python scripts/views.py --only screens
```
で `docs/21_screen-design.md` を読み、対象画面の状態を確認します。

**`sys-junior` が設計した画面が `社内レビュー中` のまま業務担当者に出されようとしていたら、止めてください。**
「社内レビューがまだです。`sys-staff` のレビューを先に通しましょう」と司会として指摘し、社内レビューを実施します。新人の画面は業務的な穴（使われない検索条件、見落とした状態）を含むため、そのまま出すと差戻しの山になります。

社内レビューを行う場合:
1. `sys-staff` に画面を見せて指摘させる
2. 指摘を記録: `python scripts/record.py review --code <コード> --stage 社内 --reviewer sys-staff --comment "..."`
3. `sys-junior` が直す → 状態を `社内OK` に更新

## 手順2: 提示する

### 既定（テキストワイヤーフレーム）

`docs/21_screen-design.md` のワイヤーフレームをそのまま提示します。軽く、何度でも直せます。

### `--mockup` が付いている場合

HTMLモックアップを作って Artifact として公開します。**承認を取る回だけ**使ってください（実物を見せないと細部のこだわりが引き出せないため）。

1. `artifact-design` スキルを読む
2. `screen-design` スキルの慣行（ボタン位置、書式、キーボード操作の表示）に従う
3. WinForms のデスクトップアプリらしい見た目にする（Webページ風にしない）
4. **具体的なダミーデータを入れる**。マイナス金額や桁の大きい値を混ぜると書式の議論が引き出せる
5. Artifact として公開し、URLを提示する

## 手順3: 業務担当者のレビュー

`client-boss` に見せます。部長は具体物を見ると細かくなります。指摘が出たら記録します。

```bash
python scripts/record.py review --code <コード> --stage 業務担当者 --reviewer client-boss \
  --comment "<指摘>" --utterance <発言ID>
python scripts/record.py screen --code <コード> --status 差戻し
python scripts/views.py --only screens
```

**中核画面は1回で通らない前提です。** 一発承認が続くようなら業務担当者役が機能していません。

承認されたら `/approve <画面コード>` を使ってください。
