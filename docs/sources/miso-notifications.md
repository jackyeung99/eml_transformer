# MISO Notifications

`miso_notifications` retrieves grouped operational notifications from MISO. The endpoint returns the current notification snapshot, so the source does not support historical backfill.

Standardization converts HTML bodies to text and produces `TextRecord` output with subject, publication time, MISO region, notification URL, topic categories, and notification metadata.

The source participates in ingestion, standardization, and embedding in the current development and production configurations.
