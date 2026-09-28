:: SPDX-FileCopyrightText: 2026 Harvey Mudd Clinic Team
:: SPDX-License-Identifier: BSD-3-Clause-Clear

@echo off
setlocal EnableDelayedExpansion

if /i "%~1"=="-h"     goto :usage
if /i "%~1"=="--help" goto :usage
if /i "%~1"=="/?"     goto :usage
goto :main

:usage
echo regen-udb-ls.bat  -  rebuild the UDB language server and install it
echo                      into the udb-vscode extension's server/ folder.
echo.
echo Usage:
echo   regen-udb-ls.bat        Rebuild and install the language server.
echo   regen-udb-ls.bat -h     Show this help.
echo.
echo Environment overrides:
echo   PARENT_DIR   Path to org.xtext.udb.parent
echo   VSCODE_DIR   Path to udb-vscode  (server/ is created inside it)
exit /b 0

:main

:: ─────────────────────────────────────────────
:: regen-udb-ls.bat  (Windows; see regen-udb-ls.sh for macOS/Linux)
::
:: WHAT THIS DOES
::   Rebuilds the UDB language server and installs it into the VS Code
::   extension so the extension has a server to launch.
::
::   The UDB VS Code extension provides editing support (syntax checking,
::   validation) for UDB spec files. That support is powered by a Java
::   language server built from the Xtext project under tools/eclipse.
::   This script (1) builds that server into a fat jar via Maven, then
::   (2) copies it, renamed to udb-ls-all.jar, into the extension's
::   server/ folder, along with the idlc/ and vendor/ Ruby folders the
::   server needs at runtime for IDL parsing.
::
::   Run this after changing the grammar or server code to refresh what
::   the extension ships. It builds the server and installs it with
::   prerequisite checks and a build-retry fallback for flaky builds.
::
:: USAGE
::   regen-udb-ls.bat            rebuild and install
::   regen-udb-ls.bat -h         show help
::
:: ENV OVERRIDES
::   PARENT_DIR   path to org.xtext.udb.parent
::   VSCODE_DIR   path to udb-vscode
:: ─────────────────────────────────────────────

:: ── resolve script directory ─────────────────
set "SCRIPT_DIR=%~dp0..\..\..\"
:: strip trailing backslash
if "%SCRIPT_DIR:~-1%"=="\" set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"

:: ── paths (override via env var if needed) ───
if not defined PARENT_DIR (
    set "PARENT_DIR=%SCRIPT_DIR%\tools\eclipse\dev\org.xtext.udb.parent"
)
if not defined VSCODE_DIR (
    set "VSCODE_SERVER_DIR=%SCRIPT_DIR%\udb-vscode\server"
) else (
    set "VSCODE_SERVER_DIR=%VSCODE_DIR%\server"
)
set "IDE_TARGET=%PARENT_DIR%\org.xtext.udb.ide\target"
set "JRUBY_DIR=%PARENT_DIR%\org.xtext.udb.jruby"

:: ── preflight checks ─────────────────────────
echo [INFO]  Checking prerequisites...

where mvn >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Maven not found.
    echo [ERROR] Install it from https://maven.apache.org/download.cgi
    echo [ERROR] and add it to your PATH, then rerun this script.
    exit /b 1
)
echo [OK]    Maven found.

if not exist "%PARENT_DIR%" (
    echo [ERROR] Parent project not found at: %PARENT_DIR%
    echo [ERROR] Set PARENT_DIR env var to override.
    exit /b 1
)

if not exist "%VSCODE_SERVER_DIR%" (
    echo [WARN]  VS Code server dir not found at: %VSCODE_SERVER_DIR% -- creating it...
    mkdir "%VSCODE_SERVER_DIR%"
    echo [OK]    Created: %VSCODE_SERVER_DIR%
)

:: ── build ────────────────────────────────────
cd /d "%PARENT_DIR%"
echo [INFO]  Working directory: %PARENT_DIR%

call :run_build
if errorlevel 1 (
    echo [WARN]  Build failed -- attempting Tycho cache fix...

    if exist "%USERPROFILE%\.m2\repository\.cache\tycho" (
        rmdir /s /q "%USERPROFILE%\.m2\repository\.cache\tycho"
        echo [INFO]  Tycho cache cleared.
    )

    set "MAVEN_OPTS=%MAVEN_OPTS% -Djdk.xml.maxGeneralEntitySizeLimit=0 -Djdk.xml.totalEntitySizeLimit=0"
    echo [INFO]  Retrying build...

    call :run_build
    if errorlevel 1 (
        echo [ERROR] Build failed even after cache clear. Check Maven output above.
        exit /b 1
    )
)

:: ── locate JAR ───────────────────────────────
echo [INFO]  Locating generated JAR in %IDE_TARGET% ...
set "JAR_PATH="
for %%f in ("%IDE_TARGET%\*SNAPSHOT-ls.jar") do (
    set "JAR_PATH=%%f"
)

if not defined JAR_PATH (
    echo [ERROR] No *SNAPSHOT-ls.jar found in %IDE_TARGET%
    echo [ERROR] Try refreshing the folder and check the build output.
    exit /b 1
)
echo [OK]    Found: %JAR_PATH%

:: ── copy and rename JAR ───────────────────────
set "DEST=%VSCODE_SERVER_DIR%\udb-ls-all.jar"
echo [INFO]  Copying JAR to %DEST% ...
copy /y "%JAR_PATH%" "%DEST%" >nul
echo [OK]    Done! JAR installed at: %DEST%

:: ── copy idlc folder ─────────────────────────
if not exist "%JRUBY_DIR%\idlc" (
    echo [WARN]  idlc folder not found at: %JRUBY_DIR%\idlc -- skipping.
) else (
    echo [INFO]  Copying idlc to %VSCODE_SERVER_DIR%\idlc ...
    if exist "%VSCODE_SERVER_DIR%\idlc" rmdir /s /q "%VSCODE_SERVER_DIR%\idlc"
    xcopy /e /i /q "%JRUBY_DIR%\idlc" "%VSCODE_SERVER_DIR%\idlc" >nul
    echo [OK]    Copied idlc to: %VSCODE_SERVER_DIR%\idlc
)

:: ── copy vendor folder ────────────────────────
if not exist "%JRUBY_DIR%\vendor" (
    echo [WARN]  vendor folder not found at: %JRUBY_DIR%\vendor -- skipping.
) else (
    echo [INFO]  Copying vendor to %VSCODE_SERVER_DIR%\vendor ...
    if exist "%VSCODE_SERVER_DIR%\vendor" rmdir /s /q "%VSCODE_SERVER_DIR%\vendor"
    xcopy /e /i /q "%JRUBY_DIR%\vendor" "%VSCODE_SERVER_DIR%\vendor" >nul
    echo [OK]    Copied vendor to: %VSCODE_SERVER_DIR%\vendor
)

echo.
echo ────────────────────────────────────────────
echo  Language server rebuilt successfully.
echo  Remember: only commit the new .jar file.
echo ────────────────────────────────────────────
exit /b 0

:: ── subroutine: run both maven commands ──────
:run_build
echo [INFO]  Running: mvn clean verify -DskipTests
call mvn clean verify -DskipTests
if errorlevel 1 exit /b 1
echo [INFO]  Running: mvn -DskipTests package
call mvn -DskipTests package
if errorlevel 1 exit /b 1
exit /b 0
