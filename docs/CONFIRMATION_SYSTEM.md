# Confirmation System

High-risk write actions are protected by a two-call confirmation flow enforced in `src/server.py`.

## Protected tools

- `create_formatted_post`
- `update_post`
- `publish_post`
- `schedule_post`
- `duplicate_post`
- `delete_draft`

## Flow

### First call

Call the tool without the `confirm_*` flag, or with it set to `false`.

The server returns:

- a human-readable preview of the action
- a short-lived `confirmation_token`
- the exact confirmation field you must set on the next call

The token:

- lives for 5 minutes
- is stored in memory only
- is scoped to the tool name plus the normalized arguments from the preview
- is single-use

### Second call

Recall the same tool with:

- the same arguments used for the preview
- `confirm_*=true`
- `confirmation_token=<token from preview>`

If the token is missing, expired, already used, or the arguments changed, the server rejects the action before running it.

## Example

First call:

```json
{
  "title": "Why SwiftUI image caching matters",
  "content": "..."
}
```

Preview response excerpt:

```text
Confirmation token: abc123...
Reply by recalling the same tool with:
- `confirm_create=true`
- `confirmation_token=abc123...`
```

Second call:

```json
{
  "title": "Why SwiftUI image caching matters",
  "content": "...",
  "confirm_create": true,
  "confirmation_token": "abc123..."
}
```

## Why it exists

Description text alone is not a real safeguard. The token flow prevents a client from blindly calling a destructive tool with `confirm_*=true` on the first turn.
