# Reverse-Engineered Endpoints

These endpoints are not documented by Substack as public APIs. They are in active use by this project and are treated as unstable.

Confirmed on: 2026-05-27  
Last verified against Substack web on 2026-05-27

## `GET {publication_url}/api/v1/post_management/{view}`

- Used by: `list_scheduled_posts`, `list_published`, `get_post_analytics`, and strategy tools that inspect published posts.
- Views used:
  - `scheduled`
  - `published`
- Query params:
  - `offset` integer
  - `limit` integer
  - optional `order_by`
  - optional `order_direction`
  - optional `query`
- Observed response shape:

```json
{
  "posts": [
    {
      "id": "post-123",
      "draft_title": "Sooner Post",
      "title": "Sooner Post",
      "trigger_at": "2026-03-09T09:00:00Z",
      "post_audience": "only_paid",
      "email_audience": "only_free",
      "audience": "everyone",
      "stats": {
        "views": 1200,
        "sent": 800,
        "delivered": 760,
        "opened": 304
      }
    }
  ],
  "total": 1
}
```

## `POST {publication_url}/drafts/{post_id}/scheduled_release`

- Used by: `schedule_post`
- Request body:

```json
{
  "trigger_at": "2026-03-27T00:15:00Z",
  "post_audience": "everyone",
  "email_audience": "everyone"
}
```

- Observed response shapes:
  - empty-body `200 OK`, treated as success and normalized locally
  - JSON success payload with `postSchedules`

## `DELETE {publication_url}/drafts/{post_id}/scheduled_release`

- Used by: internal `APIWrapper.unschedule_draft()` helper
- Request body: none
- Observed response shape:
  - JSON list or JSON object describing remaining schedules or unscheduled state

## `GET {publication_url}`

- Used by: subscriber-count fallback for `get_subscriber_count`
- Request body: none
- Observed response shape:
  - public HTML page, parsed for:
    - embedded `subscriberCount`
    - embedded `freeSubscriberCount` and `paidSubscriberCount`
    - visible text like `12.5k subscribers`

## Official-ish library methods still treated as unstable

The project also relies on `python-substack` methods whose return shapes are not trusted:

- `get_draft`
- `get_drafts`
- `post_draft`
- `put_draft`
- `publish_draft`
- `prepublish_draft`
- `get_sections`
- `get_publication_subscriber_count`
- `get_image`

The wrapper layer assumes these may return `dict`, `str`, `None`, generator items, or response-like failures.
