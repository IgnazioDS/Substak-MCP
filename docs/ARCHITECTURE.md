# Architecture

This repository ships a Node wrapper that starts the Python MCP server and forwards stdio traffic to it.

```mermaid
sequenceDiagram
    participant Client as "MCP Client"
    participant Node as "Node Wrapper (src/index.js)"
    participant Python as "Python Server (src/server.py)"
    participant Auth as "AuthHandler"
    participant API as "APIWrapper"
    participant Lib as "python-substack"
    participant Web as "Substack"

    Client->>Node: stdio JSON-RPC
    Node->>Python: spawn `python -m src.server`
    Python->>Python: route `tools/list` or `tools/call`
    alt account-bound tool
        Python->>Auth: authenticate()
        Auth->>API: wrap authenticated client
        API->>Lib: official-ish library methods
        API->>Web: private endpoint HTTP calls when needed
        Lib->>Web: library-managed HTTP/session calls
        Web-->>Lib: response
        Web-->>API: response
        Lib-->>API: normalized library result
        API-->>Python: validated response object
    else public research tool
        Python->>Web: public HTML fetches via aiohttp
        Web-->>Python: public page/search HTML
    end
    Python-->>Node: stdio JSON-RPC result
    Node-->>Client: stdio JSON-RPC result
```

## Supported runtime path

- `src/index.js` is the shipped Node entrypoint.
- `src/server.py` is the only supported Python server entrypoint.
- `AuthHandler` owns cached authenticated clients and cookie-tempfile lifecycle.
- `APIWrapper` is the trust boundary around `python-substack` and private Substack responses.

## Notes

- `tools/list` works without account authentication.
- High-risk write tools use a two-step confirmation token flow enforced in `src/server.py`.
- Research tools fetch only public pages, identify themselves with a project User-Agent, rate-limit per host, and check `robots.txt`.
