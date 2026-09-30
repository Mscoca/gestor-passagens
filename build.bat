@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

echo === P.A.T.H. - geracao do executavel ===

rem 1. Cria o ambiente virtual (prefere Python 3.12; senao usa o Python 3 padrao)
if not exist ".venv\Scripts\python.exe" (
    py -3.12 -m venv .venv 2>nul || py -3 -m venv .venv || python -m venv .venv
    if errorlevel 1 (
        echo ERRO: nao foi possivel criar o ambiente virtual. Instale o Python 3.12.
        exit /b 1
    )
)
set "PY=.venv\Scripts\python.exe"

rem 2. Instala as dependencias e o PyInstaller
"%PY%" -m pip install --upgrade pip >nul
"%PY%" -m pip install -r requirements.txt pyinstaller
if errorlevel 1 (
    echo ERRO na instalacao das dependencias.
    exit /b 1
)

rem 3. Roda os testes e para se falharem
set "QT_QPA_PLATFORM=offscreen"
"%PY%" -m pytest -q
if errorlevel 1 (
    echo.
    echo ERRO: os testes falharam. O executavel NAO foi gerado.
    exit /b 1
)
set "QT_QPA_PLATFORM="

rem 4. Gera o executavel (onedir)
rem    pastas antigas marcadas como somente leitura impedem o PyInstaller de apaga-las (Acesso negado)
if exist "build" attrib -R "build\*" /S /D >nul
if exist "dist" attrib -R "dist\*" /S /D >nul
"%PY%" -m PyInstaller --noconfirm --clean GestorPassagens.spec
if errorlevel 1 (
    echo ERRO no PyInstaller.
    exit /b 1
)

rem 5. Monta o pacote do instalador (pasta + zip) para distribuir a equipe
set "PACOTE=dist\Instalador P.A.T.H"
if exist "%PACOTE%" rmdir /s /q "%PACOTE%"
mkdir "%PACOTE%"
robocopy "dist\GestorPassagens" "%PACOTE%\GestorPassagens" /MIR /NFL /NDL /NJH /NJS /NP >nul
copy /y "instalador\Instalar P.A.T.H.bat" "%PACOTE%\" >nul
copy /y "instalador\instalar.ps1" "%PACOTE%\" >nul
rem o antivirus costuma travar os arquivos recem-copiados por alguns segundos: tenta ate 5 vezes
set TENTATIVA=0
:zipar
set /a TENTATIVA+=1
ping -n 6 127.0.0.1 >nul
if exist "dist\Instalador P.A.T.H.zip" del /q "dist\Instalador P.A.T.H.zip"
tar -a -c -f "dist\Instalador P.A.T.H.zip" -C "%PACOTE%" "GestorPassagens" "Instalar P.A.T.H.bat" "instalar.ps1"
if errorlevel 1 if %TENTATIVA% LSS 5 goto zipar
if errorlevel 1 echo AVISO: nao foi possivel gerar o .zip; use a pasta "%PACOTE%".

echo.
echo Pronto!
echo   Pacote para a equipe: dist\Instalador P.A.T.H.zip
echo   (cada analista descompacta e da dois cliques em "Instalar P.A.T.H.bat")
echo.
choice /C SN /M "Instalar o P.A.T.H. neste computador agora"
if errorlevel 2 goto fim
call "%PACOTE%\Instalar P.A.T.H.bat"
:fim
endlocal
