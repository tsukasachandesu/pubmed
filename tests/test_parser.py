import pytest

from pubmed.search.parser import PubmedXmlParseError, parse_pubmed_xml


def test_parse_pubmed_xml_raises_for_malformed_xml() -> None:
    with pytest.raises(PubmedXmlParseError):
        parse_pubmed_xml("<PubmedArticleSet><PubmedArticle></Pubmed")
