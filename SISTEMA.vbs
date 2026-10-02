' Abre o Sistema Financeiro e NFS-e SEM janela preta. O robo agendado tambem roda escondido.
'   SISTEMA.vbs        -> abre o sistema no navegador (se ja estiver aberto, so abre o navegador)
'   SISTEMA.vbs robo   -> roda o robo financeiro (usado pelo Agendador do Windows)
' Para fechar o sistema: botao "Encerrar o sistema" no menu da tela.
Option Explicit
Dim sh, fso, pasta, modo
Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
pasta = fso.GetParentFolderName(WScript.ScriptFullName)
sh.CurrentDirectory = pasta
modo = ""
If WScript.Arguments.Count > 0 Then modo = LCase(WScript.Arguments(0))
If modo = "robo" Then
  sh.Run "cmd /c ROBO.bat", 0, False
ElseIf Not fso.FileExists(pasta & "\.env") Then
  ' primeira vez: a configuracao precisa da janela para perguntar os dados da empresa
  sh.Run "cmd /c INICIAR.bat", 1, False
Else
  sh.Run "cmd /c INICIAR.bat oculto", 0, False
End If
