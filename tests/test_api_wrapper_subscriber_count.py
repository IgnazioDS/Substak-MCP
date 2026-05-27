from unittest.mock import Mock

from src.utils.api_wrapper import APIWrapper


def test_extract_subscriber_count_from_embedded_json():
    client = Mock()
    client.publication_url = "https://test.substack.com"
    wrapper = APIWrapper(client)

    html = """
    <html>
      <body>
        <script>
          window._data = {"subscriberCount": 4321};
        </script>
      </body>
    </html>
    """

    assert wrapper._extract_subscriber_count_from_html(html) == 4321


def test_extract_subscriber_count_from_visible_text():
    client = Mock()
    client.publication_url = "https://test.substack.com"
    wrapper = APIWrapper(client)

    html = """
    <html>
      <body>
        <div>Join 12.5k subscribers reading weekly iOS essays.</div>
      </body>
    </html>
    """

    assert wrapper._extract_subscriber_count_from_html(html) == 12500


def test_get_publication_subscriber_stats_falls_back_to_publication_page():
    client = Mock()
    client.publication_url = "https://test.substack.com"
    client.get_publication_subscriber_count.side_effect = KeyError("subscriberCount")
    client.get_sections.return_value = []
    client._session.get.return_value = Mock(
        status_code=200,
        text='<script>{"subscriberCount": 9876}</script>',
    )

    wrapper = APIWrapper(client)

    result = wrapper.get_publication_subscriber_stats()

    assert result["available"] is True
    assert result["total_subscribers"] == 9876
    assert result["source"] == "publication_page"
    assert result["checked_sources"] == ["python_substack", "publication_page"]


def test_get_publication_subscriber_stats_unavailable_has_reason():
    client = Mock()
    client.publication_url = "https://test.substack.com"
    client.get_publication_subscriber_count.side_effect = KeyError("subscriberCount")
    client.get_sections.return_value = []
    client._session.get.return_value = Mock(status_code=200, text="<html></html>")

    wrapper = APIWrapper(client)

    result = wrapper.get_publication_subscriber_stats()

    assert result["available"] is False
    assert result["total_subscribers"] is None
    assert result["checked_sources"] == [
        "python_substack",
        "publication_page",
        "sections",
    ]
    assert "not exposed" in result["reason"]
