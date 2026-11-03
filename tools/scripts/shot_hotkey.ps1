<#
shot_hotkey.ps1 -- press F9 in-game to capture, F10 to quit.

Why this exists
---------------
`shot.ps1` runs once and exits, so using it means alt-tabbing out of the game,
starting a countdown, and alt-tabbing back -- per shot.  For a batch of a dozen
level screenshots that is miserable, and half of them end up showing the pause
menu because you pressed Esc on the way out.

This one sits in the background and polls the keyboard with GetAsyncKeyState,
which reads the *global* key state, so it works while the game has focus and
even in exclusive fullscreen.  Press F9 and it grabs the current frame.

    F9   capture
    F10  quit

Capture method
--------------
CopyFromScreen over the window's client rect.  PrintWindow is tried first but
this game answers it with a black frame (verified), so the fallback is the path
that actually runs.  Consequence: the game window must be the one on top.  It
will be, because you are playing it.

Usage
-----
    powershell -ExecutionPolicy Bypass -File tools/scripts/shot_hotkey.ps1
    powershell -ExecutionPolicy Bypass -File tools/scripts/shot_hotkey.ps1 -Tag L3
    powershell -ExecutionPolicy Bypass -File tools/scripts/shot_hotkey.ps1 -Test   # one shot, exit

Files land in art/scene_shots/ as <tag>_<timestamp>_<n>.png
#>
param(
    [string]$Proc = "ggc",
    [string]$Tag = "ggc",
    [int]$CaptureVk = 0x78,   # F9
    [int]$StopVk = 0x79,      # F10
    [switch]$Test
)

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Drawing
Add-Type -AssemblyName System.Windows.Forms

Add-Type @"
using System;
using System.Runtime.InteropServices;
public class Shot {
    [StructLayout(LayoutKind.Sequential)]
    public struct RECT { public int Left, Top, Right, Bottom; }
    [StructLayout(LayoutKind.Sequential)]
    public struct POINT { public int X, Y; }
    [DllImport("user32.dll")] public static extern bool SetProcessDPIAware();
    [DllImport("user32.dll")] public static extern short GetAsyncKeyState(int vk);
    [DllImport("user32.dll")] public static extern bool GetClientRect(IntPtr h, out RECT r);
    [DllImport("user32.dll")] public static extern bool ClientToScreen(IntPtr h, ref POINT p);
    [DllImport("dwmapi.dll")] public static extern int DwmGetWindowAttribute(IntPtr h, int attr, out RECT r, int size);
}
"@

[void][Shot]::SetProcessDPIAware()

$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$dir = Join-Path $root "art\scene_shots"
if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }

$script:n = 0

function Grab {
    # Resolve the window fresh every time: the player may restart the game
    # between shots, and a cached handle would then point at a dead window.
    $w = Get-Process -Name $Proc -ErrorAction SilentlyContinue |
         Where-Object { $_.MainWindowHandle -ne 0 } |
         Select-Object -First 1

    $bmp = $null
    $note = ""
    if ($w) {
        # The capture rect has to come from DWM, not GetClientRect.
        #
        # At 125% display scaling GetClientRect answered "1700 x 960" for a game
        # window whose rendered content is 1360 x 768 -- 1700/1360 is exactly
        # 1.25, i.e. the client rect came back in a different DPI space than the
        # pixels CopyFromScreen actually reads.  The result was a screenshot with
        # the game in the top-left and a chunk of the desktop down the right side.
        #
        # DWMWA_EXTENDED_FRAME_BOUNDS (9) reports the composited window rectangle
        # in physical screen pixels, which is the same space CopyFromScreen uses,
        # so the two finally agree.
        $fr = New-Object Shot+RECT
        $hr = [Shot]::DwmGetWindowAttribute($w.MainWindowHandle, 9, [ref]$fr, 16)
        $rx = 0; $ry = 0; $rw = 0; $rh = 0
        if ($hr -eq 0 -and ($fr.Right - $fr.Left) -gt 8) {
            $rx = $fr.Left; $ry = $fr.Top
            $rw = $fr.Right - $fr.Left
            $rh = $fr.Bottom - $fr.Top
            $src = "dwm"
        } else {
            $cr = New-Object Shot+RECT
            [void][Shot]::GetClientRect($w.MainWindowHandle, [ref]$cr)
            $pt = New-Object Shot+POINT
            $pt.X = 0; $pt.Y = 0
            [void][Shot]::ClientToScreen($w.MainWindowHandle, [ref]$pt)
            $rx = $pt.X; $ry = $pt.Y
            $rw = $cr.Right - $cr.Left
            $rh = $cr.Bottom - $cr.Top
            $src = "client"
        }
        if ($rw -ge 8 -and $rh -ge 8) {
            $bmp = New-Object System.Drawing.Bitmap $rw, $rh
            $g = [System.Drawing.Graphics]::FromImage($bmp)
            $g.CopyFromScreen($rx, $ry, 0, 0, (New-Object System.Drawing.Size $rw, $rh))
            $g.Dispose()
            $note = "$rw x $rh ($src)"
        }
    }
    if (-not $bmp) {
        $b = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
        $bmp = New-Object System.Drawing.Bitmap $b.Width, $b.Height
        $g = [System.Drawing.Graphics]::FromImage($bmp)
        $g.CopyFromScreen($b.X, $b.Y, 0, 0, (New-Object System.Drawing.Size $b.Width, $b.Height))
        $g.Dispose()
        $note = "full screen $($b.Width) x $($b.Height)  (game window not found)"
    }

    $script:n++
    $stamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $p = Join-Path $dir ("{0}_{1}_{2:D2}.png" -f $Tag, $stamp, $script:n)
    $bmp.Save($p, [System.Drawing.Imaging.ImageFormat]::Png)
    $bmp.Dispose()
    Write-Host ("[{0}] {1}   {2}" -f $script:n, $note, (Split-Path -Leaf $p))
    return $p
}

if ($Test) {
    Write-Host "test capture..."
    [void](Grab)
    return
}

Write-Host "ready -- press F9 to capture, F10 to quit"
Write-Host "files -> $dir"
Write-Host ""

# A 50 ms poll is responsive enough to catch a deliberate keypress and cheap
# enough to leave the game alone.  350 ms of dead time after a shot stops one
# press from firing three captures.
while ($true) {
    if (([Shot]::GetAsyncKeyState($StopVk)) -band 0x8000) {
        Write-Host "`nstopped, $($script:n) shot(s) taken"
        break
    }
    if (([Shot]::GetAsyncKeyState($CaptureVk)) -band 0x8000) {
        [void](Grab)
        Start-Sleep -Milliseconds 350
    }
    Start-Sleep -Milliseconds 50
}
