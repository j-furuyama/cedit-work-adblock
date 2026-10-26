"""固定原本・権利表示が欠けた公開ソースから再生成を成功させない。"""

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from build import build


class BuildTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        tool = Path(__file__).parent
        notices = tool if (tool / 'LICENSE').is_file() else tool.parent
        self.config = json.loads((tool / 'config.json').read_text(encoding='utf-8'))
        (self.root / 'LICENSE').write_bytes((notices / 'LICENSE').read_bytes())
        (self.root / 'NOTICE.md').write_bytes((notices / 'NOTICE.md').read_bytes())
        (self.root / 'inputs').mkdir()
        sources = {}
        for name in ('easylist', 'adguard-japanese'):
            raw = ('||ads.' + name.replace('-', '') + '.example.com^\n').encode()
            (self.root / 'inputs' / (name + '.txt')).write_bytes(raw)
            sources[name] = {'revision': '1' * 40, 'sha256': hashlib.sha256(raw).hexdigest(),
                             'retrievedAt': '2026-10-25T15:00:00Z'}
        (self.root / 'sources.lock.json').write_text(json.dumps({'schemaVersion': 1, 'sources': sources}), encoding='utf-8')

    def test_fixed_source_reproduces_same_bytes_with_corresponding_revisions(self):
        first, report = build(self.root, self.config)
        self.assertEqual((first, report), build(self.root, self.config))
        rules = json.loads(first)
        self.assertTrue(all(source['revision'] == '1' * 40 for source in rules['sources']))
        self.assertEqual(rules['license'], 'GPL-3.0-only')
        self.assertEqual(report['sha256'], hashlib.sha256(first).hexdigest())
        (self.root / 'NOTICE.md').write_text('Updated notice', encoding='utf-8')
        self.assertNotEqual(report['effectiveSha256'], build(self.root, self.config)[1]['effectiveSha256'])

    def test_modified_input_or_license_is_rejected(self):
        for path in ('inputs/easylist.txt', 'LICENSE'):
            target = self.root / path
            before = target.read_bytes()
            target.write_bytes(before + b'changed')
            with self.assertRaises(ValueError):
                build(self.root, self.config)
            target.write_bytes(before)

    def test_unknown_or_missing_revision_is_rejected(self):
        path = self.root / 'sources.lock.json'
        lock = json.loads(path.read_text(encoding='utf-8'))
        lock['sources']['easylist']['revision'] = 'main'
        path.write_text(json.dumps(lock), encoding='utf-8')
        with self.assertRaises(ValueError):
            build(self.root, self.config)


if __name__ == '__main__':
    unittest.main()
