# Spica 広告フィルターの対応ソース

EasyListとAdGuard日本語から生成する、Spica向け限定フィルターの原本・設定・変換器です。
統合フィルターと変換器はGPL v3で配布します。権利表示・変更内容は [NOTICE.md](NOTICE.md)、
全文は [LICENSE](LICENSE) を参照してください。無保証です。同ライセンスに従って変更・再配布できます。

原本を取得した日時・上流コミット・SHA-256は `sources.lock.json` に記録しています。
配布manifestの `sourceCommit` と同じコミットをチェックアウトし、Python 3.13以降の標準ライブラリで再生成します。

```sh
git clone https://github.com/j-furuyama/cedit-work-adblock.git
cd cedit-work-adblock
git checkout <sourceCommit>
python3 -m unittest discover -s converter -p 'test_*.py'
python3 converter/build.py --snapshot . --output out
sha256sum out/rules.json
```

配布manifestの `disabled` が `true` の停止版は、上記の生成コマンドへ `--disabled` を加えてください。
停止版でも同じ原本・権利表示を検証し、ネットワーク・非表示規則が空のデータを生成します。

生成されたハッシュは配布manifestの `rulesSha256` と一致します。
同じコミットからは、現在の上流や取得日時に依存せず同じバイト列を生成できます。
外部Pythonパッケージは使いません。

ネットワークは無条件のホストと単純パスだけを採用し、修飾条件を削って遮断範囲を広げません。
URL例外を先に統合し、必須の固定文字列へ弱めて許可します。未知の例外は生成を停止します。
非表示は検証対象サイトの限定セレクターだけを採用し、例外をソース横断で優先します。
scriptlet・任意正規表現・書換え・汎用CSSは生成しません。

各公開コミットは配布物の対応ソースとして保持します。更新は配信元の自動処理から行います。
不具合はこのリポジトリのIssuesへ、対象のフィルター版・URL・本文や画像への影響を記載してください。
