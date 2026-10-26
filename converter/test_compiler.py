"""原本を統合しても例外・対象サイト・再現性が保たれることを検証する。"""

import copy
import json
from pathlib import Path
import unittest

from abp import UnsupportedException
from compiler import canonical, compile_sources
from cosmetics import cosmetic_rule, hiding_exception_hosts


class CompilerTests(unittest.TestCase):
    def test_per_site_css_budget_includes_parent_domain_rules(self):
        self.config['reviewedCosmeticHosts'] = ['example.com']
        for split in (False, True):
            lines = [f'{"news.example.com" if split and index >= 100 else "example.com"}##.a{"x" * 240}{index}' for index in range(200)]
            sources = {**self.sources, 'easylist': self.sources['easylist'] + ('\n'.join(lines)).encode()}
            with self.subTest(split=split), self.assertRaisesRegex(ValueError, '32KiB'):
                compile_sources(sources, self.config)

    def setUp(self):
        self.config = json.loads(Path(__file__).with_name('config.json').read_text())
        self.sources = {'easylist': b'! metadata\n||ads.example.com^\n||cdn.example.com/ads/\n',
                        'adguard-japanese': b'||jp.example.com^\n'}

    def test_cross_source_exceptions_are_retained_before_blocking(self):
        self.sources['adguard-japanese'] += b'@@||ads.example.com/banner/*$image\n@@/ads/article$script\n'
        rules, _ = compile_sources(self.sources, self.config)
        self.assertIn('ads.example.com/banner/', rules['allow']['urlLiterals'])
        self.assertIn('/ads/article', rules['allow']['urlLiterals'])
        self.assertIn('ads.example.com', rules['network']['hosts'])
        self.assertEqual(rules['network']['paths'], [{'host': 'cdn.example.com', 'prefixes': ['/ads/']}])

    def test_cosmetic_exception_in_other_source_removes_selector(self):
        self.sources['easylist'] += b'itmedia.co.jp##.advertisement\nitmedia.co.jp##.banner\n'
        self.sources['adguard-japanese'] += b'itmedia.co.jp#@#.banner\n'
        rules, _ = compile_sources(self.sources, self.config)
        self.assertEqual([rule['selector'] for rule in rules['cosmeticRules']], ['.advertisement'])

    def test_site_scope_is_intersection_and_preserves_exclusions(self):
        value = cosmetic_rule('co.jp,~private.itmedia.co.jp##.ad', ['itmedia.co.jp'])
        self.assertEqual(value['domains'], ['itmedia.co.jp'])
        self.assertEqual(value['excludedDomains'], ['private.itmedia.co.jp'])
        self.assertIsNone(cosmetic_rule('itmedia.co.jp.evil.test##.ad', ['itmedia.co.jp']))
        for line in ('##.ad', 'itmedia.co.jp##div:has(.ad)', 'itmedia.co.jp##[onclick]'):
            self.assertIsNone(cosmetic_rule(line, ['itmedia.co.jp']))

    def test_document_exception_does_not_become_resource_only_exception(self):
        self.sources['easylist'] += b'@@||news.example.com/page$document\n'
        rules, _ = compile_sources(self.sources, self.config)
        self.assertEqual(rules['allow']['documentHosts'], ['news.example.com'])
        self.assertEqual(rules['allow']['cosmeticHosts'], ['news.example.com'])

    def test_unsupported_exception_and_missing_source_stop_generation(self):
        self.sources['easylist'] += b'@@*^$script\n'
        with self.assertRaises(UnsupportedException):
            compile_sources(self.sources, self.config)
        with self.assertRaises(ValueError):
            compile_sources({'easylist': b'||ads.example.com^'}, self.config)

    def test_limits_reject_candidate_without_truncation(self):
        config = copy.deepcopy(self.config)
        config['limits']['hosts'] = 1
        with self.assertRaisesRegex(ValueError, 'hosts'):
            compile_sources(self.sources, config)

    def test_header_change_is_no_effective_change_but_rules_are_not_ignored(self):
        rules, report = compile_sources(self.sources, self.config)
        repeated, repeated_report = compile_sources(dict(reversed(list(self.sources.items()))), self.config)
        self.assertEqual(canonical(rules), canonical(repeated))
        self.assertEqual(report, repeated_report)
        self.sources['easylist'] += b'! Last modified: tomorrow\n'
        changed, changed_report = compile_sources(self.sources, self.config)
        self.assertNotEqual(rules['sources'], changed['sources'])
        self.assertEqual(report['effectiveSha256'], changed_report['effectiveSha256'])
        self.sources['easylist'] += b'||another.example.com^\n'
        self.assertNotEqual(report['effectiveSha256'], compile_sources(self.sources, self.config)[1]['effectiveSha256'])

    def test_elemhide_exception_without_safe_scope_is_rejected(self):
        self.assertEqual(hiding_exception_hosts('@@||news.example.com/path$elemhide'), ['news.example.com'])
        with self.assertRaises(UnsupportedException):
            hiding_exception_hosts('@@$elemhide,domain=~excluded.test')


if __name__ == '__main__':
    unittest.main()
