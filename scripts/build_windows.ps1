$ErrorActionPreference = "Stop"

python -m pip install --upgrade pip
python -m pip install -e ".[gui]" pyinstaller

python -m PyInstaller --noconfirm --clean --windowed --name llama-doctor-gui `
  --collect-all PySide6 `
  --collect-data llama_doctor `
  scripts/entry_gui.py

python -m PyInstaller --noconfirm --clean --console --name llama-doctor `
  --collect-data llama_doctor `
  scripts/entry_cli.py

Write-Host "Build complete. See dist/."
