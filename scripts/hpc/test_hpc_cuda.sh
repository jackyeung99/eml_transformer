#!/bin/bash
#SBATCH -J test_gpu_job
#SBATCH -A r01850
#SBATCH -p gpu-debug
#SBATCH --gres=gpu:1
#SBATCH --output=/N/project/eml_ai_forecasting/eml_transformer/logs/test_%j.out
#SBATCH --error=/N/project/eml_ai_forecasting/eml_transformer/logs/test_%j.err
#SBATCH --time=00:10:00
#SBATCH --cpus-per-task=2
#SBATCH --export=ALL

echo "JOB STARTED"
echo "Partition: $SLURM_JOB_PARTITION"
echo "Job ID: $SLURM_JOB_ID"
echo "GPUs requested: $SLURM_GPUS"
echo "CUDA visible devices: $CUDA_VISIBLE_DEVICES"

hostname
date

module load python/gpu/3.12.5

cd /N/project/eml_ai_forecasting/eml_transformer

python --version

echo "NVIDIA GPU TEST"
nvidia-smi

echo "Python CUDA test"
python - <<'PY'
import torch

print("torch version:", torch.__version__)
print("cuda available:", torch.cuda.is_available())

if torch.cuda.is_available():
    print("gpu count:", torch.cuda.device_count())
    print("gpu name:", torch.cuda.get_device_name(0))
    x = torch.randn(1000, 1000, device="cuda")
    y = x @ x
    print("matrix test ok:", y.shape)
PY

echo "JOB FINISHED"