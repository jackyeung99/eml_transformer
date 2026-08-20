# AWS Deployment

The EML Energy Forecasting Pipeline uses a simple AWS deployment designed to support the current project without introducing unnecessary infrastructure.

The deployment separates two workloads:

- A persistent API that provides access to stored data and forecasts
- Pipeline tasks that run on demand or on a schedule and stop after completing

This design is intentionally minimal, but it can be expanded as data volume, traffic, and operational requirements increase.

## Deployment Overview

The production deployment uses the following AWS services:

| Service | Responsibility |
|---|---|
| Amazon ECR | Stores the application container image. |
| Amazon ECS | Manages the API service and pipeline tasks. |
| AWS Fargate | Runs containers without requiring dedicated server management. |
| Amazon S3 | Stores pipeline data, model artifacts, and forecasts. |
| EventBridge Scheduler | Starts pipeline tasks on a configured schedule. |
| Amazon CloudWatch | Stores logs from the API and pipeline tasks. |

## High-Level Architecture

```text
Application Code
      ↓
Docker Image
      ↓
Amazon ECR
      ↓
Amazon ECS on Fargate
   ↙                 ↘
API Service       Pipeline Tasks
   ↘                 ↙
        Amazon S3
```

The API and pipeline workloads use the same application image but run different commands.

## Container Image

The application is packaged as a Docker image.

The image contains:

- The Python application
- Runtime dependencies
- Production configuration
- CLI commands
- The FastAPI service

The image is built locally or through a build process and pushed to Amazon ECR.

Using one image ensures that the API and pipeline tasks use the same application version and dependencies.

## API Service

The FastAPI application runs as a persistent ECS service.

Its responsibilities include:

- Reporting service health
- Reading stored datasets and forecasts
- Returning model and configuration information
- Providing data to a dashboard or other application

ECS keeps the desired number of API tasks running. If an API task stops unexpectedly, ECS can start a replacement.

The API reads persistent data from Amazon S3 rather than relying on files stored inside the container.

## Pipeline Tasks

Pipeline workflows run as ECS tasks.

Unlike the API, a pipeline task:

1. Starts a container.
2. Runs a CLI stage or workflow.
3. Reads and writes data in Amazon S3.
4. Sends logs to CloudWatch.
5. Stops after the command completes.

Pipeline tasks can be started manually or by a schedule.

This avoids running a pipeline container continuously when no processing work is required.

## Scheduling

EventBridge Scheduler starts ECS pipeline tasks at configured times.

A scheduled task specifies:

- The ECS cluster
- The pipeline task definition
- The container command
- The schedule
- The required network and IAM settings

For example, a schedule may start a numeric forecasting workflow once per hour. The task exits when the workflow finishes, and a new task is created during the next scheduled run.

> **Important: Source publication timing**
>
> EventBridge starts the task according to the configured schedule regardless of whether an external source has published new data.
>
> When the task runs, the ingestion pipeline requests the data currently available from each source. If expected records have not yet been published, they cannot be collected during that run and may not be available to downstream forecasting stages.
>
> Schedules should therefore account for each source's typical publication delay. When publication times are uncertain, ingestion can use an overlapping lookback window and deduplication so late records can be collected during a later run.
## Persistent Storage

Amazon S3 is the persistent storage backend for the deployed system.

S3 contains:

- Bronze source records
- Silver standardized records
- Gold features and datasets
- Stored forecasts
- Pipeline checkpoints
- Deduplication state
- Trained models and metadata

Both the API and pipeline tasks access the same bucket and prefixes.

Containers should be treated as temporary compute environments. Files stored only inside a running container may be lost when the task stops.

The S3 organization is documented in [Storage Layout](storage-layout.md).

## Logging

The API service and pipeline tasks send logs to Amazon CloudWatch.

CloudWatch logs can be used to inspect:

- Application startup
- Pipeline progress
- Record counts
- Warnings and errors
- API failures
- Task completion

Each workload should use a clearly named log group or log stream so API and pipeline logs can be distinguished.

## Permissions

ECS tasks use IAM task roles to access required AWS resources.

The API task requires permission to read the data and artifacts it serves.

Pipeline tasks may require permission to:

- Read existing data
- Write new data
- Update checkpoints
- Save trained models
- Write forecasts

EventBridge also requires permission to start the configured ECS task.

Permissions should be limited to the resources and operations required by each workload.

## Networking

ECS tasks run within a configured VPC and subnets.

The API must be reachable by the applications or users that consume it. Pipeline tasks require outbound access to external data sources and access to Amazon S3.

The current network design should remain as simple as possible while providing the required connectivity and security.

## Deployment Flow

A typical deployment follows this sequence:

```text
Build Docker image
    ↓
Push image to Amazon ECR
    ↓
Update ECS task definitions
    ↓
Deploy or restart API service
    ↓
Run pipeline task manually or by schedule
```

Updating the container image does not automatically update already running ECS tasks. The relevant service or task must use a task definition that references the new image version.

## Future Expansion

The current deployment is intentionally simple. It provides persistent forecast access and scheduled data processing without requiring a large platform.

As the project grows, the deployment could be expanded with:

- An Application Load Balancer
- HTTPS and a custom domain
- API authentication
- ECS service auto scaling
- Separate task definitions for different workflows
- S3 lifecycle and versioning rules
- CloudWatch alarms
- Failure notifications
- Dead-letter queues
- Workflow orchestration using AWS Step Functions
- Infrastructure as code
- Automated container builds and deployments
- Additional development and production environments

These additions should be introduced when there is a clear operational need rather than added before they are required.

## Related Documentation

- [Architecture Overview](overview.md) — Major system components
- [Data Flow](data-flow.md) — How data moves through the pipeline
- [Storage Layout](storage-layout.md) — Organization of data and artifacts
- [Workflows](../operations/workflows.md) — Multi-stage pipeline execution
- [Scheduling](../operations/scheduling.md) — Scheduled workflow configuration
- [Logging](../operations/logging.md) — Application and pipeline logging
- [Monitoring](../operations/monitoring.md) — Operational health checks