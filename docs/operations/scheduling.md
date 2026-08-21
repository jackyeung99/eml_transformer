# Scheduling

Production workflows run as short-lived ECS tasks started by EventBridge Scheduler. The API is a separate persistent ECS service.

The recommended scheduled command for the numeric pipeline is:

```text
eml_transformer workflow numeric --config configs/prod.yaml
```

The schedule target must define the ECS cluster, task-definition revision, networking, execution role, and container command. The task exits after the workflow completes.

> **Source publication timing**
>
> EventBridge starts a task at the configured time whether or not an external API has published new data. Ingestion collects whatever is available at that moment. Schedule enough delay for the slowest required source, and retain overlapping lookback windows so a later run can collect late records safely.

Monitor scheduled executions in EventBridge, ECS, and CloudWatch. A stopped task with a nonzero exit code requires investigation before the next run.

See [AWS Deployment](../architecture/aws-deployment.md), [Workflows](workflows.md), and [Updating AWS](../guides/updating-aws-deployment.md).
