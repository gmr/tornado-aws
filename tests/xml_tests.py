import unittest

from tornado_aws import xml


class TestCase(unittest.TestCase):

    def test_generic_xml(self):
        expectation = {'test': {'foo': 'bar', 'baz': {'qux': 'corgie'}}}
        value = """<?xml version="1.0" encoding="UTF-8"?>
        <test><foo>bar</foo><baz><qux>corgie</qux></baz></test>"""
        self.assertDictEqual(xml.loads(value), expectation)

    def test_generic_xml_with_attributes(self):
        expectation = {'test': {'foo': 'bar',
                                'baz': {'qux': 'corgie', '@val': '1'}}}
        value = """<?xml version="1.0" encoding="UTF-8"?>
        <test><foo>bar</foo><baz val="1"><qux>corgie</qux></baz></test>"""
        self.assertDictEqual(xml.loads(value), expectation)

    def test_generic_xml_with_text_and_children(self):
        expectation = {'test': {'foo': 'bar',
                                'baz': {'qux': 'corgie',
                                        '@val': '1',
                                        '#text': 'gorge'}}}
        value = """<?xml version="1.0" encoding="UTF-8"?>
        <test><foo>bar</foo><baz val="1">gorge<qux>corgie</qux></baz></test>"""
        self.assertDictEqual(xml.loads(value), expectation)

    def test_invalid_xml(self):
        with self.assertRaises(ValueError):
            xml.loads('foo')

