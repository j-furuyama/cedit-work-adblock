"""検証対象サイトの限定CSSだけを抽出し、上流の非表示例外を優先する。"""

import re
from abp import UnsupportedException, valid_host


_SIMPLE = re.compile(
    r'^(?:[a-zA-Z][a-zA-Z0-9_-]*)?(?:[.#][a-zA-Z_][a-zA-Z0-9_-]*)*'
    r'(?:\[(?:id|class|data-[a-zA-Z0-9_-]+)(?:[\^\$\*]?="[a-zA-Z0-9_ -]+")?\])?$')


def supported_selector(selector: str) -> bool:
    """実行コード・宣言・拡張擬似クラスを含まない固定文法を認める。"""
    return (0 < len(selector) <= 256 and any(marker in selector for marker in ('.', '#', '[')) and all(
        part and _SIMPLE.fullmatch(part)
        for part in re.split(r'\s*>\s*|\s+', selector)))


def covers(parent: str, child: str) -> bool:
    """文字列の部分一致ではなくDNSラベル境界で包含を判定する。"""
    return child == parent or child.endswith('.' + parent)


def cosmetic_rule(line: str, reviewed_hosts: list[str]) -> dict | None:
    """適用範囲を検証対象ホストとの積集合に狭め、対象外サイトへ広げない。"""
    if '##' not in line or line.startswith(('!', '[')):
        return None
    domains, selector = line.split('##', 1)
    if not supported_selector(selector):
        return None
    include, exclude = [], []
    for item in domains.split(','):
        host = item.lstrip('~').lower()
        if not valid_host(host):
            return None
        (exclude if item.startswith('~') else include).append(host)
    if not include:
        return None  # 汎用非表示は初期採用しない。
    narrowed = set()
    for domain in include:
        for reviewed in reviewed_hosts:
            if covers(domain, reviewed):
                narrowed.add(reviewed)
            elif covers(reviewed, domain):
                narrowed.add(domain)
    if not narrowed:
        return None
    return {'domains': sorted(narrowed), 'excludedDomains': sorted(set(exclude)),
            'selector': selector}


def hiding_exception_hosts(line: str) -> list[str]:
    """サイト非表示の例外はホスト全体へ広げて許可する。汎用例外は対象外。"""
    if not line.startswith('@@'):
        return []
    body, _, options = line[2:].partition('$')
    flags = options.split(',')
    if not any(flag in ('elemhide', 'specifichide') for flag in flags):
        return []
    domain_flags = [flag[7:] for flag in flags if flag.startswith('domain=')]
    hosts = [item for flag in domain_flags for item in flag.split('|')
             if not item.startswith('~')]
    if not hosts and body.startswith('||'):
        hosts = [re.split(r'[/^*]', body[2:], maxsplit=1)[0].lower()]
    if not hosts or not all(valid_host(host) for host in hosts):
        raise UnsupportedException('サイト非表示例外の範囲を確定できません')
    return hosts
