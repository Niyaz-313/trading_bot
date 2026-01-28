@echo off
cd /d "%~dp0"

echo ========================================
echo Fixing merge conflict in audit logs
echo ========================================
echo.

echo [1/4] Keep server version of audit logs...
git checkout --theirs audit_logs/trades_audit.jsonl
git checkout --theirs audit_logs/trades_audit.csv

echo.
echo [2/4] Stage resolved files...
git add audit_logs/

echo.
echo [3/4] Commit merge resolution...
git commit -m "Merge: keep server audit logs"

echo.
echo [4/4] Push to remote...
git push origin main

echo.
echo ========================================
echo DONE
echo ========================================
pause

cd /d "%~dp0"

echo ========================================
echo Fixing merge conflict in audit logs
echo ========================================
echo.

echo [1/4] Keep server version of audit logs...
git checkout --theirs audit_logs/trades_audit.jsonl
git checkout --theirs audit_logs/trades_audit.csv

echo.
echo [2/4] Stage resolved files...
git add audit_logs/

echo.
echo [3/4] Commit merge resolution...
git commit -m "Merge: keep server audit logs"

echo.
echo [4/4] Push to remote...
git push origin main

echo.
echo ========================================
echo DONE
echo ========================================
pause

cd /d "%~dp0"

echo ========================================
echo Fixing merge conflict in audit logs
echo ========================================
echo.

echo [1/4] Keep server version of audit logs...
git checkout --theirs audit_logs/trades_audit.jsonl
git checkout --theirs audit_logs/trades_audit.csv

echo.
echo [2/4] Stage resolved files...
git add audit_logs/

echo.
echo [3/4] Commit merge resolution...
git commit -m "Merge: keep server audit logs"

echo.
echo [4/4] Push to remote...
git push origin main

echo.
echo ========================================
echo DONE
echo ========================================
pause



