#!/bin/bash
#SBATCH --job-name=publish-silver
#SBATCH --account=r01850
#SBATCH --output=/N/project/eml_ai_forecasting/eml_transformer/logs/publish_silver_%j.log
#SBATCH --error=/N/project/eml_ai_forecasting/eml_transformer/logs/publish_silver_%j.log
#SBATCH --time=02:00:00
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G

set -euo pipefail

PROJECT_DIR="/N/project/eml_ai_forecasting/eml_transformer"
BUCKET="eml_transformer"
AWS_PROFILE="eml-sandbox"

cd "$PROJECT_DIR"

aws sts get-caller-identity \
    --profile "$AWS_PROFILE" \
    >/dev/null

aws s3 sync \
    "$PROJECT_DIR/data/silver/" \
    "s3://${BUCKET}/silver/" \
    --profile "$AWS_PROFILE" \
    --only-show-errors

echo "Silver sync completed at $(date --iso-8601=seconds)"


aws s3 sync \
    "/N/project/eml_ai_forecasting/eml_transformer/data/silver/" \
    "s3://eml_transformer/silver/" \
    --profile "eml-sandbox \
    --only-show-errors