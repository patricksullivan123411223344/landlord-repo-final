@echo off
rem uv.cmd - forward args to uvicorn using configured Python
set PYTHON=C:\Users\ddper\AppData\Local\Python\pythoncore-3.14-64\python.exe
if exist "%PYTHON%" (
  "%PYTHON%" -m uvicorn %*
) else (
  python -m uvicorn %*
)
