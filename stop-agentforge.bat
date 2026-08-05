@echo off
setlocal
cd /d "%~dp0"

echo ============================================
echo  Stopping AgentForge stack (project: agentforge)
echo  Note: volumes keep their data (no -v flag)
echo ============================================

docker compose down
docker compose ps
exit /b 0
