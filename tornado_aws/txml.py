"""
XML Deserialization
===================

Parse XML return content and return it as a dict.

"""
import collections
import xml.etree.ElementTree as ET


def loads(content):
    """Return the XML document returned from AWS as a dict

    :param str content: Response content from AWS
    :rtype: dict
    :raises: ValueError

    """
    try:
        return _xml_to_dict(ET.XML(content))
    except ET.ParseError as error:
        raise ValueError(str(error))


def _xml_to_dict(t):
    """Process child nodes, initially taken from
    https://stackoverflow.com/a/10076823/13203

    :param xml.etree.ElementTree.Element t: The XML node to process

    """
    d = {t.tag: {} if t.attrib else None}
    children = list(t)
    if children:
        dd = collections.defaultdict(list)
        for dc in map(_xml_to_dict, children):
            for k, v in dc.items():
                dd[k].append(v)
        d = {t.tag: {k: v[0] if len(v) == 1 else v for k, v in dd.items()}}
    if t.attrib:
        d[t.tag].update(('@' + k, v) for k, v in t.attrib.items())
    if t.text:
        text = t.text.strip()
        if (children or t.attrib) and text:
            d[t.tag]['#text'] = text
        else:
            d[t.tag] = t.text.strip()
    return dict(d)
