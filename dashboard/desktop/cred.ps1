# Reads one generic credential from Windows Credential Manager and writes it as JSON {"user":..,"secret":..} to
# stdout, for desktop/secrets.mjs only (it keeps the value in memory). Exit code 2 if there is no such credential.
# Add credentials with:  cmdkey /generic:FiveMinuteAI/zoho /user:hello@fiveminuteai.net /pass
# (cmdkey then asks for the password; it never appears on screen or in a file).
param([Parameter(Mandatory = $true)][ValidatePattern('^FiveMinuteAI/[a-z0-9-]+$')][string]$Target)
$ErrorActionPreference = "Stop"
Add-Type -Namespace FMA -Name Cred -MemberDefinition @'
[System.Runtime.InteropServices.StructLayout(System.Runtime.InteropServices.LayoutKind.Sequential, CharSet = System.Runtime.InteropServices.CharSet.Unicode)]
public struct CREDENTIAL {
  public int Flags; public int Type; public string TargetName; public string Comment;
  public System.Runtime.InteropServices.ComTypes.FILETIME LastWritten;
  public int CredentialBlobSize; public System.IntPtr CredentialBlob; public int Persist;
  public int AttributeCount; public System.IntPtr Attributes; public string TargetAlias; public string UserName;
}
[System.Runtime.InteropServices.DllImport("advapi32.dll", CharSet = System.Runtime.InteropServices.CharSet.Unicode, SetLastError = true)]
public static extern bool CredRead(string target, int type, int flags, out System.IntPtr credential);
[System.Runtime.InteropServices.DllImport("advapi32.dll")]
public static extern void CredFree(System.IntPtr buffer);
'@
$ptr = [IntPtr]::Zero
if (-not [FMA.Cred]::CredRead($Target, 1, 0, [ref]$ptr)) { exit 2 }   # 1 = CRED_TYPE_GENERIC
try {
    $c = [System.Runtime.InteropServices.Marshal]::PtrToStructure($ptr, [type][FMA.Cred+CREDENTIAL])
    $secret = if ($c.CredentialBlobSize -gt 0) {
        [System.Runtime.InteropServices.Marshal]::PtrToStringUni($c.CredentialBlob, [int]($c.CredentialBlobSize / 2))
    } else { "" }
    [Console]::Out.Write((@{ user = $c.UserName; secret = $secret } | ConvertTo-Json -Compress))
} finally { [FMA.Cred]::CredFree($ptr) }
