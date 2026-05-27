# Features

This file describes the behavior the repository actually ships today.

## Account tools

- Create, update, publish, schedule, duplicate, and delete drafts.
- Read drafts and published posts.
- List drafts, scheduled posts, and published posts.
- Inspect sections and post analytics.
- Upload images from a local path or a direct image URL.
- Generate the best available draft preview link.

### Safety behavior

- Create, update, publish, schedule, duplicate, and delete all require a confirmation token issued by a preview response.
- Scheduling uses a reverse-engineered endpoint and should be smoke-tested on a real publication before relying on it for release claims.
- Draft preview links are not guaranteed to be shareable. When Substack does not expose a preview token, the server returns an author-only `/publish/post/...` URL.
- Image uploads reject files larger than 25 MB and validate supported image content before upload.

## Public research tools

- Fetch and parse a publication's official RSS feed.
- Describe officially supported integration surfaces for publications, posts, and notes.
- Query Substack's Developer API for public profile matches by LinkedIn handle.
- Search for public Substack posts and publications.
- Inspect a public post URL.
- Inspect a public publication URL.
- Build a topic study plan from public results.
- Heuristically summarize coding lessons from public research results.

### Research limitations

- Developer API profile search may require prior Substack approval and a token even though the returned data is public read-only.
- Research tools use public HTML only; they do not access private publication data.
- Results depend on what search providers and public pages expose.
- The coding-lessons output is heuristic and should be treated as study guidance, not extracted fact.
- Requests use a transparent project User-Agent, obey per-host pacing, and check `robots.txt`.

## Strategy tools

- Analyze your own posts for recurring themes.
- Generate post ideas from a topic plus optional account history.
- Repurpose a post into another format.
- Compare your themes against market themes.
- Generate title and hook options.
- Plan a short series.
