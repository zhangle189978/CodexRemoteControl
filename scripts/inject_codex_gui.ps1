param(
    [Parameter(Position = 0)]
    [string]$Text = "",

    [string]$WindowTitlePattern = "Codex",

    [switch]$NoSubmit,

    [switch]$ListWindows,

    [switch]$FocusOnly,

    [int]$ClickOffsetFromBottom = 80,

    [int]$ClickOffsetFromLeft = 0,

    [switch]$RestoreClipboard,

    [ValidateSet("SendKeys", "SendKey", "Unicode", "Clipboard")]
    [string]$InputMode = "SendKeys",

    [ValidateSet("Enter", "CtrlEnter", "ClickButton", "None")]
    [string]$SubmitKey = "ClickButton",

    [int]$SendButtonOffsetFromRight = 190,

    [int]$SendButtonOffsetFromBottom = 68
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Add-Type -AssemblyName System.Windows.Forms

if (-not ("CodexRemoteControlGui.NativeWindowV4" -as [type])) {
    Add-Type -TypeDefinition @"
namespace CodexRemoteControlGui {
    using System;
    using System.Runtime.InteropServices;

    public static class NativeWindowV4 {
        [DllImport("user32.dll")]
        public static extern bool SetForegroundWindow(IntPtr hWnd);

        [DllImport("user32.dll")]
        public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);

        [DllImport("user32.dll")]
        public static extern IntPtr GetForegroundWindow();

        [DllImport("user32.dll")]
        public static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint processId);

        [DllImport("user32.dll")]
        public static extern bool GetWindowRect(IntPtr hWnd, out RectV4 lpRect);

        [DllImport("user32.dll")]
        public static extern bool SetCursorPos(int X, int Y);

        [DllImport("user32.dll")]
        public static extern void mouse_event(uint dwFlags, uint dx, uint dy, uint dwData, UIntPtr dwExtraInfo);

        [DllImport("user32.dll", SetLastError = true)]
        public static extern uint SendInput(uint nInputs, InputV4[] pInputs, int cbSize);
    }

    public struct RectV4 {
        public int Left;
        public int Top;
        public int Right;
        public int Bottom;
    }

    [StructLayout(LayoutKind.Sequential)]
    public struct InputV4 {
        public uint type;
        public InputUnionV4 U;
    }

    [StructLayout(LayoutKind.Explicit)]
    public struct InputUnionV4 {
        [FieldOffset(0)]
        public KeybdInputV4 ki;
    }

    [StructLayout(LayoutKind.Sequential)]
    public struct KeybdInputV4 {
        public ushort wVk;
        public ushort wScan;
        public uint dwFlags;
        public uint time;
        public IntPtr dwExtraInfo;
    }
}
"@
}

function Send-UnicodeText {
    param([string]$Value)

    foreach ($character in $Value.ToCharArray()) {
        $scanCode = [uint16][char]$character
        $down = New-Object CodexRemoteControlGui.InputV4
        $down.type = 1
        $down.U.ki.wVk = 0
        $down.U.ki.wScan = $scanCode
        $down.U.ki.dwFlags = 0x0004
        $down.U.ki.time = 0
        $down.U.ki.dwExtraInfo = [IntPtr]::Zero

        $up = New-Object CodexRemoteControlGui.InputV4
        $up.type = 1
        $up.U.ki.wVk = 0
        $up.U.ki.wScan = $scanCode
        $up.U.ki.dwFlags = 0x0004 -bor 0x0002
        $up.U.ki.time = 0
        $up.U.ki.dwExtraInfo = [IntPtr]::Zero

        [CodexRemoteControlGui.NativeWindowV4]::SendInput(
            2,
            [CodexRemoteControlGui.InputV4[]]@($down, $up),
            [System.Runtime.InteropServices.Marshal]::SizeOf([type][CodexRemoteControlGui.InputV4])
        ) | Out-Null
        Start-Sleep -Milliseconds 5
    }
}

function Get-CandidateWindow {
    param([string]$Pattern)

    Get-Process |
        Where-Object { $_.MainWindowHandle -ne 0 -and $_.MainWindowTitle -match $Pattern } |
        Sort-Object @{ Expression = { $_.ProcessName -ne "Codex" } }, Id |
        Select-Object -First 1
}

if ($ListWindows) {
    Get-Process |
        Where-Object { $_.MainWindowHandle -ne 0 } |
        Select-Object Id, ProcessName, MainWindowHandle, MainWindowTitle |
        Sort-Object ProcessName, Id |
        Format-Table -AutoSize
    exit 0
}

if ([string]::IsNullOrWhiteSpace($Text)) {
    throw "Text is required unless -ListWindows is used."
}

$window = Get-CandidateWindow -Pattern $WindowTitlePattern
if ($null -eq $window) {
    throw "No window matched title pattern '$WindowTitlePattern'. Run with -ListWindows to inspect candidates."
}

$handle = [IntPtr]$window.MainWindowHandle
[CodexRemoteControlGui.NativeWindowV4]::ShowWindow($handle, 5) | Out-Null
$activated = [CodexRemoteControlGui.NativeWindowV4]::SetForegroundWindow($handle)
if (-not $activated) {
    $shell = New-Object -ComObject WScript.Shell
    $shell.AppActivate([int]$window.Id) | Out-Null
}
Start-Sleep -Milliseconds 800

$foreground = [CodexRemoteControlGui.NativeWindowV4]::GetForegroundWindow()
[uint32]$foregroundProcessId = 0
[CodexRemoteControlGui.NativeWindowV4]::GetWindowThreadProcessId(
    $foreground,
    [ref]$foregroundProcessId
) | Out-Null
if ([int]$foregroundProcessId -ne [int]$window.Id) {
    throw "Codex window was found, but Windows did not make it foreground. Foreground pid is $foregroundProcessId."
}

$rect = New-Object CodexRemoteControlGui.RectV4
if ([CodexRemoteControlGui.NativeWindowV4]::GetWindowRect($handle, [ref]$rect)) {
    if ($ClickOffsetFromLeft -gt 0) {
        $x = [int]($rect.Left + $ClickOffsetFromLeft)
    }
    else {
        $x = [int](($rect.Left + $rect.Right) / 2)
    }
    $y = [int]($rect.Bottom - $ClickOffsetFromBottom)
    [CodexRemoteControlGui.NativeWindowV4]::SetCursorPos($x, $y) | Out-Null
    Start-Sleep -Milliseconds 100
    [CodexRemoteControlGui.NativeWindowV4]::mouse_event(0x0002, 0, 0, 0, [UIntPtr]::Zero)
    Start-Sleep -Milliseconds 50
    [CodexRemoteControlGui.NativeWindowV4]::mouse_event(0x0004, 0, 0, 0, [UIntPtr]::Zero)
    Start-Sleep -Milliseconds 200
}

if ($FocusOnly) {
    Write-Output "Codex GUI focused via window $($window.Id): $($window.MainWindowTitle)"
    exit 0
}

$previousClipboardData = $null
try {
    if ($RestoreClipboard) {
        $previousClipboardData = [System.Windows.Forms.Clipboard]::GetDataObject()
    }

    if ($InputMode -eq "Clipboard") {
        [System.Windows.Forms.Clipboard]::Clear()
        Start-Sleep -Milliseconds 100
        [System.Windows.Forms.Clipboard]::SetText(
            $Text,
            [System.Windows.Forms.TextDataFormat]::UnicodeText
        )
        if (-not [System.Windows.Forms.Clipboard]::ContainsText()) {
            throw "Failed to put text on the clipboard."
        }
        Start-Sleep -Milliseconds 100
        [System.Windows.Forms.SendKeys]::SendWait("^v")
    }
    elseif ($InputMode -eq "Unicode") {
        Send-UnicodeText -Value $Text
    }
    else {
        [System.Windows.Forms.SendKeys]::SendWait($Text)
    }
    Start-Sleep -Milliseconds 100

    if (-not $NoSubmit -and $SubmitKey -ne "None") {
        if ($SubmitKey -eq "CtrlEnter") {
            [System.Windows.Forms.SendKeys]::SendWait("^{ENTER}")
        }
        elseif ($SubmitKey -eq "ClickButton") {
            $sendRect = New-Object CodexRemoteControlGui.RectV4
            if (-not [CodexRemoteControlGui.NativeWindowV4]::GetWindowRect($handle, [ref]$sendRect)) {
                throw "Failed to read Codex window rectangle for send button click."
            }
            $sendX = [int]($sendRect.Right - $SendButtonOffsetFromRight)
            $sendY = [int]($sendRect.Bottom - $SendButtonOffsetFromBottom)
            [CodexRemoteControlGui.NativeWindowV4]::SetCursorPos($sendX, $sendY) | Out-Null
            Start-Sleep -Milliseconds 100
            [CodexRemoteControlGui.NativeWindowV4]::mouse_event(0x0002, 0, 0, 0, [UIntPtr]::Zero)
            Start-Sleep -Milliseconds 50
            [CodexRemoteControlGui.NativeWindowV4]::mouse_event(0x0004, 0, 0, 0, [UIntPtr]::Zero)
        }
        else {
            [System.Windows.Forms.SendKeys]::SendWait("{ENTER}")
        }
    }
}
finally {
    Start-Sleep -Milliseconds 1000
    if ($RestoreClipboard -and $null -ne $previousClipboardData) {
        [System.Windows.Forms.Clipboard]::SetDataObject($previousClipboardData, $true)
    }
}

$mode = if ($NoSubmit) { "pasted" } else { "submitted" }
Write-Output "Codex GUI $mode text via window $($window.Id): $($window.MainWindowTitle)"
