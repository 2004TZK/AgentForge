@echo off
setlocal
cd /d "%~dp0"

echo ============================================
echo  Starting AgentForge stack (project: agentforge)
echo  Services: mysql redis qdrant migrate ssl-init ai backend web nginx
echo  Volumes: mysql-data / qdrant-data / redis-data / uploads
echo ============================================

docker compose up -d --build
if errorlevel 1 goto :error

echo.
echo  AgentForge is running. All volumes started together.
docker compose ps
exit /b 0

:error
echo.
echo  FAILED to start AgentForge. Make sure Docker Desktop is running.
exit /b 1
