' Starts the Five Minute AI desktop app without a console window. Used by the shortcuts install.ps1 makes.
' Pass "--live" (the second shortcut) to let buttons really commit and start workflows.
Set sh = CreateObject("WScript.Shell")
Set fs = CreateObject("Scripting.FileSystemObject")
dir = fs.GetParentFolderName(WScript.ScriptFullName)
args = ""
If WScript.Arguments.Count > 0 Then args = " " & WScript.Arguments(0)
sh.Run "node """ & dir & "\app.mjs""" & args, 0, False
