# Instala (ou atualiza) o P.A.T.H. no computador do analista, sem precisar de administrador.
# - copia o programa para %LOCALAPPDATA%\Programs\PATH
# - cria atalhos na Área de Trabalho e no Menu Iniciar
# - abre o programa
param(
    [string]$Destino = "$env:LOCALAPPDATA\Programs\PATH",
    [switch]$SemAtalhos,
    [switch]$NaoAbrir
)
$ErrorActionPreference = "Stop"

function Falhar($msg) {
    Write-Host ""
    Write-Host "ERRO: $msg" -ForegroundColor Red
    Write-Host ""
    exit 1
}

# Procura a pasta do programa: ao lado deste script (pacote) ou em ..\dist (projeto)
$candidatos = @(
    (Join-Path $PSScriptRoot "GestorPassagens"),
    (Join-Path $PSScriptRoot "..\dist\GestorPassagens")
)
$origem = $candidatos | Where-Object { Test-Path (Join-Path $_ "GestorPassagens.exe") } | Select-Object -First 1
if (-not $origem) { Falhar "Não encontrei a pasta GestorPassagens com o GestorPassagens.exe ao lado do instalador." }
$origem = (Resolve-Path $origem).Path

Write-Host "Instalando o P.A.T.H. em $Destino ..."

# Fecha o programa se estiver aberto (os dados já ficam salvos a cada ação)
$aberto = Get-Process -Name "GestorPassagens" -ErrorAction SilentlyContinue |
    Where-Object { $_.Path -and $_.Path.StartsWith($Destino, [StringComparison]::OrdinalIgnoreCase) }
if ($aberto) {
    Write-Host "Fechando o P.A.T.H. aberto para atualizar..."
    $aberto | Stop-Process -Force
    Start-Sleep -Seconds 2
}

# Copia espelhando a pasta (remove arquivos de versões antigas)
New-Item -ItemType Directory -Force -Path $Destino | Out-Null
& robocopy $origem $Destino /MIR /R:3 /W:2 /NFL /NDL /NJH /NJS /NP | Out-Null
if ($LASTEXITCODE -ge 8) { Falhar "Falha ao copiar os arquivos (robocopy código $LASTEXITCODE)." }

$exe = Join-Path $Destino "GestorPassagens.exe"
if (-not (Test-Path $exe)) { Falhar "A cópia terminou, mas o GestorPassagens.exe não está em $Destino." }

if (-not $SemAtalhos) {
    $shell = New-Object -ComObject WScript.Shell
    $locais = @([Environment]::GetFolderPath("Desktop"), [Environment]::GetFolderPath("Programs"))
    foreach ($pasta in $locais) {
        $atalho = $shell.CreateShortcut((Join-Path $pasta "P.A.T.H.lnk"))
        $atalho.TargetPath = $exe
        $atalho.WorkingDirectory = $Destino
        $atalho.IconLocation = "$exe,0"
        $atalho.Description = "P.A.T.H. - Passagens Aéreas, Terrestres e Hospedagens"
        $atalho.Save()
    }
    Write-Host "Atalhos criados na Área de Trabalho e no Menu Iniciar."
}

Write-Host ""
Write-Host "P.A.T.H. instalado com sucesso." -ForegroundColor Green
if (-not $NaoAbrir) { Start-Process -FilePath $exe -WorkingDirectory $Destino }
exit 0
