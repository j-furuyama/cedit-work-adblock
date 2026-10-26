"""原本横断で例外を先に集約し、再現可能な限定フィルター候補を生成する。"""

from collections import Counter, defaultdict
import hashlib
import json

from abp import UnsupportedException, document_exception_hosts, exception_pattern, network_rule
from cosmetics import cosmetic_rule, hiding_exception_hosts


PROFILE = 'android-url-v1'
SOURCE_METADATA = {
    'easylist': {'title': 'EasyList', 'authors': 'The EasyList authors',
                 'url': 'https://easylist.to/easylist/easylist.txt',
                 'licenseUrl': 'https://easylist.to/pages/licence.html'},
    'adguard-japanese': {'title': 'AdGuard Japanese filter', 'authors': 'AdGuard Software Ltd. and contributors',
                        'url': 'https://github.com/AdguardTeam/FiltersRegistry/tree/master/filters/filter_7_Japanese',
                        'licenseUrl': 'https://github.com/AdguardTeam/AdguardFilters/blob/master/LICENSE'},
}


def canonical(value: object) -> bytes:
    """同じ入力はOS・日時に依存せず、同じUTF-8バイト列にする。"""
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(',', ':'), allow_nan=False).encode('utf-8')


def compile_sources(sources: dict[str, bytes], config: dict) -> tuple[dict, dict]:
    """上限超過や解釈不能な例外を切り捨てず、公開候補の生成を失敗させる。"""
    if set(sources) != {'easylist', 'adguard-japanese'}:
        raise ValueError('両方の上流原本が必要です')
    lines, report = {}, {}
    for name, raw in sorted(sources.items()):
        if not raw or len(raw) > 10 * 1024 * 1024:
            raise ValueError('原本の容量が不正です')
        lines[name] = [line.strip() for line in raw.decode('utf-8-sig').splitlines()]
        report[name] = Counter()

    allow_literals, page_hosts, hiding_hosts, excluded_selectors = set(), set(), set(), set()
    for source_lines in lines.values():
        for line in source_lines:
            if line.startswith('@@'):
                pattern = exception_pattern(line)
                if pattern:
                    literals = [token['value'] for token in pattern['tokens']
                                if token['kind'] == 'literal']
                    if not literals:
                        raise UnsupportedException('固定文字列を持たない例外')
                    # 元の例外が成立するURLは必ずこの文字列を含む。条件を弱める方向は許可側だけ。
                    allow_literals.add(max(literals, key=lambda value: (len(value), value)).lower())
                page_hosts.update(document_exception_hosts(line))
                hiding_hosts.update(hiding_exception_hosts(line))
            elif '#@#' in line and not line.startswith(('!', '[')):
                # 別サイトの同名セレクターも除外し、非表示例外を取り落とさない。
                excluded_selectors.add(line.split('#@#', 1)[1])

    network, cosmetics = set(), {}
    for name, source_lines in lines.items():
        for line in source_lines:
            if not line or line.startswith(('!', '[')):
                kind = 'metadata'
            elif line.startswith('@@') or '#@#' in line:
                kind = 'exception'
            elif (rule := network_rule(line)) is not None:
                network.add(rule)
                kind = 'networkAdopted'
            elif (rule := cosmetic_rule(line, config['reviewedCosmeticHosts'])) is not None:
                if rule['selector'] in excluded_selectors:
                    kind = 'cosmeticExcludedByException'
                else:
                    cosmetics[canonical(rule)] = rule
                    kind = 'cosmeticAdopted'
            elif any(marker in line for marker in ('##', '#$#', '#?#', '#%#')):
                kind = 'cosmeticUnsupportedOrUnreviewed'
            else:
                kind = 'networkUnsupported'
            report[name][kind] += 1

    hosts = {rule.host for rule in network if not rule.path_prefix}
    paths = defaultdict(set)
    for rule in sorted(network):
        if rule.path_prefix and not any(
                '.'.join(rule.host.split('.')[offset:]) in hosts
                for offset in range(len(rule.host.split('.')))):
            paths[rule.host].add(rule.path_prefix)
    result = {
        'schemaVersion': 1, 'engineProfile': PROFILE, 'disabled': False,
        'network': {'hosts': sorted(hosts), 'paths': [
            {'host': host, 'prefixes': sorted(prefixes)} for host, prefixes in sorted(paths.items())]},
        'allow': {'urlLiterals': sorted(allow_literals), 'documentHosts': sorted(page_hosts),
                  'cosmeticHosts': sorted(hiding_hosts | page_hosts)},
        'cosmeticRules': [cosmetics[key] for key in sorted(cosmetics)],
        'license': 'GPL-3.0-only', 'licenseSha256': config['licenseSha256'],
        'sources': [{'id': name, **SOURCE_METADATA[name], 'sha256': hashlib.sha256(raw).hexdigest()}
                    for name, raw in sorted(sources.items())],
    }
    limits = config['limits']
    cosmetic_bytes = Counter()
    for rule in result['cosmeticRules']:
        for host in rule['domains']:
            cosmetic_bytes[host] += len(rule['selector']) + 1
    largest_site = 0
    for host in cosmetic_bytes:
        parts = host.split('.')
        largest_site = max(largest_site, sum(cosmetic_bytes['.'.join(parts[index:])] for index in range(len(parts))))
    if largest_site > 32768:
        raise ValueError('サイト別セレクターが32KiBを超えています')
    counts = {'hosts': len(hosts), 'pathHosts': len(paths),
              'pathPrefixes': sum(map(len, paths.values())), 'cosmeticRules': len(cosmetics),
              'allowLiterals': len(allow_literals), 'bytes': len(canonical(result))}
    for key, value in counts.items():
        if value > limits[key]:
            raise ValueError('フィルター候補が上限を超えています: ' + key)
    if not hosts or not all(report[name]['networkAdopted'] for name in sources):
        raise ValueError('上流の片側またはネットワーク規則が空です')
    # 原本ヘッダーの取得日時だけが変わった候補は公開しない。採用規則・ライセンスは含める。
    return result, {'sources': {name: dict(sorted(counts.items())) for name, counts in report.items()},
                    'counts': counts, 'effectiveSha256': effective_hash(result)}


def effective_hash(rules: dict) -> str:
    """固定原本の参照だけを比較対象から外し、出典・ライセンスの変更は検出する。"""
    effective = {**rules, 'sources': [
        {key: value for key, value in source.items() if key not in ('sha256', 'revision', 'retrievedAt')}
        for source in rules['sources']]}
    return hashlib.sha256(canonical(effective)).hexdigest()
