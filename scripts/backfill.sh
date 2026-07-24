#!/bin/bash
#SBATCH --job-name=backfill
#SBATCH --account=r01850
#SBATCH --export=ALL
#SBATCH --nodes=1
#SBATCH --output=logs/backfill_%j.log
#SBATCH --error=logs/backfill_%j.log
#SBATCH --gpus=1
#SBATCH --cpus-per-task=10
#SBATCH --mem=120G
#SBATCH --time=20:00:00
#SBATCH --mail-user=jayeun@iu.edu
#SBATCH --mail-type=BEGIN,FAIL,END
#SBATCH --partition=gpu

set -euo pipefail

: "${SOURCE:?SOURCE must be provided}"
: "${FROM_DATE:?FROM_DATE must be provided}"
: "${TO_DATE:?TO_DATE must be provided}"
: "${CONFIG:=configs/dev.yaml}"
: "${WINDOW_DAYS:=7}"

export OMP_NUM_THREADS="$SLURM_CPUS_PER_TASK"
export UV_CACHE_DIR=/N/project/eml_ai_forecasting/.uv-cache
export PYTHONUNBUFFERED=1
export PYTHONFAULTHANDLER=1
export TQDM_MININTERVAL=10
export TQDM_POSITION=-1

cd /N/project/eml_ai_forecasting/eml_transformer

echo "Source:      $SOURCE"
echo "From date:   $FROM_DATE"
echo "To date:     $TO_DATE"
echo "Window days: $WINDOW_DAYS"
echo "Config:      $CONFIG"

uv run --frozen python -u -m eml_transformer.cli backfill \
    --source "$SOURCE" \
    --from-date "$FROM_DATE" \
    --to-date "$TO_DATE" \
    --window-days "$WINDOW_DAYS" \
    --config "$CONFIG"