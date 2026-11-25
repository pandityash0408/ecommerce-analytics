@echo off
echo Building and starting E-Commerce Analytics Stack (Backend + Frontend + Nginx HTTPS + Cloudflare)...
docker compose up --build -d
docker restart ecommerce-nginx-https >nul 2>&1
echo Waiting 6 seconds for Cloudflare Tunnel public HTTPS URL...
timeout /t 6 /nobreak >nul
for /f "delims=" %%u in ('powershell -NoProfile -Command "(docker logs ecommerce-cloudflare-tunnel 2>&1 | Select-String -Pattern 'https://[a-z0-9-]+\.trycloudflare\.com' -AllMatches).Matches.Value | Select-Object -Last 1"') do set CF_URL=%%u
if defined CF_URL (
    echo Opening live Cloudflare HTTPS URL: %CF_URL%
    start "" "%CF_URL%"
) else (
    echo Cloudflare URL not ready yet; opening https://localhost
    start "" "https://localhost"
)