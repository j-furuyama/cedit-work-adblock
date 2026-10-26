"""匿名取得した固定スナップショットの原本・ライセンスを検証して再生成する。"""

import argparse
import hashlib
import json
from pathlib import Path
import re
from datetime import datetime

from compiler import canonical, compile_sources, effective_hash


def build(snapshot: Path, config: dict) -> tuple[bytes, dict]:
    """パスや入力を外部URLから補充せず、固定コミットに含まれる素材だけで生成する。"""
    if hashlib.sha256((snapshot / 'LICENSE').read_bytes()).hexdigest() != config['licenseSha256']:
        raise ValueError('ライセンス全文のハッシュが一致しません')
    lock_raw = (snapshot / 'sources.lock.json').read_bytes()
    if len(lock_raw) > 65536:
        raise ValueError('原本参照が容量上限を超えています')
    lock = json.loads(lock_raw)
    if lock.get('schemaVersion') != 1 or set(lock.get('sources', {})) != {'easylist', 'adguard-japanese'}:
        raise ValueError('原本参照の形式が不正です')
    sources = {}
    for name, entry in lock['sources'].items():
        if not isinstance(entry, dict) or not re.fullmatch(r'[0-9a-f]{40}', entry.get('revision', '')):
            raise ValueError('原本の対応コミットが不正です')
        path = snapshot / 'inputs' / (name + '.txt')
        if path.stat().st_size > 10 * 1024 * 1024:
            raise ValueError('原本の容量上限を超えています')
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != entry.get('sha256'):
            raise ValueError('原本ハッシュが一致しません')
        sources[name] = raw
    rules, report = compile_sources(sources, config)
    for source in rules['sources']:
        entry = lock['sources'][source['id']]
        retrieved = entry.get('retrievedAt')
        if not isinstance(retrieved, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z', retrieved):
            raise ValueError('原本の取得日時が不正です')
        datetime.strptime(retrieved, '%Y-%m-%dT%H:%M:%SZ')
        source['revision'], source['retrievedAt'] = entry['revision'], retrieved
    notice = (snapshot / 'NOTICE.md').read_bytes()
    if not notice or len(notice) > 65536:
        raise ValueError('権利表示の容量が不正です')
    rules['noticeSha256'] = hashlib.sha256(notice).hexdigest()
    encoded = canonical(rules)
    if len(encoded) > config['limits']['bytes']:
        raise ValueError('生成物の容量上限を超えています')
    report['counts']['bytes'] = len(encoded)
    report['effectiveSha256'] = effective_hash(rules)
    report['sha256'] = hashlib.sha256(encoded).hexdigest()
    return encoded, report


def main() -> None:
    """固定入力からrulesと検証レポートを出力し、公開や署名は別の責務に委ねる。"""
    parser = argparse.ArgumentParser()
    parser.add_argument('--snapshot', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    config = json.loads(Path(__file__).with_name('config.json').read_text(encoding='utf-8'))
    rules, report = build(args.snapshot, config)
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / 'rules.json').write_bytes(rules)
    (args.output / 'conversion-report.json').write_bytes(canonical(report))
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
