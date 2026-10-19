<#
.SYNOPSIS
    PhoneDesk - a Samsung DeX-style desktop for Galaxy phones without DeX, over USB.

.DESCRIPTION
    scrcpy creates a second (virtual) display on the phone and shows it in a window on this PC.
    One UI fills that display with its own DeX launcher (taskbar, app drawer, clock, notifications).
    PhoneDesk switches the display to freeform so apps open as movable, resizable windows, and runs
    from the system tray: it opens the desktop when the phone is plugged in, moves apps between the
    phone and the desktop, and remembers screen size, text size and options.

    Tested on Galaxy M15 (SM-M156B), Android 16 / One UI 8.5, scrcpy 4.1, Windows 11.

.EXAMPLE
    PhoneDesk.ps1               Run (system tray icon).
    PhoneDesk.ps1 -Install      Check requirements, add Desktop and Start menu shortcuts.
    PhoneDesk.ps1 -Uninstall    Remove shortcuts and settings, undo the phone setting PhoneDesk changed.
#>
param([switch]$Install, [switch]$Uninstall)

Add-Type -AssemblyName System.Windows.Forms, System.Drawing
if (-not ('PhoneDesk.Win32' -as [type])) {
    Add-Type -ReferencedAssemblies System.Windows.Forms, System.Drawing -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
using System.Windows.Forms;

namespace PhoneDesk {
    public static class Win32 {
        [StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left, Top, Right, Bottom; }
        [StructLayout(LayoutKind.Sequential)] public struct POINT { public int X, Y; }
        [DllImport("user32.dll")] public static extern bool SetProcessDPIAware();
        [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
        [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
        [DllImport("user32.dll")] public static extern bool IsIconic(IntPtr hWnd);
        [DllImport("user32.dll")] public static extern bool GetClientRect(IntPtr hWnd, out RECT rect);
        [DllImport("user32.dll")] public static extern bool ClientToScreen(IntPtr hWnd, ref POINT point);
    }

    // Window bar strip: never takes focus, so clicking its buttons leaves the phone window active.
    public class BarForm : Form {
        protected override bool ShowWithoutActivation { get { return true; } }
        protected override CreateParams CreateParams {
            get {
                CreateParams cp = base.CreateParams;
                cp.ExStyle |= 0x08000000 | 0x80;   // WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW
                return cp;
            }
        }
    }
}
'@
}

# ---------------------------------------------------------------------------------------------
# Paths and settings
# ---------------------------------------------------------------------------------------------
$AppDir      = Join-Path $env:LOCALAPPDATA 'PhoneDesk'
$ConfigFile  = Join-Path $AppDir 'settings.json'
$BackupFile  = Join-Path $AppDir 'phone-settings-backup.json'
$LogFile     = Join-Path $AppDir 'scrcpy.log'
$IconFile    = Join-Path $AppDir 'PhoneDesk.ico'
$StartupLnk  = Join-Path ([Environment]::GetFolderPath('Startup')) 'PhoneDesk.lnk'
$ShortcutDirs = @([Environment]::GetFolderPath('Desktop'), [Environment]::GetFolderPath('Programs'))
$WindowTitle = 'PhoneDesk'
$PowerShellExe = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'

# Developer setting that lets every app open in a resizable window. Its original value is
# backed up before the first change and put back by "Restore phone settings" / -Uninstall.
$PhoneSetting = 'force_resizable_activities'

$Defaults = [ordered]@{
    Width          = 1920
    Height         = 1080
    Dpi            = 160
    Fullscreen     = $false
    Audio          = $true
    OnScreenKeyboard = $true
    WindowBars     = $true
    PhoneScreenOff = $false
    AutoOpen       = $true
}

function Read-Settings {
    $s = [pscustomobject]$Defaults
    if (Test-Path $ConfigFile) {
        try {
            $saved = Get-Content $ConfigFile -Raw | ConvertFrom-Json
            foreach ($k in $Defaults.Keys) { if ($null -ne $saved.$k) { $s.$k = $saved.$k } }
        } catch { }
    }
    $s
}

function Save-Settings { $Settings | ConvertTo-Json | Set-Content -Path $ConfigFile -Encoding UTF8 }

# ---------------------------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------------------------
function Find-Scrcpy {
    $candidates = @(
        (Join-Path $PSScriptRoot 'scrcpy\scrcpy.exe')
        Get-ChildItem "$env:LOCALAPPDATA\Microsoft\WinGet\Packages\Genymobile.scrcpy_*\*\scrcpy.exe" -ErrorAction SilentlyContinue |
            Sort-Object LastWriteTime -Descending | ForEach-Object FullName
        (Get-Command scrcpy.exe -ErrorAction SilentlyContinue).Source
        'C:\scrcpy\scrcpy.exe'
    )
    $candidates | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1
}

function Find-Adb([string]$ScrcpyExe) {
    $candidates = @(
        (Get-Command adb.exe -ErrorAction SilentlyContinue).Source
        'C:\platform-tools\adb.exe'
        "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe"
        $(if ($ScrcpyExe) { Join-Path (Split-Path $ScrcpyExe) 'adb.exe' })
    )
    $candidates | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1
}

$Scrcpy = Find-Scrcpy
$Adb    = Find-Adb $Scrcpy

$script:Serial = $null
function Invoke-Adb   { & $Adb @args 2>$null }
function Invoke-Phone { & $Adb -s $script:Serial @args 2>$null }

# First USB phone as @{ Serial; State } (State: device / unauthorized / offline), or $null.
function Get-Phone {
    $phones = foreach ($line in (Invoke-Adb devices)) {
        if ($line -match '^(\S+)\s+(device|unauthorized|offline)\s*$') {
            [pscustomobject]@{ Serial = $Matches[1]; State = $Matches[2] }
        }
    }
    $phones | Sort-Object { $_.State -ne 'device' } | Select-Object -First 1
}

# ---------------------------------------------------------------------------------------------
# Phone setting (backed up once, restorable)
# ---------------------------------------------------------------------------------------------
function Set-PhoneDesktopSetting {
    if (-not (Test-Path $BackupFile)) {
        $original = "$(Invoke-Phone shell settings get global $PhoneSetting)".Trim()
        @{ $PhoneSetting = $original } | ConvertTo-Json | Set-Content -Path $BackupFile -Encoding UTF8
    }
    Invoke-Phone shell settings put global $PhoneSetting 1 | Out-Null
}

function Restore-PhoneSetting {
    if (-not (Test-Path $BackupFile)) { return $true }
    $original = (Get-Content $BackupFile -Raw | ConvertFrom-Json).$PhoneSetting
    if (-not $original -or $original -eq 'null') { Invoke-Phone shell settings delete global $PhoneSetting | Out-Null }
    else { Invoke-Phone shell settings put global $PhoneSetting $original | Out-Null }
    $now = "$(Invoke-Phone shell settings get global $PhoneSetting)".Trim()
    if ($now -eq '1' -and $original -ne '1') { return $false }    # adb call failed; keep the backup
    Remove-Item $BackupFile
    $true
}

# ---------------------------------------------------------------------------------------------
# Icon and shortcuts
# ---------------------------------------------------------------------------------------------
function New-IconBitmap([int]$Size) {
    $bmp = New-Object System.Drawing.Bitmap $Size, $Size
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
    $k = $Size / 32.0
    [single]$r = 12 * $k; [single]$lo = 1 * $k; [single]$hi = 31 * $k - $r
    $tile = New-Object System.Drawing.Drawing2D.GraphicsPath
    $tile.AddArc($lo, $lo, $r, $r, 180, 90)
    $tile.AddArc($hi, $lo, $r, $r, 270, 90)
    $tile.AddArc($hi, $hi, $r, $r, 0, 90)
    $tile.AddArc($lo, $hi, $r, $r, 90, 90)
    $tile.CloseFigure()
    $g.FillPath((New-Object System.Drawing.SolidBrush ([System.Drawing.Color]::FromArgb(255, 21, 101, 216))), $tile)
    $pen = New-Object System.Drawing.Pen ([System.Drawing.Color]::White), ([single](2.4 * $k))
    $g.DrawRectangle($pen, [single](6 * $k), [single](8 * $k), [single](20 * $k), [single](13 * $k))
    $g.FillRectangle([System.Drawing.Brushes]::White, [single](14 * $k), [single](21 * $k), [single](4 * $k), [single](3 * $k))
    $g.FillRectangle([System.Drawing.Brushes]::White, [single](11 * $k), [single](24 * $k), [single](10 * $k), [single](2 * $k))
    $g.Dispose()
    $bmp
}

# .ico with PNG-compressed images (supported by Windows Vista and later).
function Save-IconFile {
    $sizes = 16, 32, 48, 256
    $pngs = foreach ($s in $sizes) {
        $bmp = New-IconBitmap $s
        $ms = New-Object System.IO.MemoryStream
        $bmp.Save($ms, [System.Drawing.Imaging.ImageFormat]::Png)
        $bmp.Dispose()
        , $ms.ToArray()
    }
    $w = New-Object System.IO.BinaryWriter ([System.IO.File]::Create($IconFile))
    $w.Write([uint16]0); $w.Write([uint16]1); $w.Write([uint16]$sizes.Count)
    $offset = 6 + 16 * $sizes.Count
    for ($i = 0; $i -lt $sizes.Count; $i++) {
        $dim = if ($sizes[$i] -ge 256) { 0 } else { $sizes[$i] }
        $w.Write([byte]$dim); $w.Write([byte]$dim); $w.Write([byte]0); $w.Write([byte]0)
        $w.Write([uint16]1); $w.Write([uint16]32)
        $w.Write([uint32]$pngs[$i].Length); $w.Write([uint32]$offset)
        $offset += $pngs[$i].Length
    }
    foreach ($p in $pngs) { $w.Write($p) }
    $w.Close()
}

function New-Shortcut([string]$LnkPath) {
    if (-not (Test-Path $IconFile)) { Save-IconFile }
    $lnk = (New-Object -ComObject WScript.Shell).CreateShortcut($LnkPath)
    $lnk.TargetPath       = $PowerShellExe
    $lnk.Arguments        = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$PSCommandPath`""
    $lnk.WorkingDirectory = $PSScriptRoot
    $lnk.IconLocation     = "$IconFile,0"
    $lnk.Description      = 'DeX-style desktop for your Galaxy phone'
    $lnk.WindowStyle      = 7
    $lnk.Save()
}

# ---------------------------------------------------------------------------------------------
# Desktop (scrcpy virtual display)
# ---------------------------------------------------------------------------------------------
$script:Proc       = $null    # cmd.exe wrapper around scrcpy (redirects its log)
$script:DisplayId  = $null    # Android display id of the desktop
$script:UserClosed = $false   # desktop closed while phone still connected: don't auto-reopen
$script:LastState  = 'none'
$script:Model      = ''
$script:TipShown   = $false

function Test-DesktopRunning { [bool]($script:Proc -and -not $script:Proc.HasExited) }

function Get-DesktopWindow {
    Get-Process scrcpy -ErrorAction SilentlyContinue |
        Where-Object { $_.MainWindowTitle -eq $WindowTitle } | Select-Object -First 1
}

function Show-Desktop {
    $w = Get-DesktopWindow
    if (-not $w) { return }
    if ([PhoneDesk.Win32]::IsIconic($w.MainWindowHandle)) { [void][PhoneDesk.Win32]::ShowWindow($w.MainWindowHandle, 9) }
    [void][PhoneDesk.Win32]::SetForegroundWindow($w.MainWindowHandle)
}

# Checks the phone and returns its state: device / unauthorized / offline / none.
function Update-PhoneState {
    $phone = Get-Phone
    $state = if ($phone) { $phone.State } else { 'none' }
    if ($state -ne $script:LastState) {
        $script:LastState = $state
        if ($state -eq 'device') {
            $script:Serial = $phone.Serial
            $name = "$(Invoke-Phone shell settings get global device_name)".Trim()
            if (-not $name -or $name -eq 'null') { $name = "$(Invoke-Phone shell getprop ro.product.model)".Trim() }
            $script:Model = $name
        } elseif ($state -eq 'unauthorized') {
            Notify 'Allow USB debugging' 'Unlock your phone and tap Allow on the USB debugging prompt.'
        }
        Update-Menu
    }
    $state
}

function Start-Desktop {
    if (Test-DesktopRunning) { Show-Desktop; return }
    switch (Update-PhoneState) {
        'device'       { }
        'unauthorized' { Notify 'Allow USB debugging' 'Unlock your phone and tap Allow on the USB debugging prompt.'; return }
        default        { Notify 'Phone not found' 'Connect your phone with a USB data cable and turn on USB debugging.'; return }
    }
    Set-PhoneDesktopSetting

    $a = @(
        '-s', $script:Serial
        "--new-display=$($Settings.Width)x$($Settings.Height)/$($Settings.Dpi)"
        "--window-title=$WindowTitle"
        '--no-vd-destroy-content'       # on close or unplug, open apps move back to the phone
        '--mouse-bind=++bh:bhsn'        # right/middle click go to Android; mouse buttons 4/5 = Back/Home
        '--stay-awake'
        '--max-fps=60'
        '--video-bit-rate=16M'
    )
    # Show the phone keyboard on the desktop, or hide it and type only with the PC keyboard
    $a += '--display-ime-policy=' + $(if ($Settings.OnScreenKeyboard) { 'local' } else { 'hide' })
    if (-not $Settings.Audio)     { $a += '--no-audio' }
    if ($Settings.Fullscreen)     { $a += '--fullscreen' }
    if ($Settings.PhoneScreenOff) { $a += '--turn-screen-off' }

    # Start from an empty log so the previous session's display id is never picked up
    Remove-Item $LogFile -ErrorAction SilentlyContinue

    $psi = New-Object System.Diagnostics.ProcessStartInfo 'cmd.exe'
    $psi.Arguments = '/c ""{0}" {1} > "{2}" 2>&1"' -f $Scrcpy, ($a -join ' '), $LogFile
    $psi.UseShellExecute = $false
    $psi.CreateNoWindow = $true
    $psi.WorkingDirectory = Split-Path $Scrcpy
    $psi.EnvironmentVariables['ADB'] = $Adb    # share one adb server with PhoneDesk
    $script:Proc = [System.Diagnostics.Process]::Start($psi)
    $script:DisplayId = $null
    Update-Menu
}

function Stop-Desktop {
    $script:UserClosed = $true
    if (-not (Test-DesktopRunning)) { return }
    $w = Get-DesktopWindow
    if ($w) { [void]$w.CloseMainWindow(); [void]$script:Proc.WaitForExit(5000) }
    if (-not $script:Proc.HasExited) { & taskkill.exe /PID $script:Proc.Id /T /F 2>$null | Out-Null }
    $script:Proc = $null
    $script:DisplayId = $null
    Update-Menu
}


function Restart-Desktop {
    Stop-Desktop
    $script:UserClosed = $false
    Start-Desktop
}

function Read-Log {
    try {
        $fs = [System.IO.File]::Open($LogFile, 'Open', 'Read', 'ReadWrite')
        $reader = New-Object System.IO.StreamReader $fs
        $text = $reader.ReadToEnd()
        $reader.Close()
        $text
    } catch { '' }
}

# Once scrcpy reports the new display, make it freeform so every app opens as a window.
function Initialize-Display {
    if ((Read-Log) -notmatch 'New display: \S+ \(id=(\d+)\)') { return }
    $script:DisplayId = [int]$Matches[1]
    Invoke-Phone shell cmd window set-display-windowing-mode -d $script:DisplayId 5 | Out-Null
    if ("$(Invoke-Phone shell cmd window get-display-windowing-mode -d $script:DisplayId)" -notmatch 'freeform') {
        $script:DisplayId = $null    # not applied yet; try again on the next tick
        return
    }
    Update-Menu
    if (-not $script:TipShown) {
        $script:TipShown = $true
        Notify 'Desktop ready' 'Double-click desktop icons to open apps. Alt+F = full screen. Tray icon > Help for more.'
    }
}

function Show-StartError {
    $lines = (Read-Log) -split "`r?`n" | Where-Object { $_ -match '\S' }
    $errors = $lines | Where-Object { $_ -match 'ERROR|Exception' }
    $detail = (@(if ($errors) { $errors } else { $lines }) | Select-Object -Last 8) -join "`n"
    Show-Message "The desktop could not start.`n`n$detail`n`nFull log: $LogFile" 'Warning'
}

# Standard (non-launcher) app tasks on a display, top-most first.
function Get-Apps([int]$Display) {
    $root = $null
    foreach ($line in (Invoke-Phone shell am stack list)) {
        if ($line -match '^RootTask id=(\d+) .*displayId=(\d+)') {
            $root = [pscustomobject]@{ Root = [int]$Matches[1]; Display = [int]$Matches[2]; Standard = $false; Component = $null }
        } elseif ($root -and $line -match 'mActivityType=(\w+)') {
            $root.Standard = $Matches[1] -eq 'standard'
        } elseif ($root -and $line -match '^\s*taskId=\d+: (\S+)') {
            $root.Component = $Matches[1]
            if ($root.Display -eq $Display -and $root.Standard) { $root }
            $root = $null
        }
    }
}

# Moves the phone's current app onto the desktop, or the focused desktop window onto the phone.
function Move-App([switch]$ToDesktop) {
    if (-not $script:DisplayId) { return }
    $from, $to = if ($ToDesktop) { 0, $script:DisplayId } else { $script:DisplayId, 0 }
    $app = Get-Apps $from | Select-Object -First 1
    if (-not $app) {
        Notify 'Nothing to move' $(if ($ToDesktop) { 'Open an app on your phone first.' } else { 'No app windows are open on the desktop.' })
        return
    }
    Invoke-Phone shell am display move-stack $app.Root $to | Out-Null
    if ($ToDesktop) { Show-Desktop }
}

# ---------------------------------------------------------------------------------------------
# Window bars: a thin strip just above each desktop window with minimize, maximize and close.
# The strip sits outside the app, so it never covers the app's own header.
# ---------------------------------------------------------------------------------------------
$BarHeight  = 26
$BarButton  = 34
$script:Bars        = @{}   # taskId -> BarForm
$script:SavedBounds = @{}   # taskId -> bounds before maximize, for restore
$script:DisplayW    = 0     # desktop size, read from its home task
$script:DisplayH    = 0
$script:Windows     = @()   # last list of desktop windows

# Standard app windows on the desktop display, with their bounds in desktop pixels.
function Get-DesktopWindows {
    $list = @()
    $root = $null; $display = -1; $type = ''; $rootBounds = @(0, 0, 0, 0)
    foreach ($line in (Invoke-Phone shell am stack list)) {
        if ($line -match '^RootTask id=(\d+) bounds=\[(-?\d+),(-?\d+)\]\[(-?\d+),(-?\d+)\] displayId=(\d+)') {
            $root = [int]$Matches[1]; $display = [int]$Matches[6]; $type = ''
            $rootBounds = @([int]$Matches[2], [int]$Matches[3], [int]$Matches[4], [int]$Matches[5])
            continue
        }
        if ($display -ne $script:DisplayId) { continue }
        if ($line -match 'mActivityType=(\w+)') {
            $type = $Matches[1]
            if ($type -eq 'home' -and $rootBounds[0] -eq 0 -and $rootBounds[1] -eq 0) {
                $script:DisplayW = $rootBounds[2]; $script:DisplayH = $rootBounds[3]
            }
            continue
        }
        if ($type -eq 'standard' -and $line -match '^\s*taskId=(\d+): (\S+) bounds=\[(-?\d+),(-?\d+)\]\[(-?\d+),(-?\d+)\].* visible=(\w+)') {
            $list += [pscustomobject]@{
                Task = [int]$Matches[1]; Root = $root; Component = $Matches[2]
                L = [int]$Matches[3]; T = [int]$Matches[4]; R = [int]$Matches[5]; B = [int]$Matches[6]
                Visible = ($Matches[7] -eq 'true')
            }
        }
    }
    $list
}

# Maps desktop pixels to screen pixels: scrcpy scales the desktop to fit its window, centred.
function Get-DesktopMapping {
    $w = Get-DesktopWindow
    if (-not $w -or $script:DisplayW -le 0) { return $null }
    $rc = New-Object 'PhoneDesk.Win32+RECT'
    [void][PhoneDesk.Win32]::GetClientRect($w.MainWindowHandle, [ref]$rc)
    $origin = New-Object 'PhoneDesk.Win32+POINT'
    [void][PhoneDesk.Win32]::ClientToScreen($w.MainWindowHandle, [ref]$origin)
    $scale = [Math]::Min($rc.Right / $script:DisplayW, $rc.Bottom / $script:DisplayH)
    [pscustomobject]@{
        Scale = $scale
        X0 = $origin.X + ($rc.Right - $script:DisplayW * $scale) / 2
        Y0 = $origin.Y + ($rc.Bottom - $script:DisplayH * $scale) / 2
    }
}

function Get-AppLabel([string]$component) {
    $last = (($component -split '/')[0] -split '\.')[-1]
    $names = @{ myfiles = 'My Files'; chrome = 'Chrome'; messaging = 'Messages'; notes = 'Notes'; dialer = 'Phone'; gm = 'Gmail'; maps = 'Maps' }
    if ($names.ContainsKey($last)) { return $names[$last] }
    $last.Substring(0, 1).ToUpper() + $last.Substring(1)
}

function Paint-Bar($form, $e) {
    $win = $form.Tag
    if (-not $win) { return }
    $g = $e.Graphics
    $g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
    $fg = [System.Drawing.Color]::FromArgb(235, 235, 235)
    $pen = New-Object System.Drawing.Pen $fg, ([single]1.6)
    $text = New-Object System.Drawing.SolidBrush $fg
    $font = New-Object System.Drawing.Font 'Segoe UI', 9
    $g.DrawString((Get-AppLabel $win.Component), $font, $text, ([single]8), ([single]4))
    $w = $form.ClientSize.Width; $mid = [single]($form.ClientSize.Height / 2)
    $x = [single]($w - 3 * $BarButton + $BarButton / 2)
    $g.DrawLine($pen, $x - 6, $mid + 3, $x + 6, $mid + 3)                                   # minimize
    $x = [single]($w - 2 * $BarButton + $BarButton / 2)
    $g.DrawRectangle($pen, $x - 6, $mid - 6, 12, 12)                                       # maximize
    $x = [single]($w - $BarButton + $BarButton / 2)
    $g.DrawLine($pen, $x - 6, $mid - 6, $x + 6, $mid + 6); $g.DrawLine($pen, $x + 6, $mid - 6, $x - 6, $mid + 6)   # close
}

function Invoke-BarButton($win, [int]$slot) {
    switch ($slot) {
        0 {   # minimize: open Samsung's window menu from the handle, then tap Minimize in it
            $cx = [int](($win.L + $win.R) / 2)
            Invoke-Phone shell input touchscreen -d $script:DisplayId tap $cx ($win.T + 8) | Out-Null
            Start-Sleep -Milliseconds 450
            Invoke-Phone shell input touchscreen -d $script:DisplayId tap ($cx - 45) ($win.T + 46) | Out-Null
        }
        1 {   # maximize, or restore the size it had before
            if ($script:SavedBounds.ContainsKey($win.Task)) {
                $b = $script:SavedBounds[$win.Task]; $script:SavedBounds.Remove($win.Task)
            } else {
                $script:SavedBounds[$win.Task] = @($win.L, $win.T, $win.R, $win.B)
                $b = @(0, 0, $script:DisplayW, $script:DisplayH)
            }
            Invoke-Phone shell am task resize $win.Task $b[0] $b[1] $b[2] $b[3] | Out-Null
        }
        2 {   # close: remove the window's task
            Invoke-Phone shell am stack remove $win.Root | Out-Null
        }
    }
}

function Bar-MouseDown($form, $e) {
    if ($e.Button -ne [System.Windows.Forms.MouseButtons]::Left -or -not $form.Tag) { return }
    $slot = [int][Math]::Floor(($e.X - ($form.ClientSize.Width - 3 * $BarButton)) / $BarButton)
    if ($slot -ge 0 -and $slot -le 2) { Invoke-BarButton $form.Tag $slot; Update-Bars }
}

function Hide-Bars {
    foreach ($f in @($script:Bars.Values)) { $f.Dispose() }
    $script:Bars = @{}
    $script:Windows = @()
}

function Update-Bars {
    if (-not (Test-DesktopRunning) -or -not $script:DisplayId -or -not $Settings.WindowBars) { Hide-Bars; return }
    $m = Get-DesktopMapping
    if (-not $m) { return }
    $shown = @{}
    foreach ($win in @($script:Windows | Where-Object { $_.Visible })) {
        $shown[$win.Task] = $true
        if (-not $script:Bars.ContainsKey($win.Task)) {
            $f = New-Object PhoneDesk.BarForm
            $f.FormBorderStyle = 'None'; $f.ShowInTaskbar = $false; $f.TopMost = $true
            $f.StartPosition = 'Manual'; $f.BackColor = [System.Drawing.Color]::FromArgb(40, 40, 40)
            $f.add_Paint({ param($s, $e) Paint-Bar $s $e })
            $f.add_MouseDown({ param($s, $e) Bar-MouseDown $s $e })
            $script:Bars[$win.Task] = $f
        }
        $f = $script:Bars[$win.Task]
        $f.Tag = $win
        $x = [int]($m.X0 + $win.L * $m.Scale)
        $y = [int]($m.Y0 + $win.T * $m.Scale)
        $width = [Math]::Max(3 * $BarButton + 120, [int](($win.R - $win.L) * $m.Scale))
        $f.Bounds = New-Object System.Drawing.Rectangle $x, ($y - $BarHeight), $width, $BarHeight
        if (-not $f.Visible) { $f.Show() }
        $f.Invalidate()
    }
    foreach ($id in @($script:Bars.Keys)) {
        if (-not $shown.ContainsKey($id)) { $script:Bars[$id].Dispose(); $script:Bars.Remove($id) }
    }
}

# ---------------------------------------------------------------------------------------------
# Tray UI helpers
# ---------------------------------------------------------------------------------------------
function Notify([string]$Title, [string]$Text) {
    if ($Tray) { $Tray.ShowBalloonTip(5000, $Title, $Text, [System.Windows.Forms.ToolTipIcon]::None) }
}

function Show-Message([string]$Text, [string]$Icon = 'Information') {
    if ($Timer) { $Timer.Stop() }
    $owner = New-Object System.Windows.Forms.Form -Property @{ TopMost = $true; ShowInTaskbar = $false; Opacity = 0 }
    $owner.Show()
    [void][System.Windows.Forms.MessageBox]::Show($owner, $Text, 'PhoneDesk', 'OK', $Icon)
    $owner.Dispose()
    if ($Timer) { $Timer.Start() }
}

function Show-Help {
    Show-Message @'
USING THE DESKTOP
  - Double-click icons on the desktop; single-click apps in the taskbar.
  - Apps open as windows. Each window has a grey bar just above it with
    the app name and three buttons:  -  minimize,  []  maximize (click
    again to restore),  x  close.
    Minimized apps come back by opening them again (desktop icon, taskbar
    or app drawer). Turn the bar off in tray > Options.
  - Clicking a text box shows the phone keyboard on the desktop
    (tray menu > On-screen keyboard on desktop), or just type with the PC keyboard.
    Too big? Keyboard toolbar "..." > Mode > Floating keyboard.
  - Right-click opens context menus. Mouse side buttons = Back / Home.
  - Copy and paste work between the PC and the phone.
  - Drag files onto the window to copy them to the phone's Download folder
    (drop an .apk file to install it).

KEYBOARD SHORTCUTS
  Alt+F          Full screen on / off
  Alt+O          Turn the phone's own screen off (Alt+Shift+O turns it on)
  Alt+H / Alt+B  Home / Back
  Alt+S          Recent apps
  Alt+Up/Down    Volume

TRAY MENU
  Move phone app to desktop - brings the app open on your phone onto the desktop.
  Send desktop app to phone - moves the front desktop window back to the phone.
  Screen size, Text size and Options change how the desktop looks and starts.

Unplugging the cable closes the desktop; open apps move back to the phone.
'@
}

function Set-Option {
    param([int]$Width, [int]$Height, [int]$Dpi, [Nullable[bool]]$Fullscreen, [Nullable[bool]]$Audio,
          [Nullable[bool]]$OnScreenKeyboard, [Nullable[bool]]$PhoneScreenOff, [Nullable[bool]]$AutoOpen,
          [Nullable[bool]]$WindowBars)
    $restart = $false
    foreach ($k in @($PSBoundParameters.Keys)) {
        if ($Settings.$k -ne $PSBoundParameters[$k]) {
            $Settings.$k = $PSBoundParameters[$k]
            if ($k -in 'Width', 'Height', 'Dpi', 'Audio', 'OnScreenKeyboard') { $restart = $true }
            if ($k -eq 'WindowBars') { Update-Bars }
        }
    }
    Save-Settings
    if ($restart -and (Test-DesktopRunning)) { Restart-Desktop }
    Update-Menu
}

function Switch-Startup {
    if (Test-Path $StartupLnk) { Remove-Item $StartupLnk } else { New-Shortcut $StartupLnk }
    Update-Menu
}

function Restore-FromMenu {
    Stop-Desktop
    if ((Update-PhoneState) -ne 'device') { Notify 'Phone not connected' 'Connect the phone to restore its settings.'; return }
    if (Restore-PhoneSetting) { Notify 'Phone settings restored' 'The next time you open the desktop the setting is applied again.' }
}

function Update-Menu {
    if (-not $Menu) { return }
    $running = Test-DesktopRunning
    $name = if ($script:Model) { $script:Model } else { 'phone' }
    $status = if ($running -and $script:DisplayId) { "Desktop open - $name" }
              elseif ($running)                       { 'Starting desktop...' }
              elseif ($script:LastState -eq 'device') { "Connected - $name" }
              elseif ($script:LastState -eq 'unauthorized') { 'Allow USB debugging on the phone' }
              else                                    { 'Phone not connected' }
    $miStatus.Text = $status
    $tip = "PhoneDesk - $status"
    $Tray.Text = $tip.Substring(0, [Math]::Min(63, $tip.Length))
    $miOpen.Text = if ($running) { 'Show desktop' } else { 'Open desktop' }
    $miClose.Enabled = $running
    $miToDesk.Enabled = [bool]$script:DisplayId
    $miToPhone.Enabled = [bool]$script:DisplayId
    foreach ($i in $miSize.DropDownItems) { $i.Checked = ($i.Tag[0] -eq $Settings.Width -and $i.Tag[1] -eq $Settings.Height) }
    foreach ($i in $miDpi.DropDownItems)  { $i.Checked = ($i.Tag -eq $Settings.Dpi) }
    $miFull.Checked    = $Settings.Fullscreen
    $miAudio.Checked   = $Settings.Audio
    $miBars.Checked    = $Settings.WindowBars
    $miKeyboard.Checked = $Settings.OnScreenKeyboard
    $miKeyboard.Text = if ($Settings.OnScreenKeyboard) { 'On-screen keyboard on desktop: ON' } else { 'On-screen keyboard on desktop: OFF' }
    $miScreen.Checked  = $Settings.PhoneScreenOff
    $miAuto.Checked    = $Settings.AutoOpen
    $miStartup.Checked = Test-Path $StartupLnk
}

function Invoke-Tick {
    if ($ExitSignal.WaitOne(0)) { Exit-PhoneDesk; return }
    if ($OpenSignal.WaitOne(0)) { $script:UserClosed = $false; Start-Desktop }

    if ($script:Proc) {
        if (-not $script:Proc.HasExited) {
            if (-not $script:DisplayId) { Initialize-Display }
            return
        }
        # scrcpy ended by itself: window closed, cable unplugged, or failed to start
        $hadDisplay = [bool]$script:DisplayId
        $script:Proc = $null
        $script:DisplayId = $null
        if ((Update-PhoneState) -eq 'device') {
            $script:UserClosed = $true
            if (-not $hadDisplay) { Show-StartError }
        } else {
            Notify 'Phone disconnected' 'Open apps moved back to your phone. Plug it in again to continue.'
        }
        Update-Menu
        return
    }

    if ((Update-PhoneState) -ne 'device') { $script:UserClosed = $false }
    elseif ($Settings.AutoOpen -and -not $script:UserClosed) { Start-Desktop }
}

function Exit-PhoneDesk {
    $Timer.Stop()
    $BarTimer.Stop()
    Hide-Bars
    Stop-Desktop
    $Tray.Visible = $false
    $Tray.Dispose()
    [System.Windows.Forms.Application]::Exit()
}

# ---------------------------------------------------------------------------------------------
# Install / uninstall
# ---------------------------------------------------------------------------------------------
function Invoke-Install {
    Write-Host ''
    Write-Host '  PhoneDesk setup' -ForegroundColor Cyan
    Write-Host '  ---------------'
    $null = New-Item -ItemType Directory -Force -Path $AppDir

    $script:Scrcpy = Find-Scrcpy
    if (-not $script:Scrcpy) {
        Write-Host '  scrcpy (free, open source, github.com/Genymobile/scrcpy) is required.'
        if (Get-Command winget.exe -ErrorAction SilentlyContinue) {
            $answer = Read-Host '  Install it now with winget? [Y/n]'
            if ($answer -notmatch '^\s*n') {
                winget install --id Genymobile.scrcpy --exact --accept-source-agreements --accept-package-agreements
                $script:Scrcpy = Find-Scrcpy
            }
        }
        if (-not $script:Scrcpy) {
            Write-Host ''
            Write-Host '  scrcpy not found. Download scrcpy-win64 from https://github.com/Genymobile/scrcpy/releases,' -ForegroundColor Yellow
            Write-Host '  unzip it into a folder named "scrcpy" next to PhoneDesk.ps1, then run Install.cmd again.' -ForegroundColor Yellow
            return
        }
    }
    $version = "$(& $script:Scrcpy --version 2>$null | Select-Object -First 1)"
    Write-Host "  [ok] $version"
    Write-Host "       $script:Scrcpy"
    if ($version -match 'scrcpy (\d+)\.(\d+)' -and ([int]$Matches[1] * 100 + [int]$Matches[2]) -lt 302) {
        Write-Host '  [!]  scrcpy 3.2 or newer is required. Update with: winget upgrade Genymobile.scrcpy' -ForegroundColor Yellow
        return
    }

    $script:Adb = Find-Adb $script:Scrcpy
    Write-Host "  [ok] adb: $script:Adb"

    Save-IconFile
    foreach ($dir in $ShortcutDirs) { New-Shortcut (Join-Path $dir 'PhoneDesk.lnk') }
    Write-Host '  [ok] Shortcuts added to the Desktop and Start menu'

    $phone = Get-Phone
    switch ($(if ($phone) { $phone.State } else { 'none' })) {
        'device'       { Write-Host "  [ok] Phone connected ($($phone.Serial))" }
        'unauthorized' { Write-Host '  [!]  Phone found - unlock it and tap Allow on the USB debugging prompt.' -ForegroundColor Yellow }
        default        { Write-Host '  [!]  No phone found yet - turn on USB debugging and plug it in (see README).' -ForegroundColor Yellow }
    }

    Write-Host ''
    $answer = Read-Host '  Start PhoneDesk now? [Y/n]'
    if ($answer -notmatch '^\s*n') {
        Start-Process $PowerShellExe -ArgumentList "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$PSCommandPath`"" -WindowStyle Hidden
        Write-Host '  PhoneDesk is running - look for its icon in the system tray (bottom right).'
    }
}

function Invoke-Uninstall {
    Write-Host ''
    Write-Host '  PhoneDesk uninstall' -ForegroundColor Cyan
    Write-Host '  -------------------'
    # Ask a running PhoneDesk to close (this also closes the desktop).
    try { [void][System.Threading.EventWaitHandle]::OpenExisting('Local\PhoneDesk.Exit').Set(); Start-Sleep 3 } catch { }

    if (Test-Path $BackupFile) {
        $phone = Get-Phone
        if ($phone -and $phone.State -eq 'device' -and $Adb) {
            $script:Serial = $phone.Serial
            if (Restore-PhoneSetting) { Write-Host '  [ok] Phone setting restored' }
        } else {
            Write-Host '  [!]  Phone not connected, so its setting was not restored. Either connect it and' -ForegroundColor Yellow
            Write-Host '       run Uninstall.cmd again, or run:  adb shell settings put global force_resizable_activities 0' -ForegroundColor Yellow
            Write-Host '       (or turn off Developer options > "Force activities to be resizable" on the phone).' -ForegroundColor Yellow
            return
        }
    }
    foreach ($lnk in @($StartupLnk) + ($ShortcutDirs | ForEach-Object { Join-Path $_ 'PhoneDesk.lnk' })) {
        if (Test-Path $lnk) { Remove-Item $lnk }
    }
    Write-Host '  [ok] Shortcuts removed'
    Remove-Item $AppDir -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host '  [ok] Settings removed'
    Write-Host ''
    Write-Host '  You can now delete the PhoneDesk folder. To remove scrcpy too:  winget uninstall Genymobile.scrcpy'
}

# ---------------------------------------------------------------------------------------------
# Entry point (dot-sourcing the script only loads the functions)
# ---------------------------------------------------------------------------------------------
if ($MyInvocation.InvocationName -eq '.') { return }
if ($Install)   { Invoke-Install; return }
if ($Uninstall) { Invoke-Uninstall; return }

$null = New-Item -ItemType Directory -Force -Path $AppDir
if (-not $Scrcpy -or -not $Adb) {
    [void][System.Windows.Forms.MessageBox]::Show("scrcpy was not found.`n`nRun Install.cmd in the PhoneDesk folder first.", 'PhoneDesk', 'OK', 'Warning')
    return
}

# One PhoneDesk per user; launching it again opens the desktop in the running copy.
$Mutex = New-Object System.Threading.Mutex $false, 'Local\PhoneDesk.Instance'
try { $owned = $Mutex.WaitOne(0) } catch [System.Threading.AbandonedMutexException] { $owned = $true }
$OpenSignal = New-Object System.Threading.EventWaitHandle $false, ([System.Threading.EventResetMode]::AutoReset), 'Local\PhoneDesk.Open'
$ExitSignal = New-Object System.Threading.EventWaitHandle $false, ([System.Threading.EventResetMode]::AutoReset), 'Local\PhoneDesk.Exit'
if (-not $owned) { [void]$OpenSignal.Set(); return }

[void][PhoneDesk.Win32]::SetProcessDPIAware()
[System.Windows.Forms.Application]::EnableVisualStyles()
$Settings = Read-Settings
if (-not (Test-Path $IconFile)) { Save-IconFile }

$Tray = New-Object System.Windows.Forms.NotifyIcon
$Tray.Icon = [System.Drawing.Icon]::FromHandle((New-IconBitmap ([System.Windows.Forms.SystemInformation]::SmallIconSize.Width)).GetHicon())
$Tray.Text = 'PhoneDesk'
$Menu = New-Object System.Windows.Forms.ContextMenuStrip
$Tray.ContextMenuStrip = $Menu

function Add-MenuItem($Parent, [string]$Text, [scriptblock]$OnClick, $Tag) {
    $item = New-Object System.Windows.Forms.ToolStripMenuItem $Text
    if ($OnClick) { $item.add_Click($OnClick) }
    if ($null -ne $Tag) { $item.Tag = $Tag }
    if ($Parent -is [System.Windows.Forms.ContextMenuStrip]) { [void]$Parent.Items.Add($item) }
    else { [void]$Parent.DropDownItems.Add($item) }
    $item
}
function Add-Separator { [void]$Menu.Items.Add((New-Object System.Windows.Forms.ToolStripSeparator)) }

$miStatus = Add-MenuItem $Menu 'Phone not connected'
$miStatus.Enabled = $false
Add-Separator
$miOpen = Add-MenuItem $Menu 'Open desktop' { $script:UserClosed = $false; Start-Desktop }
$miOpen.Font = New-Object System.Drawing.Font $miOpen.Font, ([System.Drawing.FontStyle]::Bold)
$miClose = Add-MenuItem $Menu 'Close desktop' { Stop-Desktop }
Add-Separator
$miToDesk  = Add-MenuItem $Menu 'Move phone app to desktop' { Move-App -ToDesktop }
$miToPhone = Add-MenuItem $Menu 'Send desktop app to phone' { Move-App }
Add-Separator

$miSize = Add-MenuItem $Menu 'Screen size'
$screen = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
$screenW = $screen.Width - $screen.Width % 8
$screenH = $screen.Height - $screen.Height % 8
$sizes = @(@(1280, 720), @(1600, 900), @(1920, 1080), @(2560, 1440))
if (-not ($sizes | Where-Object { $_[0] -eq $screenW -and $_[1] -eq $screenH })) { $sizes += , @($screenW, $screenH) }
foreach ($s in $sizes) {
    $label = '{0} x {1}' -f $s[0], $s[1]
    if ($s[0] -eq $screenW -and $s[1] -eq $screenH) { $label += '   (this screen)' }
    [void](Add-MenuItem $miSize $label { Set-Option -Width $this.Tag[0] -Height $this.Tag[1] } $s)
}

$miDpi = Add-MenuItem $Menu 'Text size'
foreach ($d in @(@('Small', 140), @('Normal', 160), @('Large', 200), @('Extra large', 240))) {
    [void](Add-MenuItem $miDpi $d[0] { Set-Option -Dpi $this.Tag } $d[1])
}

Add-Separator
# Top level, so it is easy to find: turn it off when you type with a keyboard connected to the PC
$miKeyboard = Add-MenuItem $Menu 'On-screen keyboard on desktop' { Set-Option -OnScreenKeyboard (-not $Settings.OnScreenKeyboard) }
$miKeyboard.ToolTipText = 'Off = hide the phone keypad on the desktop (use your PC keyboard)'

$miOptions = Add-MenuItem $Menu 'Options'
$miFull    = Add-MenuItem $miOptions 'Start in full screen (Alt+F toggles)' { Set-Option -Fullscreen (-not $Settings.Fullscreen) }
$miAudio   = Add-MenuItem $miOptions 'Play phone sound on this PC' { Set-Option -Audio (-not $Settings.Audio) }
$miBars    = Add-MenuItem $miOptions 'Show minimize / maximize / close bar on windows' { Set-Option -WindowBars (-not $Settings.WindowBars) }
$miScreen  = Add-MenuItem $miOptions 'Turn phone screen off while desktop is open' { Set-Option -PhoneScreenOff (-not $Settings.PhoneScreenOff) }
$miAuto    = Add-MenuItem $miOptions 'Open desktop when phone is plugged in' { Set-Option -AutoOpen (-not $Settings.AutoOpen) }
$miStartup = Add-MenuItem $miOptions 'Start PhoneDesk with Windows' { Switch-Startup }
Add-Separator
[void](Add-MenuItem $Menu 'Help and shortcuts' { Show-Help })
[void](Add-MenuItem $Menu 'Restore phone settings' { Restore-FromMenu })
[void](Add-MenuItem $Menu 'Exit' { Exit-PhoneDesk })

$Menu.add_Opening({ Update-Menu })
$Tray.add_MouseClick({ if ($_.Button -eq [System.Windows.Forms.MouseButtons]::Left) { $script:UserClosed = $false; Start-Desktop } })

$Timer = New-Object System.Windows.Forms.Timer
$Timer.Interval = 2000
$Timer.add_Tick({ try { Invoke-Tick } catch { } })

# Window bars follow the desktop windows; refreshed once a second, only while the desktop is open
$BarTimer = New-Object System.Windows.Forms.Timer
$BarTimer.Interval = 1000
$BarTimer.add_Tick({
    try {
        if (Test-DesktopRunning -and $script:DisplayId -and $Settings.WindowBars) { $script:Windows = Get-DesktopWindows; Update-Bars }
        else { Hide-Bars }
    } catch { }
})

$Tray.Visible = $true
Update-Menu
Invoke-Tick
$Timer.Start()
$BarTimer.Start()
[System.Windows.Forms.Application]::Run()
$Mutex.ReleaseMutex()
