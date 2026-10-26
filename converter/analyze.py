"""固定原本を解析し、採用候補・例外・原本ハッシュを公開前の検証材料へまとめる。"""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

from abp import (UnsupportedException, document_exception_hosts,
                 exception_pattern, network_rule)


def analyze(path: Path) -> dict:
    """原本を変更せず、条件を落とさず採用できる候補を数える。"""
    raw = path.read_bytes()
    if len(raw) > 10 * 1024 * 1024:
        raise ValueError("原本の容量上限を超えています")
    lines = raw.decode("utf-8-sig").splitlines()
    reasons = Counter()
    rules = set()
    exceptions = []
    page_hosts = set()
    errors = []
    for number, line in enumerate(lines, 1):
        line = line.strip()
        if not line or line.startswith(("!", "[Adblock")):
            reasons["metadata"] += 1
        elif line.startswith("@@"):
            try:
                value = exception_pattern(line)
                if value:
                    exceptions.append(value)
                page_hosts.update(document_exception_hosts(line))
                reasons["exception"] += 1
            except UnsupportedException as error:
                # 原文やURLを実行ログへ展開せず、原本の固定行と分類だけを記録します。
                errors.append({"line": number, "reason": str(error)})
        elif (rule := network_rule(line)) is not None:
            rules.add(rule)
            reasons["network_candidate"] += 1
        elif any(marker in line for marker in ("##", "#@#", "#$#", "#?#")):
            reasons["cosmetic_requires_validation"] += 1
        else:
            reasons["unsupported_network_condition"] += 1
    return {
        "schemaVersion": 1,
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "lines": len(lines),
        "uniqueNetworkCandidates": len(rules),
        "pathCandidates": sum(bool(rule.path_prefix) for rule in rules),
        "exceptionPatterns": len(exceptions),
        "upstreamDocumentExceptions": sorted(page_hosts),
        "classifications": dict(sorted(reasons.items())),
        "unsupportedExceptions": errors,
    }


def main() -> None:
    """本番公開とは独立した調査CLI。例外を表現できなければ失敗終了する。"""
    parser = argparse.ArgumentParser()
    parser.add_argument("sources", type=Path, nargs="+")
    args = parser.parse_args()
    reports = {path.name: analyze(path) for path in args.sources}
    print(json.dumps(reports, ensure_ascii=False, indent=2))
    if any(report["unsupportedExceptions"] for report in reports.values()):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
