@echo off
chcp 65001 >nul
cd /d "E:\02_projects\03_PythonProject\Operator-recommend-system\Algorithm_classification\system_redesign"
if "%DEEPSEEK_API_KEY%"=="" (
  echo DEEPSEEK_API_KEY is not set. Set it in the environment before running this script.
  pause
  exit /b 1
)
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
python scripts/demo_interactive_workflow_qa.py --server
pause
