# ABOUTME: Unit tests for APIWrapper response normalization and endpoint helpers.
# ABOUTME: Exercises non-ideal response shapes from python-substack and private endpoints.

from unittest.mock import Mock

import pytest

from src.utils.api_wrapper import APIWrapper, SubstackAPIError


class FakeResponse:
    """Small response-like object for wrapper tests."""

    def __init__(self, status_code=200, json_data=None, text=""):
        self.status_code = status_code
        self._json_data = json_data
        self.text = text

    def json(self):
        return self._json_data


def build_client() -> Mock:
    client = Mock()
    client.publication_url = "https://test.substack.com"
    client._session = Mock()
    return client


def test_handle_response_rejects_error_list_payload():
    wrapper = APIWrapper(build_client())

    with pytest.raises(SubstackAPIError, match="permission denied"):
        wrapper._handle_response(
            {"errors": ["permission denied", "secondary detail"]},
            "get_post_management[scheduled]",
        )


def test_handle_response_rejects_message_with_error_status():
    wrapper = APIWrapper(build_client())

    with pytest.raises(SubstackAPIError, match="bad gateway"):
        wrapper._handle_response(
            {"message": "bad gateway", "status": 502},
            "publish_draft",
        )


def test_handle_response_rejects_response_like_http_errors():
    wrapper = APIWrapper(build_client())

    with pytest.raises(SubstackAPIError, match="permission denied"):
        wrapper._handle_response(
            FakeResponse(
                status_code=403,
                json_data={"errors": ["permission denied"]},
                text="permission denied",
            ),
            "get_post_management[published]",
        )


def test_get_post_management_surfaces_non_2xx_json_errors():
    client = build_client()
    client._session.get.return_value = FakeResponse(
        status_code=403,
        json_data={"errors": ["permission denied"]},
        text="permission denied",
    )
    wrapper = APIWrapper(client)

    with pytest.raises(SubstackAPIError, match="permission denied"):
        wrapper.get_post_management("scheduled")


def test_get_drafts_accepts_generators_of_dicts():
    client = build_client()
    client.get_drafts.return_value = (
        {"id": "draft-1", "draft_title": "One"},
        {"id": "draft-2", "draft_title": "Two"},
    )
    wrapper = APIWrapper(client)

    drafts = wrapper.get_drafts(limit=2)

    assert [draft["id"] for draft in drafts] == ["draft-1", "draft-2"]


def test_get_sections_accepts_generators_of_dicts():
    client = build_client()
    client.get_sections.return_value = (
        {"id": 1, "name": "General"},
        {"id": 2, "name": "Paid"},
    )
    wrapper = APIWrapper(client)

    sections = wrapper.get_sections()

    assert [section["name"] for section in sections] == ["General", "Paid"]


def test_get_image_rejects_none_response():
    client = build_client()
    client.get_image.return_value = None
    wrapper = APIWrapper(client)

    with pytest.raises(SubstackAPIError, match="returned None"):
        wrapper.get_image("/tmp/example.png")


def test_get_user_id_coerces_to_string():
    client = build_client()
    client.get_user_id.return_value = 12345
    wrapper = APIWrapper(client)

    assert wrapper.get_user_id() == "12345"


def test_get_user_id_requires_method():
    client = build_client()
    del client.get_user_id
    wrapper = APIWrapper(client)

    with pytest.raises(SubstackAPIError, match="method not available"):
        wrapper.get_user_id()


def test_get_draft_surfaces_key_errors():
    client = build_client()
    client.get_draft.side_effect = KeyError("draft_body")
    wrapper = APIWrapper(client)

    with pytest.raises(SubstackAPIError, match="Missing required field"):
        wrapper.get_draft("draft-1")


def test_get_draft_rejects_non_dict_payload():
    client = build_client()
    client.get_draft.return_value = ["not", "a", "dict"]
    wrapper = APIWrapper(client)

    with pytest.raises(SubstackAPIError, match="expected dict"):
        wrapper.get_draft("draft-1")


def test_post_draft_wraps_underlying_exceptions():
    client = build_client()
    client.post_draft.side_effect = RuntimeError("boom")
    wrapper = APIWrapper(client)

    with pytest.raises(SubstackAPIError, match="Failed to create draft: boom"):
        wrapper.post_draft({"draft_title": "Hello"})


def test_put_draft_wraps_underlying_exceptions():
    client = build_client()
    client.put_draft.side_effect = RuntimeError("boom")
    wrapper = APIWrapper(client)

    with pytest.raises(SubstackAPIError, match="Failed to update draft: boom"):
        wrapper.put_draft("draft-1", title="Updated")


def test_publish_draft_wraps_underlying_exceptions():
    client = build_client()
    client.publish_draft.side_effect = RuntimeError("boom")
    wrapper = APIWrapper(client)

    with pytest.raises(SubstackAPIError, match="Failed to publish draft: boom"):
        wrapper.publish_draft("draft-1")


def test_unschedule_draft_wraps_single_payload_in_list():
    client = build_client()
    client._session.delete.return_value = FakeResponse(
        status_code=200,
        json_data={"id": "schedule-1"},
        text='{"id":"schedule-1"}',
    )
    wrapper = APIWrapper(client)

    result = wrapper.unschedule_draft("draft-1")

    assert result == [{"id": "schedule-1"}]


def test_delete_draft_accepts_success_string():
    client = build_client()
    client.delete_draft.return_value = "Deleted successfully"
    wrapper = APIWrapper(client)

    assert wrapper.delete_draft("draft-1") is True


def test_delete_draft_rejects_failure_string():
    client = build_client()
    client.delete_draft.return_value = "Nope"
    wrapper = APIWrapper(client)

    with pytest.raises(SubstackAPIError, match="Delete failed"):
        wrapper.delete_draft("draft-1")


def test_prepublish_draft_returns_empty_dict_on_failure():
    client = build_client()
    client.prepublish_draft.side_effect = RuntimeError("unsupported")
    wrapper = APIWrapper(client)

    assert wrapper.prepublish_draft("draft-1") == {}


def test_extract_subscriber_count_handles_human_suffixes():
    wrapper = APIWrapper(build_client())

    assert wrapper._parse_human_number("1.2k") == 1200
    assert wrapper._parse_human_number("3m") == 3000000


def test_get_subscriber_count_from_sections_sums_free_and_paid_counts():
    wrapper = APIWrapper(build_client())
    wrapper.get_sections = Mock(
        return_value=[
            {"free_subscriber_count": 10, "paid_subscriber_count": 2},
            {"subscriber_count": 5},
        ]
    )

    assert wrapper._get_subscriber_count_from_sections() == 17
