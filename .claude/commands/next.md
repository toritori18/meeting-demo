---
description: 次の議題へ進む
allowed-tools: Bash, Read, Agent, SendMessage
---

司会として次の議題に移ります。

0. **まず残り時間を確認する**
   ```bash
   python scripts/clock.py
   ```
   **残り5分以下なら新しい議題を開かないこと。** 着地に入り、決まったことを記録して
   残りを宿題にし、`/meeting-close` へ向かいます。時間切れで全部決まらないのは正常です。

1. 直前の議題で**決まったことがあれば記録する**
   ```bash
   python scripts/record.py decision --body "..." --status 仮 --by ... --utterance <発言ID>
   ```
2. 決まらなかった論点は宿題にするか、**仮決めにして進む**かを監督に確認する
   - 新規案件では未決が大量に出る。全部宿題にすると宿題だけが増えて何も決まらない
3. 司会として議題の切り替えを宣言し、記録する
   ```bash
   python scripts/log.py --speaker "司会" --topic "<新しい議題>" --body "では次に〜について伺います"
   ```
4. `sys-staff` に次の議題を振る

引数で議題が指定されていればそれに移ります: **$ARGUMENTS**
指定がなければ、`sys-staff` の質問リスト（`docs/00_question-list.md`）の順に従ってください。

議題を切り替えたら、参加者に残り時間を伝えてください（「残り12分です」）。

議題が一つ終わるたびに監督に続行可否を返して一時停止します（`/auto` が on なら止まりません）。
