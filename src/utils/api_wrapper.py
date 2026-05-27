# ABOUTME: API wrapper to handle python-substack string error responses
# ABOUTME: Provides consistent error handling for all API calls

import html
import logging
import re
from typing import Any, Dict, List, cast

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class SubstackAPIError(Exception):
    """Custom exception for Substack API errors"""

    pass


class APIWrapper:
    """Wrapper for python-substack API client to handle string errors"""

    def __init__(self, client: Any) -> None:
        """Initialize wrapper with the underlying client

        Args:
            client: The python-substack API client
        """
        self.client = client
        self.publication_url = client.publication_url

        # Debug logging
        logger.debug(f"APIWrapper initialized with client type: {type(client)}")
        logger.debug(f"Client has get_draft method: {hasattr(client, 'get_draft')}")

    def _handle_response(self, response: Any, method_name: str) -> Any:
        """Handle API response and convert errors to exceptions

        Args:
            response: The API response
            method_name: Name of the method called (for error messages)

        Returns:
            The response if valid

        Raises:
            SubstackAPIError: If response is an error
        """
        if response is None:
            raise SubstackAPIError(f"{method_name} returned None")

        if hasattr(response, "status_code"):
            status_code = getattr(response, "status_code", 200)
            if status_code >= 400:
                payload = None
                try:
                    payload = response.json()
                except Exception:
                    payload = getattr(response, "text", None)

                error_message = self._extract_error_message(payload)
                if not error_message:
                    error_message = getattr(response, "text", "") or "Unknown error"
                raise SubstackAPIError(f"API error: {error_message}")

        if isinstance(response, str):
            logger.error(f"{method_name} returned string: {response}")
            if "not found" in response.lower():
                raise SubstackAPIError("Post not found")
            elif (
                "unauthorized" in response.lower()
                or "authentication" in response.lower()
            ):
                raise SubstackAPIError(
                    "Authentication failed - please check your credentials"
                )
            elif "rate limit" in response.lower():
                raise SubstackAPIError("Rate limit exceeded - please try again later")
            raise SubstackAPIError(f"API error: {response}")

        if isinstance(response, dict):
            error_message = self._extract_error_message(response)
            status = response.get("status")
            if error_message is not None:
                logger.error(f"{method_name} returned error object: {error_message}")
                if "not found" in error_message.lower():
                    raise SubstackAPIError("Post not found")
                if "unauthorized" in error_message.lower():
                    raise SubstackAPIError("Authentication failed")
                raise SubstackAPIError(f"API error: {error_message}")
            if isinstance(status, int) and status >= 400:
                raise SubstackAPIError(
                    f"API error: {response.get('message', 'Unknown error')}"
                )

        return response

    def _extract_error_message(self, response: Any) -> str | None:
        """Best-effort extraction of an error message from varied response shapes."""
        if isinstance(response, dict):
            error = response.get("error")
            if isinstance(error, str) and error:
                return error
            if isinstance(response.get("errors"), list) and response["errors"]:
                return "; ".join(str(item) for item in response["errors"])
            errors_value = response.get("errors")
            if isinstance(errors_value, str) and errors_value:
                return errors_value
            if (
                isinstance(response.get("message"), str)
                and isinstance(response.get("status"), int)
                and response["status"] >= 400
            ):
                return cast(str, response["message"])
            return None

        if isinstance(response, str):
            return response

        return None

    def get_user_id(self) -> str:
        """Get user ID with error handling"""
        try:
            result = self.client.get_user_id()
            # User ID is expected to be a string, so don't use _handle_response
            if result is None:
                raise SubstackAPIError("get_user_id returned None")
            return str(result)
        except AttributeError:
            # Method might not exist
            raise SubstackAPIError("get_user_id method not available")

    def get_draft(self, post_id: str) -> Dict[str, Any]:
        """Get a draft with error handling"""
        try:
            logger.debug(f"APIWrapper.get_draft called with post_id: {post_id}")
            logger.debug(
                f"About to call self.client.get_draft, client type: {type(self.client)}"
            )

            result = self.client.get_draft(post_id)
            # Log what we got back
            logger.debug(f"get_draft({post_id}) returned type: {type(result)}")
            if isinstance(result, str):
                logger.debug(f"get_draft returned string: {result}")

            # Handle the response
            checked_result = self._handle_response(result, "get_draft")

            # Additional validation for draft structure
            if not isinstance(checked_result, dict):
                raise SubstackAPIError(
                    f"Invalid draft response - expected dict, got {type(checked_result)}"
                )

            # Ensure it has at least some expected fields
            # Don't require all fields as draft structure may vary
            if not any(
                key in checked_result
                for key in ["id", "draft_title", "title", "body", "draft_body"]
            ):
                logger.warning(
                    f"Draft response missing expected fields. Keys: {list(checked_result.keys())[:10]}"
                )

            return checked_result

        except SubstackAPIError:
            # Let our own errors bubble up
            raise
        except KeyError as e:
            # Handle KeyError from python-substack
            key_name = str(e).strip("'")
            raise SubstackAPIError(
                f"Missing required field in API response: {key_name}"
            )
        except AttributeError as e:
            # Handle AttributeError (e.g., 'str' object has no attribute 'get')
            logger.error(f"AttributeError in APIWrapper.get_draft: {str(e)}")
            logger.error(f"Full exception details: {repr(e)}")
            raise SubstackAPIError(f"Invalid API response format: {str(e)}")
        except Exception as e:
            logger.error(
                f"Unexpected exception in get_draft: {type(e).__name__}: {str(e)}"
            )
            raise SubstackAPIError(f"Failed to get post {post_id}: {str(e)}")

    def get_drafts(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get drafts with error handling"""
        try:
            logger.info(f"APIWrapper.get_drafts called with limit={limit}")
            logger.info(f"Client type: {type(self.client)}")
            logger.info(f"Client has get_drafts: {hasattr(self.client, 'get_drafts')}")

            result = self.client.get_drafts(limit=limit)
            logger.info(f"get_drafts returned type: {type(result)}")

            # Convert generator to list and check each item
            drafts = []
            for i, draft in enumerate(result):
                logger.debug(f"Processing draft {i+1}")
                checked_draft = self._handle_response(draft, "get_drafts[item]")
                if isinstance(checked_draft, dict):
                    drafts.append(checked_draft)

            logger.info(f"APIWrapper.get_drafts returning {len(drafts)} drafts")
            return drafts
        except Exception as e:
            logger.error(f"get_drafts error: {type(e).__name__}: {str(e)}")
            import traceback

            logger.error(f"Traceback: {traceback.format_exc()}")
            return []

    def get_post_management(
        self,
        view: str,
        limit: int = 25,
        offset: int = 0,
        order_by: str | None = None,
        order_direction: str | None = None,
        search_query: str | None = None,
    ) -> Dict[str, Any]:
        """Fetch rows from Substack's post management dashboard API."""
        try:
            params: Dict[str, Any] = {"offset": offset, "limit": limit}
            if order_by:
                params["order_by"] = order_by
            if order_direction:
                params["order_direction"] = order_direction
            if search_query:
                params["query"] = search_query

            response = self.client._session.get(
                f"{self.publication_url}/api/v1/post_management/{view}",
                params=params,
            )
            self._handle_response(response, f"get_post_management[{view}]")
            payload = self._handle_response(
                response.json(), f"get_post_management[{view}]"
            )
            if not isinstance(payload, dict):
                raise SubstackAPIError("Post management response was not a dictionary")
            return payload
        except Exception as e:
            raise SubstackAPIError(
                f"Failed to load post management view '{view}': {str(e)}"
            )

    def post_draft(self, draft_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a draft with error handling"""
        try:
            result = self.client.post_draft(draft_data)
            payload = self._handle_response(result, "post_draft")
            if not isinstance(payload, dict):
                raise SubstackAPIError("Draft creation response was not a dictionary")
            return payload
        except Exception as e:
            raise SubstackAPIError(f"Failed to create draft: {str(e)}")

    def put_draft(self, post_id: str, **kwargs: Any) -> Dict[str, Any]:
        """Update a draft with error handling"""
        try:
            result = self.client.put_draft(post_id, **kwargs)
            payload = self._handle_response(result, "put_draft")
            if not isinstance(payload, dict):
                raise SubstackAPIError("Draft update response was not a dictionary")
            return payload
        except Exception as e:
            raise SubstackAPIError(f"Failed to update draft: {str(e)}")

    def publish_draft(self, post_id: str) -> Dict[str, Any]:
        """Publish a draft with error handling"""
        try:
            result = self.client.publish_draft(post_id)
            payload = self._handle_response(result, "publish_draft")
            if not isinstance(payload, dict):
                raise SubstackAPIError("Publish response was not a dictionary")
            return payload
        except Exception as e:
            raise SubstackAPIError(f"Failed to publish draft: {str(e)}")

    def schedule_draft(
        self,
        post_id: str,
        trigger_at: str,
        post_audience: str = "everyone",
        email_audience: str = "everyone",
    ) -> Dict[str, Any]:
        """Schedule a draft for future publication."""
        try:
            payload = {
                "trigger_at": trigger_at,
                "post_audience": post_audience,
                "email_audience": email_audience,
            }
            response = self.client._session.post(
                f"{self.publication_url}/drafts/{post_id}/scheduled_release",
                json=payload,
            )
            if response.status_code >= 400:
                raise SubstackAPIError(
                    f"Schedule failed with status {response.status_code}: {response.text}"
                )

            if not response.text.strip():
                return {
                    "id": str(post_id),
                    "postSchedules": [
                        {
                            "trigger_at": trigger_at,
                            "post_audience": post_audience,
                            "email_audience": email_audience,
                        }
                    ],
                }

            payload = self._handle_response(response.json(), "schedule_draft")
            if not isinstance(payload, dict):
                raise SubstackAPIError("Schedule response was not a dictionary")
            return payload
        except Exception as e:
            raise SubstackAPIError(f"Failed to schedule draft: {str(e)}")

    def unschedule_draft(self, post_id: str) -> List[Any]:
        """Remove a scheduled release from a draft."""
        try:
            response = self.client._session.delete(
                f"{self.publication_url}/drafts/{post_id}/scheduled_release"
            )
            if response.status_code >= 400:
                raise SubstackAPIError(
                    f"Unschedule failed with status {response.status_code}: {response.text}"
                )
            data = response.json()
            return data if isinstance(data, list) else [data]
        except Exception as e:
            raise SubstackAPIError(f"Failed to unschedule draft: {str(e)}")

    def delete_draft(self, post_id: str) -> bool:
        """Delete a draft with error handling"""
        try:
            result = self.client.delete_draft(post_id)
            if isinstance(result, str):
                if "deleted" in result.lower() or "success" in result.lower():
                    return True
                else:
                    raise SubstackAPIError(f"Delete failed: {result}")
            return True
        except Exception as e:
            raise SubstackAPIError(f"Failed to delete draft: {str(e)}")

    def prepublish_draft(self, post_id: str) -> Dict[str, Any]:
        """Prepublish a draft with error handling"""
        try:
            result = self.client.prepublish_draft(post_id)
            payload = self._handle_response(result, "prepublish_draft")
            if not isinstance(payload, dict):
                raise SubstackAPIError("Prepublish response was not a dictionary")
            return payload
        except Exception as e:
            # This method might not exist or might fail silently
            logger.warning(f"prepublish_draft failed: {str(e)}")
            return {}

    def get_sections(self) -> List[Dict[str, Any]]:
        """Get sections with error handling"""
        try:
            result = self.client.get_sections()
            if result is None:
                return []
            # Convert generator to list
            sections = []
            for section in result:
                checked_section = self._handle_response(section, "get_sections[item]")
                if isinstance(checked_section, dict):
                    sections.append(checked_section)
            return sections
        except Exception as e:
            logger.error(f"get_sections error: {str(e)}")
            return []

    def get_publication_subscriber_count(self) -> int:
        """Get subscriber count with error handling"""
        checked_sources: List[str] = []
        try:
            # The python-substack method directly accesses ["subscriberCount"]
            # which will raise KeyError if the key doesn't exist
            result = self.client.get_publication_subscriber_count()
            checked_sources.append("python_substack")

            # If we get here, the library successfully extracted the count
            if isinstance(result, (int, float)):
                return int(result)
            else:
                raise SubstackAPIError(
                    f"Unexpected subscriber count type: {type(result)}"
                )

        except KeyError as e:
            # This happens when the API response doesn't have 'subscriberCount' key
            logger.warning(f"subscriberCount key not found in API response: {e}")
            html_count = self._get_subscriber_count_from_publication_page()
            checked_sources.append("publication_page")
            if html_count is not None:
                return html_count

            section_count = self._get_subscriber_count_from_sections()
            checked_sources.append("sections")
            if section_count is not None:
                return section_count

            raise SubstackAPIError(
                "Subscriber count unavailable from publication metadata, page markup, and section summaries"
            )

        except AttributeError as e:
            # Method might not exist or client might be None
            raise SubstackAPIError(f"API client error: {str(e)}")

        except Exception as e:
            # Any other unexpected error
            logger.error(
                f"Unexpected error getting subscriber count: {type(e).__name__}: {str(e)}"
            )
            raise SubstackAPIError(f"Failed to get subscriber count: {str(e)}")

    def get_publication_subscriber_stats(self) -> Dict[str, Any]:
        """Return subscriber count plus source metadata when available."""
        checked_sources: List[str] = []

        try:
            count = self.client.get_publication_subscriber_count()
            checked_sources.append("python_substack")
            if isinstance(count, (int, float)):
                return {
                    "available": True,
                    "total_subscribers": int(count),
                    "source": "python_substack",
                    "checked_sources": checked_sources,
                }
        except KeyError:
            checked_sources.append("python_substack")
        except Exception as exc:
            logger.warning("Primary subscriber count lookup failed: %s", exc)
            checked_sources.append("python_substack")

        html_count = self._get_subscriber_count_from_publication_page()
        checked_sources.append("publication_page")
        if html_count is not None:
            return {
                "available": True,
                "total_subscribers": html_count,
                "source": "publication_page",
                "checked_sources": checked_sources,
            }

        section_count = self._get_subscriber_count_from_sections()
        checked_sources.append("sections")
        if section_count is not None:
            return {
                "available": True,
                "total_subscribers": section_count,
                "source": "sections",
                "checked_sources": checked_sources,
            }

        return {
            "available": False,
            "total_subscribers": None,
            "source": None,
            "checked_sources": checked_sources,
            "reason": "Subscriber count was not exposed in publication metadata, page markup, or section summaries.",
        }

    def _get_subscriber_count_from_sections(self) -> int | None:
        sections = self.get_sections()
        if not sections:
            return None

        total = 0
        found_any = False
        for section in sections:
            count = section.get("subscriber_count", 0)
            if count == 0:
                count = section.get("free_subscriber_count", 0) + section.get(
                    "paid_subscriber_count", 0
                )
            if count:
                found_any = True
                total += int(count)

        return total if found_any else None

    def _get_subscriber_count_from_publication_page(self) -> int | None:
        try:
            response = self.client._session.get(self.publication_url)
            if getattr(response, "status_code", 200) >= 400:
                logger.warning(
                    "Publication page subscriber lookup failed with status %s",
                    getattr(response, "status_code", "unknown"),
                )
                return None
            return self._extract_subscriber_count_from_html(
                getattr(response, "text", "")
            )
        except Exception as exc:
            logger.warning("Publication page subscriber lookup failed: %s", exc)
            return None

    def _extract_subscriber_count_from_html(self, html_text: str) -> int | None:
        if not html_text:
            return None

        patterns = [
            r'"subscriberCount"\s*:\s*([0-9]+)',
            r'"subscriber_count"\s*:\s*([0-9]+)',
            r'"communityCount"\s*:\s*([0-9]+)',
        ]
        for pattern in patterns:
            match = re.search(pattern, html_text)
            if match:
                return int(match.group(1))

        free_paid_match = re.search(
            r'"freeSubscriberCount"\s*:\s*([0-9]+).*?"paidSubscriberCount"\s*:\s*([0-9]+)',
            html_text,
            re.DOTALL,
        )
        if free_paid_match:
            return int(free_paid_match.group(1)) + int(free_paid_match.group(2))

        soup = BeautifulSoup(html_text, "html.parser")
        visible_text = html.unescape(soup.get_text(" ", strip=True))
        text_match = re.search(
            r"([0-9][0-9,\.]*\s*[kKmM]?)\s+subscribers?\b",
            visible_text,
        )
        if text_match:
            return self._parse_human_number(text_match.group(1))

        return None

    def _parse_human_number(self, raw: str) -> int:
        cleaned = raw.replace(",", "").strip().lower()
        multiplier = 1
        if cleaned.endswith("k"):
            multiplier = 1000
            cleaned = cleaned[:-1]
        elif cleaned.endswith("m"):
            multiplier = 1000000
            cleaned = cleaned[:-1]
        return int(float(cleaned) * multiplier)

    def get_image(self, image_path: str) -> Dict[str, Any]:
        """Upload an image to Substack CDN with error handling

        Args:
            image_path: Path to the image file or URL

        Returns:
            Dict with image metadata including URL

        Raises:
            SubstackAPIError: If upload fails
        """
        try:
            result = self.client.get_image(image_path)
            payload = self._handle_response(result, "get_image")
            if not isinstance(payload, dict):
                raise SubstackAPIError("Image upload response was not a dictionary")
            return payload
        except FileNotFoundError:
            raise SubstackAPIError(f"Image file not found: {image_path}")
        except Exception as e:
            logger.error(f"get_image error: {type(e).__name__}: {str(e)}")
            raise SubstackAPIError(f"Failed to upload image: {str(e)}")
