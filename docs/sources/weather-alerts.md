# Weather Alerts

`weather_alerts` retrieves active alerts from the National Weather Service API for configured state or area codes. Because the endpoint represents current active alerts, the source is a snapshot and does not support backfill.

The source deduplicates alerts returned for multiple areas. Silver text combines headline, description, and instructions and retains event, severity, urgency, certainty, affected zones, effective/expiration times, and geographic metadata.

Failed area requests are logged and do not prevent other configured areas from being processed.
