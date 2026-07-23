# Getting Started on Quartz HPC

This project uses a self-contained `uv` environment. Quartz provides the GPU and NVIDIA driver; `uv` manages Python, PyTorch, CUDA runtime libraries, and the remaining project dependencies.

## 1. Clone and enter the project

```bash
git clone <repository-url>
cd eml_transformer
```

## 2. Create the environment

Install `uv` if it is not already available, then run:

```bash
uv python install 3.10
uv venv --python 3.10
uv sync --extra embeddings
```

The project configuration should direct PyTorch to the CUDA 12.6 wheel index. You do not need to load the Quartz Python, PyTorch, or CUDA modules.

## 3. Start an interactive GPU session

Use `gpu-debug` for short tests:

```bash
srun \
  --account=r01850 \
  --partition=gpu-debug \
  --time=01:00:00 \
  --nodes=1 \
  --cpus-per-task=10 \
  --mem=120G \
  --gpus=1 \
  --pty bash
```

Use `gpu` for longer V100 jobs. Request `hopper` when an H100 is needed and your account has access.

## 4. Verify GPU access

```bash
nvidia-smi

uv run python - <<'PY'
import torch

print("PyTorch:", torch.__version__)
print("CUDA build:", torch.version.cuda)
print("GPU available:", torch.cuda.is_available())
print("GPU:", torch.cuda.get_device_name() if torch.cuda.is_available() else "None")
PY
```

## 5. Run the project

```bash
uv run eml_transformer --help
uv run eml_transformer embed --source iem_afos
```

For the NVIDIA embedding model on a V100, begin with `batch_size: 1` and limit or chunk long documents. `--mem` controls system RAM, while GPU memory is fixed by the allocated GPU.

## 6. Submit production work

Use an `sbatch` script for long-running backfills or embedding jobs so the process survives disconnects:

```bash
sbatch scripts/<job-script>.sh
```

Useful commands:

```bash
squeue -u "$USER"
sacct -j <job-id> --format=JobID,State,Elapsed,ReqMem,MaxRSS,AllocTRES
scancel <job-id>
```

Do not run compute-intensive work on the login node.
