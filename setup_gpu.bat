@echo off
echo Installing CUDA-enabled PyTorch for RTX GPU (~2.5 GB download)...
echo This uses the project venv at D:\iucee-venv
echo Do NOT close this window until install completes.
echo.

if not exist "D:\iucee-venv\Scripts\python.exe" (
  echo Creating venv at D:\iucee-venv ...
  python -m venv D:\iucee-venv
)

D:\iucee-venv\Scripts\python.exe -m pip install torch==2.6.0+cu124 torchvision==0.21.0+cu124 --index-url https://download.pytorch.org/whl/cu124 --no-cache-dir --default-timeout=1000

echo.
echo Verifying GPU...
D:\iucee-venv\Scripts\python.exe -c "import torch; print('torch', torch.__version__); print('cuda', torch.cuda.is_available()); print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'No GPU')"
echo.
echo Done. Restart the backend with start.bat or start.py
pause
