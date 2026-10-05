<#
  Corrige janelas que abrem ATRAS da ultima janela ativa (Windows 10/11).

  Causas tratadas:
   1. ForegroundLockTimeout alterado (por programa/"otimizador") -> Windows bloqueia
      a nova janela de vir para frente e so pisca o icone na barra de tarefas.
   2. "Ativar janela ao passar o mouse" (ActiveWindowTracking / X-Mouse) ligado.
   3. Algum processo em segundo plano roubando o foco (use -Monitorar para descobrir).

  Uso (PowerShell, NAO precisa ser administrador):
    powershell -ExecutionPolicy Bypass -File .\corrigir-foco-janelas.ps1             # diagnostica e corrige
    powershell -ExecutionPolicy Bypass -File .\corrigir-foco-janelas.ps1 -Monitorar  # registra quem pega o foco
#>
param(
  [switch]$Monitorar,
  [int]$Segundos = 120
)

Add-Type @"
using System;
using System.Runtime.InteropServices;
using System.Text;
public static class W32 {
  [DllImport("user32.dll", SetLastError=true)]
  public static extern bool SystemParametersInfo(uint a, uint b, IntPtr c, uint d);
  [DllImport("user32.dll", SetLastError=true)]
  public static extern bool SystemParametersInfo(uint a, uint b, ref uint c, uint d);
  [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
  [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
  [DllImport("user32.dll", CharSet=CharSet.Unicode)]
  public static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
}
"@

$SPI_GETACTIVEWINDOWTRACKING   = 0x1000
$SPI_SETACTIVEWINDOWTRACKING   = 0x1001
$SPI_GETFOREGROUNDLOCKTIMEOUT  = 0x2000
$SPI_SETFOREGROUNDLOCKTIMEOUT  = 0x2001
$SPI_SETFOREGROUNDFLASHCOUNT   = 0x2005
$SPIF_UPDATE_AND_SEND          = 0x3
$PADRAO_LOCK = 200000   # valor padrao do Windows (200 s)
$PADRAO_FLASH = 7

if ($Monitorar) {
  $log = Join-Path $env:USERPROFILE "Desktop\foco-janelas.log"
  "Monitorando por $Segundos s. Abra suas janelas normalmente. Log: $log"
  $ultimo = [IntPtr]::Zero
  $fim = (Get-Date).AddSeconds($Segundos)
  while ((Get-Date) -lt $fim) {
    $h = [W32]::GetForegroundWindow()
    if ($h -ne $ultimo) {
      $ultimo = $h
      $procId = 0; [void][W32]::GetWindowThreadProcessId($h, [ref]$procId)
      $sb = New-Object System.Text.StringBuilder 256
      [void][W32]::GetWindowText($h, $sb, 256)
      $p = Get-Process -Id $procId -ErrorAction SilentlyContinue
      $linha = "{0:HH:mm:ss.fff}  {1,-28} PID {2,-6} '{3}'" -f (Get-Date), $p.ProcessName, $procId, $sb
      $linha; Add-Content -Path $log -Value $linha
    }
    Start-Sleep -Milliseconds 100
  }
  "`nProcure no log um processo que aparece LOGO DEPOIS da janela que voce abriu"
  "(ou que aparece repetidamente sem titulo). Esse e o ladrao de foco."
  return
}

# ---------- Diagnostico ----------
$reg = Get-ItemProperty "HKCU:\Control Panel\Desktop"
[uint32]$lock = 0; [void][W32]::SystemParametersInfo($SPI_GETFOREGROUNDLOCKTIMEOUT, 0, [ref]$lock, 0)
[uint32]$track = 0; [void][W32]::SystemParametersInfo($SPI_GETACTIVEWINDOWTRACKING, 0, [ref]$track, 0)

"=== Diagnostico ==="
"ForegroundLockTimeout (sessao) : $lock   (padrao $PADRAO_LOCK)"
"ForegroundLockTimeout (registro): $($reg.ForegroundLockTimeout)"
"ForegroundFlashCount (registro) : $($reg.ForegroundFlashCount)   (padrao $PADRAO_FLASH)"
"Ativar janela ao passar o mouse : $([bool]$track)   (padrao False)"

# ---------- Correcao ----------
"`n=== Corrigindo ==="
[void][W32]::SystemParametersInfo($SPI_SETFOREGROUNDLOCKTIMEOUT, 0, [IntPtr]$PADRAO_LOCK, $SPIF_UPDATE_AND_SEND)
[void][W32]::SystemParametersInfo($SPI_SETFOREGROUNDFLASHCOUNT, 0, [IntPtr]$PADRAO_FLASH, $SPIF_UPDATE_AND_SEND)
[void][W32]::SystemParametersInfo($SPI_SETACTIVEWINDOWTRACKING, 0, [IntPtr]::Zero, $SPIF_UPDATE_AND_SEND)
Set-ItemProperty "HKCU:\Control Panel\Desktop" -Name ForegroundLockTimeout -Value $PADRAO_LOCK -Type DWord
Set-ItemProperty "HKCU:\Control Panel\Desktop" -Name ForegroundFlashCount  -Value $PADRAO_FLASH -Type DWord
"Valores restaurados ao padrao do Windows (vale na hora e apos reiniciar)."
"`nSe o problema continuar, rode com -Monitorar para identificar o programa que rouba o foco."
