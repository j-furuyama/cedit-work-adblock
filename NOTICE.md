# フィルターの権利表示と変更内容

EasyList: The EasyList authors — <https://easylist.to/>

AdGuard Japanese filter: AdGuard Software Ltd. and contributors — <https://github.com/AdguardTeam/AdguardFilters>

EasyListは上流で提示されたGPL v3以降の選択肢からv3を選択する。
統合フィルター・Spica補正・この変換器はGPL v3（`GPL-3.0-only`）で配布する。
ライセンス全文は同梱の `LICENSE` を参照。無保証であり、同ライセンスに従って再配布・変更できる。
上流原本の権利表示は `inputs/` の原本内にも保持する。

2026-10-26: Spica向けの限定文法への変換を実装。リソース種別・第三者条件等を要する遮断規則、
任意正規表現・scriptlet・書換え・汎用CSSは採用しない。ネットワーク例外を先に評価し、
必須の固定文字列による広い許可へ変換する。ページ全体の例外とサイト非表示例外を別に保持する。
非表示は検証対象サイトに限定し、ソース横断の例外セレクターを保守的に除外する。

配布物に対応する原本・設定・変換器の固定コミットは配布manifestの `sourceCommit` に記録する。
そのコミットを取得して `converter/build.py` を実行すると同じ `rules.json` を再生成できる。
取得日時だけの変更で同じ規則を再公開せず、対応する過去の公開コミットを維持する。
