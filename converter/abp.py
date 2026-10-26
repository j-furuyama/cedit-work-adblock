"""上流の限定文法を解析し、条件の欠落による遮断範囲の拡大を防ぐ。"""

from dataclasses import dataclass
import re


class UnsupportedException(ValueError):
    """例外を安全に表現できない場合は、公開側が処理を停止する。"""


_HOST = re.compile(r"[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?", re.ASCII)
_PATH = re.compile(r"/[a-zA-Z0-9_./%-]*", re.ASCII)


def valid_host(host: str) -> bool:
    """IP・ワイルドカード・空ラベルを含まない公開DNS名だけを採用する。"""
    return (len(host) <= 253 and bool(_HOST.fullmatch(host))
            and "." in host and ".." not in host
            and not all(c.isdigit() or c == "." for c in host)
            and all(0 < len(label) <= 63 and not label.startswith("-")
                    and not label.endswith("-") for label in host.split(".")))


@dataclass(frozen=True, order=True)
class NetworkRule:
    """URLホストと、存在する場合だけ単純パス前方一致を表す。"""

    host: str
    path_prefix: str = ""


def network_rule(line: str) -> NetworkRule | None:
    """追加条件・書換え・任意正規表現を落として採用することはしない。"""
    if not line.startswith("||") or any(c in line[2:] for c in ("$", "*", "?", "|")):
        return None
    value = line[2:]
    if value.endswith("^") and "/" not in value:
        host = value[:-1].lower()
        return NetworkRule(host) if valid_host(host) else None
    if "/" in value and "^" not in value:
        host, path = value.split("/", 1)
        host = host.lower()
        path = "/" + path
        if valid_host(host) and len(path) <= 512 and _PATH.fullmatch(path):
            return NetworkRule(host, path)
    return None


def exception_pattern(line: str) -> dict | None:
    """ABP例外を文字列・ワイルドカード・区切りの固定トークンへ変換する。

    リソース種別や適用サイト条件は遮断へ転用せず、より広く許可する方向へ
    保守的に扱う。汎用非表示だけの例外は、汎用CSSを採用しないv1では不要。
    """
    if not line.startswith("@@"):
        return None
    if not line.isascii() or (line.startswith('@@/') and re.search(r'/(?:\$.*)?$', line[3:])):
        raise UnsupportedException("非ASCIIまたは正規表現の例外")
    body, _, options = line[2:].partition("$")
    flags = options.split(",") if options else []
    supported = {'generichide', 'specifichide', 'elemhide', 'document', 'script',
                 'image', 'stylesheet', 'object', 'xmlhttprequest', 'subdocument',
                 'media', 'font', 'popup', 'other', 'ping', 'websocket', 'webrtc',
                 'third-party', 'match-case', 'redirect', 'csp', 'important', 'badfilter'}
    for flag in flags:
        name, separator, _ = flag.partition('=')
        if (name.lstrip('~') not in supported and name != 'domain' or
                separator and name not in ('domain', 'redirect', 'csp')):
            raise UnsupportedException("未対応の例外修飾子")
    if flags and all(flag in ("generichide", "specifichide", "elemhide")
                     or flag.startswith("domain=") for flag in flags):
        return None
    if not body:
        raise UnsupportedException("URL条件のないネットワーク例外")
    if len(body) > 2048 or any(ord(c) < 32 for c in body):
        raise UnsupportedException("例外の長さ・制御文字")
    anchor = "any"
    if body.startswith("||"):
        anchor, body = "host", body[2:]
        host = re.split(r"[/^*]", body, maxsplit=1)[0].lower()
        if not valid_host(host):
            # 例外側だけは境界を弱めて広く許可し、遮断を強めない。
            anchor = "any"
    elif body.startswith("|"):
        anchor, body = "start", body[1:]
    end = body.endswith("|")
    if end:
        body = body[:-1]
    if "|" in body:
        raise UnsupportedException("途中のURLアンカー")
    tokens = []
    for value in re.split(r"([*^])", body):
        if value == "*":
            tokens.append({"kind": "wildcard"})
        elif value == "^":
            tokens.append({"kind": "separator"})
        elif value:
            tokens.append({"kind": "literal", "value": value})
    return {"anchor": anchor, "end": end, "tokens": tokens}


def document_exception_hosts(line: str) -> list[str]:
    """ページ全体の除外を、上流に由来するホスト単位の広い許可へ変換する。"""
    if not line.startswith("@@"):
        return []
    body, _, options = line[2:].partition("$")
    if "document" not in options.split(","):
        return []
    if not body.startswith("||"):
        raise UnsupportedException("ホストを確定できないページ例外")
    host = re.split(r"[/^]", body[2:], maxsplit=1)[0].lower()
    if not valid_host(host):
        raise UnsupportedException("不正なページ例外ホスト")
    return [host]
