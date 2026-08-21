# NewsAPI

`newsapi` queries the NewsAPI `/v2/everything` endpoint using a configured query, language, sort order, page size, and page limit. It requires `NEWSAPI_KEY`.

Standardization combines title, description, and available content into a `TextRecord`. Metadata retains the publisher, author, query, language, and sort order.

The source supports incremental date windows and historical backfill, although it is disabled in the current development and production configurations.
