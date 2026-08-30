---
description: 会議を開く。目的を自由文で伝えると、招集ルールから参加者を判断して確認を取り、開会する
argument-hint: <会議の目的を自由文で> [30分 / 45分 など]
allowed-tools: Bash, Read, Agent, SendMessage
---

会議の目的: **$ARGUMENTS**

あなたは**司会**です。以下の手順で会議を開いてください。中身の議論には踏み込まず、進行に徹します。

## 手順1: 招集を判断して確認を取る

目的の文面から、下表のルールで参加者と参加形態を決めます。

| 目的に含まれる性質 | 招集 | 参加形態 |
|---|---|---|
| 方向性・スコープ・成功条件を決めたい | `client-boss` | **opening**（語って退席） |
| 承認をもらいたい（画面・仕様） | `client-boss` | **full** |
| 評価・不満を聞きたい（運用テスト） | `client-boss` | **full**（主役） |
| 業務の詳細を詰めたい | `client-staff` | full |
| 予算・期限・環境の前提を確認したい | `sys-manager` | **bookend** |
| 機能追加・スコープ・優先順位を裁いてほしい | `sys-manager` | **bookend**（または oneonone） |
| （常に） | `sys-staff`, `sys-junior` | full |

複数該当したら重ねます。`client-boss` が opening と full の両方に該当したら **full を採る**。

**招集案を表で提示し、監督（ユーザー）の確認を取ってから次に進んでください。** 「今日は部長抜きで」等の上書きがあれば従います。確認なしに開会しないこと。

## 手順2: 状態を読み込む

```bash
python scripts/views.py
```
を実行してから、以下を読みます。

- `docs/01_session-log.md` — 過去の開催履歴
- `docs/02_decision-log.md` — **特に「仮決めのまま残っている項目」**
- `docs/03_open-issues.md` — 未消化の宿題と、各種枠の残り
- `docs/04_established-facts.md` — **決定権ステータス**
- `docs/21_screen-design.md` — 画面の承認状態（画面が絡む会議のとき）

## 手順3: DBに会議を登録する

```bash
python scripts/record.py meeting-open --purpose "<目的>" \
  --participant "client-staff:full" --participant "sys-staff:full" ...
```

## 手順4: 開会を宣言する

司会として、次を提示します。

1. 第N回であること、本日の目的
2. 参加者と参加形態（誰がいつ退席するか）
3. **前回までの決定のうち、仮決めのまま残っているもの** ← 本決めへの昇格を促す
4. **未消化の宿題**（期限切れがあれば強調）
5. 現在の決定権ステータス
6. **持ち時間と、その中で扱う議題**（30分なら2〜3論点が限度。何を today's scope にするか）
7. 本日のゴールを監督に宣言してもらう

議題を絞るのは司会の仕事です。`sys-staff` の質問リスト全部を1回で消化しようとしないこと。
**優先度の高い順に2〜3論点**を選び、残りは次回に回します。

司会の発言もDBに残します。
```bash
python scripts/log.py --speaker "司会" --topic "開会" --body "..."
```

## 手順5: 進行に入る

- `sys-manager` が bookend なら、まず**冒頭パート**（概要・4機能・制約を伝えて退席）
- `client-boss` が opening なら、次に**業務担当者パート**。ここで `sys-staff` が決定権の確認をするかを見る
- **運用テストの会議**（`client-boss` が full・主役）なら、本体に入る前に**部長に指摘票を提示させる**。
  部長は事前に一通り使って書き出した指摘票を持って出席します。提示された各項目は司会が記録すること
  ```bash
  python scripts/record.py issue --body "<指摘の内容>" --owner sys-staff --due "<期限>"
  python scripts/record.py review --code <画面コード> --stage 業務担当者 --reviewer client-boss --comment "<画面への指摘>"   # 画面への指摘はこちら
  ```
  **仕分けは `sys-staff` の仕事です。** 部長は不具合も要望も新機能要求も区別せず「直してください」で出してきます
- その後**本体**。議題ごとに進め、**議題が一つ終わるたびに監督に続行可否を返して一時停止**する（`/auto` が on なら止まらない）
- **議題を変えるたびに `python scripts/clock.py` で残り時間を確認し、参加者に伝える**
  （「残り10分です」）。5分を切ったら新しい議題を開かず着地に入る

## 手順6: フックの生存確認（その会議で最初のエージェント呼び出しのときだけ）

発言のDB登録は `PostToolUse` フックが自動で行います。**このフックが実際に発火しているかを、最初の1回だけ確認してください。**

1. 最初のエージェント呼び出しの**直前**に件数を数える
   ```bash
   python scripts/query.py --limit 1 >/dev/null; python -c "import sys;sys.path.insert(0,'scripts');from db_init import connect;print(connect().execute('SELECT COUNT(*) FROM utterance').fetchone()[0])"
   ```
2. エージェントを呼ぶ
3. **直後**にもう一度数える

**増えていれば**フックは生きています。以後は何もしなくてよい。

**増えていなければ**フックが効いていません（設定が未読み込み、実行環境の差など）。その場合は**フォールバックに切り替え**、以後この会議では各エージェントの発言を受け取るたびに司会が明示的に記録してください。

```bash
python scripts/log.py --speaker <エージェント名> --topic "<議題>" --body "<発言内容>"
```

フォールバックに切り替えたことを監督に一度伝えてください。**発言の記録が1件でも漏れると、蒸し返しへの防御に穴が開きます。**

原因を追いたいときは `MEETING_HOOK_DEBUG=1` を立てて `python scripts/log.py --hook` に JSON を流すと、握りつぶしている例外が stderr に出ます。
