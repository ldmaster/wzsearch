@echo off
setlocal
if "%~1"=="" (
    echo.
    echo  Arraste e solte aqui o arquivo do WhatsApp exportado ^(.zip ou .txt^).
    echo.
    pause
    exit /b 1
)
echo.
echo  Gerando a lista de fotos...
"%~dp0wzsearch.exe" "%~1" --photos --csv "%~dp1%~n1_fotos.csv"
echo.
echo  Pronto! O arquivo "%~n1_fotos.csv" foi criado na mesma pasta do export.
echo  Abra ele no Excel ou Google Sheets.
echo.
pause
