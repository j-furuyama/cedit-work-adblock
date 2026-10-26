"""条件と例外が失われて誤遮断を起こすケースを検証する。"""

import unittest
from abp import (NetworkRule, UnsupportedException, document_exception_hosts,
                 exception_pattern, network_rule, valid_host)


class AbpTests(unittest.TestCase):
    def test_only_equivalent_network_conditions_are_adopted(self):
        self.assertEqual(network_rule("||ads.example.com^"), NetworkRule("ads.example.com"))
        self.assertEqual(network_rule("||cdn.example.com/ads/"), NetworkRule("cdn.example.com", "/ads/"))
        for line in ("||cdn.example.com^$third-party", "||cdn.example.com^$domain=news.test",
                     "||cdn.example.com^$image", "||*.example.com^", "/ads/", "||example.com^$removeparam=x"):
            self.assertIsNone(network_rule(line), line)

    def test_dns_boundaries_are_not_arbitrary_url_patterns(self):
        for host in ("a..test", "-ad.test", "ad-.test", "127.0.0.1", "ad.test:80", "ad.test/path"):
            self.assertFalse(valid_host(host), host)
        self.assertTrue(valid_host("ads.example.com"))

    def test_network_exception_is_tokenized_without_executable_regex(self):
        value = exception_pattern("@@||ads.example.com/banner/*^$image,domain=news.test")
        self.assertEqual(value["anchor"], "host")
        self.assertEqual(value["tokens"], [{"kind":"literal", "value":"ads.example.com/banner/"},
                                          {"kind":"wildcard"}, {"kind":"separator"}])

    def test_unrepresentable_exception_stops_generation(self):
        for line in ("@@/[ab]+/", "@@/ad/", "@@/ad$/", "@@/ad/$script", "@@$document,domain=news.test", "@@abc|def", "@@||news.test^$genericblock", "@@||広告.test^"):
            with self.assertRaises(UnsupportedException, msg=line):
                exception_pattern(line)

    def test_generic_hiding_is_not_accidentally_network_allow_all(self):
        self.assertIsNone(exception_pattern("@@$generichide,domain=news.test"))
        self.assertIsNotNone(exception_pattern("@@/ad/banner/*$image,domain=news.test"))

    def test_wildcard_host_exception_is_conservatively_broadened(self):
        value = exception_pattern("@@||www.google.*/search?$xmlhttprequest")
        self.assertEqual(value["anchor"], "any")
        self.assertEqual(value["tokens"][0], {"kind":"literal", "value":"www.google."})

    def test_document_exception_keeps_entire_page_exemption(self):
        self.assertEqual(document_exception_hosts("@@||news.test/path$document"), ["news.test"])
        self.assertEqual(document_exception_hosts("@@||ads.test/banner$script"), [])


if __name__ == "__main__":
    unittest.main()
