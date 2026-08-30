---
description: 議題ごとの一時停止を解除する（連続実行）。もう一度実行すると停止モードに戻る
allowed-tools: Bash, Read
---

現在の設定を確認し、切り替えます。

```bash
python scripts/record.py state --key auto
```

- `off` なら `on` にする（連続実行。議題ごとに止まらない）
- `on` なら `off` にする（既定。議題ごとに監督へ続行可否を返す）

```bash
python scripts/record.py state --key auto --value on
```

切り替えたら、現在どちらのモードかを明示してください。

**注意**: `on` にすると会議が最後まで自走するため、エージェントの呼び出し回数が増えます。1会議あたり35〜40回程度を見込んでください。介入したくなったら平文で割り込めば止まります。
