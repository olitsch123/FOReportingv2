@echo off
echo ========================================
echo Pushing FOReporting v2 to GitHub
echo Repository: https://github.com/olitsch123/FOReportingv2.git
echo Branch: v2.3
echo ========================================
echo.

echo Adding all changes...
git add -A

echo.
echo Creating commit...
git commit -m "Complete PE functionality implementation - v2.3: Multi-method extraction, validation, reconciliation, and production-ready API endpoints"

echo.
echo Pushing to GitHub...
git push origin v2.3

echo.
echo ========================================
echo Push complete! View your repository at:
echo https://github.com/olitsch123/FOReportingv2/tree/v2.3
echo ========================================
pause