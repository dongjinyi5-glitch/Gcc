<#
shot.ps1 -- capture the Guns, Gore and Cannoli window to a PNG.

Why a script instead of the PrtScn key
--------------------------------------
GGC is a Unity 4.3 standalone player.  In *exclusive* fullscreen the front
buffer is owned by the swap chain, so a plain GDI screen grab can come back
black, and Unity has no built-in screenshot hotkey.  This script:

  1. finds the window by title (partial match, so it survives a rename),
  2. restores it if minimised and raises it,
  3. captures the *client area* with PrintWindow(PW_RENDERFULLCONTENT), which
     asks the app to redraw itself into our DC -- this works even when the
     window is partly covered by something else,
  4. if that comes back black (which happens on some exclusive-fullscreen
     setups), falls back to a straight CopyFromScreen of the same rectangle.

The client area is captured, not the desktop, so the result is exactly the
game's render size -- that is what makes it comparable, pixel for pixel, with
the composited panoramas in art/scene_sheets/.

Usage
-----
    # from the project root; 5 s countdown so you can alt-tab back in
    powershell -ExecutionPolicy Bypass -File tools/scripts/shot.ps1

    # no countdown, explicit destination, whole screen instead of the window
    powershell -ExecutionPolicy Bypass -File tools/scripts/shot.ps1 -Delay 0 -FullScreen -Out art/scene_shots/x.png

    # the window title differs?  pass a fragment of it
    powershell -ExecutionPolicy Bypass -File tools/scripts/shot.ps1 -Title "Cannoli"

ASCII only on purpose: PowerShell 5.1 reads a BOM-less script as ANSI, and a
non-ASCII literal here would be mangled into a broken path.
#>
param(
    [string]$Proc = "ggc",
    [string]$Title = "Guns",
    [int]$Delay = 5,
    [string]$Out = "",
    [switch]$FullScreen
)

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Drawing
Add-Type -AssemblyName System.Windows.Forms

Add-Type @"
using System;
using System.Runtime.InteropServices;

public class Win {
    [StructLayout(LayoutKind.Sequential)]
    public struct RECT { public int Left, Top, Right, Bottom; }
    [StructLayout(LayoutKind.Sequential)]
    public struct POINT { public int X, Y; }

    [DllImport("user32.dll")] public static extern bool SetProcessDPIAware();
    [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
    [DllImport("user32.dll")] public static extern bool GetClientRect(IntPtr h, out RECT r);
    [DllImport("user32.dll")] public static extern bool ClientToScreen(IntPtr h, ref POINT p);
    [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr h, IntPtr hdc, uint flags);
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
    [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int cmd);
    [DllImport("user32.dll")] public static extern bool IsIconic(IntPtr h);
}
"@

# Physical pixels, not DPI-virtualised ones -- otherwise a 150% display scale
# gives a 1280x720 grab of a 1920x1080 game and the comparison is worthless.
[void][Win]::SetProcessDPIAware()

function Get-ClientBox([IntPtr]$h) {
    $cr = New-Object Win+RECT
    [void][Win]::GetClientRect($h, [ref]$cr)
    $p = New-Object Win+POINT
    $p.X = 0; $p.Y = 0
    [void][Win]::ClientToScreen($h, [ref]$p)
    return [pscustomobject]@{
        X = $p.X
        Y = $p.Y
        W = $cr.Right - $cr.Left
        H = $cr.Bottom - $cr.Top
    }
}

function Test-Black([System.Drawing.Bitmap]$bmp) {
    # Sample a sparse grid.  A real frame has highlights somewhere; a failed
    # exclusive-fullscreen grab is uniformly 0,0,0.
    $max = 0
    $stepX = [Math]::Max(1, [int]($bmp.Width / 40))
    $stepY = [Math]::Max(1, [int]($bmp.Height / 24))
    for ($y = 0; $y -lt $bmp.Height; $y += $stepY) {
        for ($x = 0; $x -lt $bmp.Width; $x += $stepX) {
            $c = $bmp.GetPixel($x, $y)
            $v = [Math]::Max($c.R, [Math]::Max($c.G, $c.B))
            if ($v -gt $max) { $max = $v }
            if ($max -gt 12) { return $false }
        }
    }
    return $true
}

# ---- locate the window -----------------------------------------------------
# Match by *process name* first.  Title matching is a trap here: AssetStudio
# opens the game's files and titles its window "... Guns Gore and Cannoli -
# 4.3.4f1 - StandaloneWindows", so '*Guns*' happily grabs the wrong window.
# NOTE: PowerShell variable names are case-INsensitive, so a local `$proc`
# silently overwrites the parameter `$Proc`.  That cost a debugging round --
# the fallback branch then printed "no process named ''".  Keep them distinct.
$win = $null
$hwnd = [IntPtr]::Zero
if (-not $FullScreen) {
    if ($Proc) {
        $win = Get-Process -Name $Proc -ErrorAction SilentlyContinue |
               Where-Object { $_.MainWindowHandle -ne 0 } |
               Select-Object -First 1
    }
    if (-not $win -and $Title) {
        Write-Host ("no live window for process '{0}' -- falling back to title match" -f $Proc)
        $win = Get-Process |
               Where-Object { $_.MainWindowHandle -ne 0 -and $_.MainWindowTitle -like "*$Title*" } |
               Select-Object -First 1
    }
    if ($win) {
        $hwnd = $win.MainWindowHandle
        Write-Host ("window : [{0}] '{1}'  pid {2}  hwnd {3}" -f $win.ProcessName, $win.MainWindowTitle, $win.Id, $hwnd)
        if ([Win]::IsIconic($hwnd)) { [void][Win]::ShowWindow($hwnd, 9) }   # SW_RESTORE
        [void][Win]::ShowWindow($hwnd, 5)                                    # SW_SHOW
        [void][Win]::SetForegroundWindow($hwnd)
    } else {
        Write-Host ("no window for process '{0}' or title '*{1}*' -- capturing the whole screen instead" -f $Proc, $Title)
        Write-Host "(is the game running?  windows seen:)"
        Get-Process | Where-Object { $_.MainWindowHandle -ne 0 } |
            Select-Object -First 12 ProcessName, MainWindowTitle | Format-Table -AutoSize | Out-String | Write-Host
    }
}

if ($Delay -gt 0) {
    Write-Host ("capture in {0} s -- switch to the game now" -f $Delay)
    for ($i = $Delay; $i -ge 1; $i--) {
        Write-Host ("  {0}" -f $i)
        Start-Sleep -Seconds 1
    }
}

# ---- capture ---------------------------------------------------------------
$bmp = $null
$mode = ""
if ($hwnd -ne [IntPtr]::Zero) {
    $box = Get-ClientBox $hwnd
    Write-Host ("client : {0}x{1} at {2},{3}" -f $box.W, $box.H, $box.X, $box.Y)
    if ($box.W -lt 8 -or $box.H -lt 8) { throw "client area is $($box.W)x$($box.H) -- window not ready" }

    $bmp = New-Object System.Drawing.Bitmap $box.W, $box.H
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $hdc = $g.GetHdc()
    # 2 = PW_RENDERFULLCONTENT: include the DWM-composited surface, which is
    # what makes this work on a window that is not the foreground one.
    $ok = [Win]::PrintWindow($hwnd, $hdc, 2)
    $g.ReleaseHdc($hdc)
    $g.Dispose()
    $mode = "PrintWindow"

    if (-not $ok -or (Test-Black $bmp)) {
        $bmp.Dispose()
        $bmp = New-Object System.Drawing.Bitmap $box.W, $box.H
        $g = [System.Drawing.Graphics]::FromImage($bmp)
        $g.CopyFromScreen($box.X, $box.Y, 0, 0, (New-Object System.Drawing.Size $box.W, $box.H))
        $g.Dispose()
        $mode = "CopyFromScreen (PrintWindow came back black)"
    }
} else {
    $b = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
    $bmp = New-Object System.Drawing.Bitmap $b.Width, $b.Height
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.CopyFromScreen($b.X, $b.Y, 0, 0, (New-Object System.Drawing.Size $b.Width, $b.Height))
    $g.Dispose()
    $mode = "CopyFromScreen (full screen)"
}

# ---- save ------------------------------------------------------------------
if ([string]::IsNullOrWhiteSpace($Out)) {
    $root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
    $dir = Join-Path $root "art\scene_shots"
    $stamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $Out = Join-Path $dir ("ggc_{0}.png" -f $stamp)
} else {
    if (-not [System.IO.Path]::IsPathRooted($Out)) {
        $Out = Join-Path (Get-Location).Path $Out
    }
    $dir = Split-Path -Parent $Out
}
if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }

$bmp.Save($Out, [System.Drawing.Imaging.ImageFormat]::Png)
$bmp.Dispose()

$fi = Get-Item $Out
Write-Host ""
Write-Host ("saved  : {0}" -f $fi.FullName)
Write-Host ("size   : {0} bytes  via {1}" -f $fi.Length, $mode)
