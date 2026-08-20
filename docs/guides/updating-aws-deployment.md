# Updating the AWS Deployment

This guide explains how to deploy a new version of the EML Energy Forecasting Pipeline to AWS.

The API service and scheduled pipeline tasks use the same Docker image, but run different commands. Updating production therefore involves:

1. Building a new Docker image
2. Tagging the image
3. Pushing it to Amazon ECR
4. Creating new ECS task-definition revisions
5. Updating the API service
6. Updating the scheduled pipeline task
7. Verifying the deployment

## Deployment Overview

```text
Updated Code
    ↓
Docker Build
    ↓
Docker Tag
    ↓
Amazon ECR
    ↓
New ECS Task Definitions
   ↙                     ↘
API Service       Scheduled Pipeline Tasks
```

Amazon S3 stores persistent data and model artifacts, so replacing an ECS task does not remove existing pipeline data.

## Prerequisites

Before deploying, confirm that the following are installed and configured:

- Docker
- AWS CLI
- Access to the AWS account
- Permission to push to Amazon ECR
- Permission to update ECS task definitions and services
- Permission to update EventBridge schedules

Verify the local tools:

```bash
docker --version
aws --version
```

Confirm the active AWS identity:

```bash
aws sts get-caller-identity \
    --profile eml-sandbox
```

Replace the profile name when using a different AWS CLI profile.

## Deployment Values

The examples below use the following placeholder values:

| Value | Example |
|---|---|
| AWS account ID | `123456789012` |
| AWS region | `us-east-2` |
| ECR repository | `eml-transformer` |
| Image version | `2026-08-20-1` |
| ECS cluster | `eml-cluster` |
| API service | `eml-api-service` |

The complete ECR image URI follows this format:

```text
{account-id}.dkr.ecr.{region}.amazonaws.com/{repository}:{tag}
```

For example:

```text
123456789012.dkr.ecr.us-east-2.amazonaws.com/eml-transformer:2026-08-20-1
```

Use the actual values from the AWS environment when running these commands.

## 1. Prepare the Update

Before building the production image:

1. Confirm that the intended code is committed.
2. Run the automated tests.
3. Test the relevant pipeline stages locally.
4. Confirm that production configuration changes are included.
5. Choose a unique image version.

Run the tests:

```bash
uv run pytest
```

If configuration files are copied into the Docker image, any production configuration change requires a new image build.

## 2. Choose an Image Tag

Use a unique tag for every deployment.

Examples include:

```text
2026-08-20-1
v0.3.0
git-a1b2c3d
```

A versioned tag makes it possible to identify the code used by each ECS task and roll back to an earlier image.

Avoid relying only on `latest`. Reusing `latest` makes deployments and rollbacks harder to trace.

## 3. Build the Docker Image

Run the build from the repository root:

```bash
docker build \
    -t eml-transformer:2026-08-20-1 \
    .
```

If the ECS task uses an `x86_64` Fargate runtime, explicitly build for that platform when necessary:

```bash
docker build \
    --platform linux/amd64 \
    -t eml-transformer:2026-08-20-1 \
    .
```

The image platform must match the CPU architecture configured in the ECS task definition.

## 4. Test the Image Locally

Confirm that the CLI is available inside the image:

```bash
docker run --rm \
    eml-transformer:2026-08-20-1 \
    eml_transformer --help
```

Test the API startup when practical:

```bash
docker run --rm \
    -p 8000:8000 \
    eml-transformer:2026-08-20-1
```

Then check:

```text
http://127.0.0.1:8000/health
```

Local container tests may require environment variables or AWS credentials when the production configuration uses external APIs or Amazon S3.

## 5. Authenticate Docker with ECR

Authenticate Docker with the private ECR registry:

```bash
aws ecr get-login-password \
    --region us-east-2 \
    --profile eml-sandbox \
| docker login \
    --username AWS \
    --password-stdin \
    123456789012.dkr.ecr.us-east-2.amazonaws.com
```

The ECR authentication token is temporary. Run this command again if Docker reports that authentication has expired.

See the official [Amazon ECR image-push documentation](https://docs.aws.amazon.com/AmazonECR/latest/userguide/docker-push-ecr-image.html) for the current authentication process.

## 6. Tag the Image for ECR

Tag the local image with the complete ECR URI:

```bash
docker tag \
    eml-transformer:2026-08-20-1 \
    123456789012.dkr.ecr.us-east-2.amazonaws.com/eml-transformer:2026-08-20-1
```

Confirm that both tags exist:

```bash
docker images eml-transformer
```

## 7. Push the Image to ECR

Push the versioned image:

```bash
docker push \
    123456789012.dkr.ecr.us-east-2.amazonaws.com/eml-transformer:2026-08-20-1
```

Verify that the image is available:

```bash
aws ecr describe-images \
    --repository-name eml-transformer \
    --region us-east-2 \
    --profile eml-sandbox
```

The image must be present in ECR before an ECS task definition references it.

## Optional: Update the `latest` Tag

A versioned tag should be the primary deployment identifier. If the repository also maintains `latest`, apply and push it separately:

```bash
docker tag \
    eml-transformer:2026-08-20-1 \
    123456789012.dkr.ecr.us-east-2.amazonaws.com/eml-transformer:latest
```

```bash
docker push \
    123456789012.dkr.ecr.us-east-2.amazonaws.com/eml-transformer:latest
```

Pushing a new `latest` image does not replace containers that are already running.

If an ECS service continues using the same `latest` task definition, it must be forced to start a new deployment so its replacement tasks pull the updated image.

```bash
aws ecs update-service \
    --cluster eml-cluster \
    --service eml-api-service \
    --force-new-deployment \
    --region us-east-2 \
    --profile eml-sandbox
```

AWS documents this behavior in the [`update-service` CLI reference](https://docs.aws.amazon.com/cli/latest/reference/ecs/update-service.html).

Using a new versioned image and task-definition revision is preferred because it makes the deployed version explicit.

## 8. Create New ECS Task-Definition Revisions

ECS task definitions are revisioned. Create a new revision rather than modifying an existing revision.

If the API and pipeline use separate task-definition families, update both:

```text
API task definition
Pipeline task definition
```

For each task definition:

1. Open Amazon ECS in the AWS Console.
2. Select **Task definitions**.
3. Select the appropriate task-definition family.
4. Select the current revision.
5. Choose **Create new revision**.
6. Update the container image URI.
7. Confirm environment variables, IAM roles, logging, CPU, memory, and networking settings.
8. Create the revision.

Set the image to the versioned ECR URI:

```text
123456789012.dkr.ecr.us-east-2.amazonaws.com/eml-transformer:2026-08-20-1
```

The API and pipeline task definitions may use the same image while supplying different commands.

Example API command **Default command inside the docker file**:

```text
uvicorn eml_transformer.api.main:app --host 0.0.0.0 --port 8000
```

Example pipeline command:

```text
eml_transformer workflows numeric --config configs/prod.yaml
```

The exact commands should match the package entry points and production configuration.

See the official [ECS task-definition update guide](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/update-task-definition-console-v2.html).

## 9. Update the API Service

Update the persistent ECS API service to use the new task-definition revision.

Using the AWS Console:

1. Open the ECS cluster.
2. Select the API service.
3. Choose **Update**.
4. Select the new API task-definition revision.
5. Enable a new deployment.
6. Complete the update.

Using the AWS CLI:

```bash
aws ecs update-service \
    --cluster eml-cluster \
    --service eml-api-service \
    --task-definition eml-api-task:NEW_REVISION \
    --region us-east-2 \
    --profile eml-sandbox
```

Replace `NEW_REVISION` with the revision that references the new image.

ECS starts replacement tasks using the new revision and removes the old tasks according to the service's deployment settings.

See the official [ECS service-update documentation](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/update-service-console-v2.html).

## 10. Monitor the API Deployment

Wait for the ECS service to become stable:

```bash
aws ecs wait services-stable \
    --cluster eml-cluster \
    --services eml-api-service \
    --region us-east-2 \
    --profile eml-sandbox
```

Inspect the service:

```bash
aws ecs describe-services \
    --cluster eml-cluster \
    --services eml-api-service \
    --region us-east-2 \
    --profile eml-sandbox
```

Confirm that:

- The deployment uses the expected task-definition revision.
- The desired number of tasks is running.
- No tasks are repeatedly stopping.
- The health check succeeds.
- CloudWatch does not show startup errors.

Test the deployed API:

```bash
curl http://<api-address>/health
```

Also test at least one endpoint that reads production storage.

## 11. Test the Pipeline Task Manually

Before updating the schedule, run the new pipeline task definition manually.

In the ECS Console:

1. Open the cluster.
2. Choose **Run new task**.
3. Select the new pipeline task-definition revision.
4. Use the same networking and security settings as the scheduled task.
5. Run the task.
6. Monitor its CloudWatch logs.
7. Confirm that it exits successfully.

Verify that the task:

- Starts with the expected image
- Loads `configs/prod.yaml`
- Connects to Amazon S3
- Reaches required external APIs
- Writes the expected outputs
- Updates checkpoints only after successful processing
- Exits with code `0`

Testing the task manually prevents a broken revision from being introduced directly into the production schedule.

## 12. Update the Scheduled Pipeline Task

EventBridge Scheduler starts the pipeline using a particular ECS task definition.

Update the schedule so its ECS target uses the new pipeline task-definition revision.

Using the AWS Console:

1. Open EventBridge Scheduler.
2. Select the pipeline schedule.
3. Choose **Edit**.
4. Locate the ECS task target.
5. Select the new task-definition revision.
6. Confirm the cluster, subnets, security groups, IAM role, and command.
7. Save the schedule.

Verify the following values carefully:

- ECS cluster
- Task-definition revision
- Launch type or capacity provider
- Subnets
- Security groups
- Public IP setting
- EventBridge execution role
- Container command
- Environment overrides

Updating the API service does not automatically update the EventBridge schedule. They are separate workloads and must be updated independently.

## 13. Confirm Source Publication Timing

The schedule starts the pipeline at the configured time whether or not external APIs have published new data.

When the task runs, ingestion collects whatever data is currently available. If expected records have not yet been published, they cannot be used by downstream feature, dataset, or forecasting stages during that run.

After updating the schedule, confirm that its execution time accounts for:

- Source publication frequency
- Typical publication delay
- Late or revised records
- Workflow execution time
- Desired forecast-delivery time

Overlapping ingestion windows and deduplication allow a later task to collect records that were unavailable during an earlier run.

## 14. Verify the Scheduled Run

After the next scheduled execution, confirm:

- EventBridge successfully started the ECS task.
- The task used the expected task-definition revision.
- The task pulled the expected image version.
- The workflow completed successfully.
- CloudWatch contains the expected logs.
- New data and forecasts appear in S3.
- The API can return the new forecast output.

Do not consider the deployment complete until both the API service and scheduled pipeline task have been verified.

## Rollback

Versioned image tags and task-definition revisions make rollback straightforward.

### Roll Back the API

Update the API service to a previous task-definition revision:

```bash
aws ecs update-service \
    --cluster eml-cluster \
    --service eml-api-service \
    --task-definition eml-api-task:PREVIOUS_REVISION \
    --region us-east-2 \
    --profile eml-sandbox
```

### Roll Back the Scheduled Pipeline

Edit the EventBridge schedule and restore the previous pipeline task-definition revision.

Because stored data and models are persistent, determine whether the failed deployment wrote any incorrect outputs before rerunning an older version.

Do not delete the new image or task-definition revision until the problem has been investigated.

## Deployment Checklist

### Before Building

- [ ] Confirm the intended code is committed
- [ ] Run automated tests
- [ ] Test affected stages locally
- [ ] Review production configuration
- [ ] Choose a unique image tag

### Build and Push

- [ ] Build the Docker image
- [ ] Test the image locally
- [ ] Authenticate Docker with ECR
- [ ] Tag the image with the ECR URI
- [ ] Push the versioned image
- [ ] Verify that the image exists in ECR

### ECS

- [ ] Create a new API task-definition revision
- [ ] Create a new pipeline task-definition revision
- [ ] Update the API service
- [ ] Wait for the service to become stable
- [ ] Test the API health endpoint
- [ ] Run the pipeline task manually
- [ ] Verify the manual task in CloudWatch

### Scheduling

- [ ] Update the EventBridge schedule
- [ ] Confirm the scheduled task-definition revision
- [ ] Confirm network and IAM settings
- [ ] Confirm source publication timing
- [ ] Verify the next scheduled run
- [ ] Confirm that new forecasts are available through the API

## Quick Command Summary

Build:

```bash
docker build \
    -t eml-transformer:2026-08-20-1 \
    .
```

Authenticate:

```bash
aws ecr get-login-password \
    --region us-east-2 \
    --profile eml-sandbox \
| docker login \
    --username AWS \
    --password-stdin \
    123456789012.dkr.ecr.us-east-2.amazonaws.com
```

Tag:

```bash
docker tag \
    eml-transformer:2026-08-20-1 \
    123456789012.dkr.ecr.us-east-2.amazonaws.com/eml-transformer:2026-08-20-1
```

Push:

```bash
docker push \
    123456789012.dkr.ecr.us-east-2.amazonaws.com/eml-transformer:2026-08-20-1
```

Update the API:

```bash
aws ecs update-service \
    --cluster eml-cluster \
    --service eml-api-service \
    --task-definition eml-api-task:NEW_REVISION \
    --region us-east-2 \
    --profile eml-sandbox
```

Wait for stability:

```bash
aws ecs wait services-stable \
    --cluster eml-cluster \
    --services eml-api-service \
    --region us-east-2 \
    --profile eml-sandbox
```

## Related Documentation

- [AWS Deployment](../architecture/aws-deployment.md)
- [Local Setup](../guides/local-setup.md)
- [Configuration](../guides/configuration.md)
- [Workflows](workflows.md)
- [Scheduling](scheduling.md)
- [Logging](logging.md)
- [Monitoring](monitoring.md)
- [Troubleshooting](troubleshooting.md)
- [Amazon ECR: Pushing an image](https://docs.aws.amazon.com/AmazonECR/latest/userguide/docker-push-ecr-image.html)
- [Amazon ECS: Updating a service](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/update-service-console-v2.html)