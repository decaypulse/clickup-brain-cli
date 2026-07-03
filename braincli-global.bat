@echo off
REM Глобальная команда braincli
REM Если braincli не работает в обычном cmd, используй этот файл

cd /d "C:\Users\decyp\Desktop\clickup-cli"
python clickup_agent.py %*
