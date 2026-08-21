# GDELT

`gdelt` retrieves GDELT 2.0 GKG files for 15-minute timestamps and filters records using configured themes, organizations, and locations.

Bronze records retain selected GKG fields. Silver records contain page title when available, URL, themes, organizations, people, locations, tone, filter evidence, and publication-time provenance. Article text is initially empty and is populated by the scraping stage.

The source supports backfill. Its normal text path is:

```text
ingest → standardize → scrape → embed
```

Scraping is currently marked for migration to the shared batched dataset interface before large AWS runs.
