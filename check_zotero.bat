@echo off
chcp 65001 > nul
setlocal EnableDelayedExpansion

echo.
echo ========================================
echo   Zotero 环境检查工具
echo   ResearchAgent Project
echo ========================================
echo.

REM 检查 1: Zotero 端口 23119
echo [1/4] 检查 Zotero 本地 API 端口 (23119)
echo ----------------------------------------
netstat -ano -p tcp | findstr :23119 > nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo [✓] Zotero 端口 23119 正在监听
    netstat -ano -p tcp | findstr :23119
) else (
    echo [✗] Zotero 端口 23119 未监听
    echo     请确保 Zotero Desktop 已启动
)
echo.

REM 检查 2: Zotero API 响应
echo [2/4] 测试 Zotero API 连通性
echo ----------------------------------------
curl.exe -s -o nul -w "HTTP 状态码: %%{http_code}\n" --max-time 5 "http://127.0.0.1:23119/api/users/0/items?limit=1" 2>nul
if %ERRORLEVEL% EQU 0 (
    echo [✓] Zotero API 响应正常
) else (
    echo [✗] Zotero API 无法访问
    echo     建议: 检查 Zotero 是否启用本地 API
)
echo.

REM 检查 3: zotero-mcp 可执行文件
echo [3/4] 检查 zotero-mcp 可执行文件
echo ----------------------------------------
set ZOTERO_MCP_PATH=D:\Hcworkspace\Anoconda3\envs\research_agent\Scripts\zotero-mcp.exe
if exist "%ZOTERO_MCP_PATH%" (
    echo [✓] zotero-mcp.exe 存在
    echo     路径: %ZOTERO_MCP_PATH%
    echo     版本信息:
    "%ZOTERO_MCP_PATH%" version 2>nul
    if %ERRORLEVEL% NEQ 0 (
        echo     [提示] version 命令失败，但文件存在
    )
) else (
    echo [✗] zotero-mcp.exe 不存在
    echo     路径: %ZOTERO_MCP_PATH%
    echo     建议: 检查 third_party/zotero-mcp 是否安装
)
echo.

REM 检查 4: zotero-cli 可执行文件
echo [4/4] 检查 zotero-cli 可执行文件
echo ----------------------------------------
set ZOTERO_CLI_PATH=D:\Hcworkspace\Anoconda3\envs\research_agent\Scripts\zotero-cli.exe
if exist "%ZOTERO_CLI_PATH%" (
    echo [✓] zotero-cli.exe 存在
    echo     路径: %ZOTERO_CLI_PATH%
    echo     测试获取 collections:
    "%ZOTERO_CLI_PATH%" get collections --limit 3 2>nul
    if %ERRORLEVEL% EQU 0 (
        echo [✓] zotero-cli 工作正常
    ) else (
        echo [!] zotero-cli 调用失败，可能需要配置认证
    )
) else (
    echo [✗] zotero-cli.exe 不存在
    echo     路径: %ZOTERO_CLI_PATH%
    echo     建议: 安装 zotero-cli 工具
)
echo.

REM 总结
echo ========================================
echo   检查完成
echo ========================================
echo.
echo 如果所有检查项都显示 [✓]，说明 Zotero 环境配置正确。
echo 如果有 [✗] 或 [!]，请按照上方提示进行修复。
echo.
echo 相关文档: docs/DEVELOPMENT_ISSUES.md
echo.

pause
