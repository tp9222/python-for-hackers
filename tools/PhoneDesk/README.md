# PhoneDesk

A Samsung DeX-style desktop for Galaxy phones that don't have DeX (for example the Galaxy M15), shown on your Windows PC over a USB cable.

- A full desktop with a taskbar, app drawer, clock, notifications and quick settings, all from One UI's own DeX launcher.
- Apps open as **windows** that you can move, resize and overlap.
- It works with your PC's mouse and keyboard, and copy/paste is shared between the PC and the phone.
- Phone sound plays on the PC.
- You can drag files onto the desktop to copy them to the phone.
- The phone keeps working on its own screen while the desktop is open.
- Opens automatically when you plug the phone in. When you unplug, your open apps move back to the phone.

Tested on a Galaxy M15 5G (SM-M156B) with Android 16 / One UI 8.5, on Windows 11.

---

## What's in the folder

| File | What it is |
|---|---|
| `Install.cmd` | Double-click to set up: checks everything and adds the Desktop and Start menu shortcuts |
| `PhoneDesk.ps1` | The app itself. It runs in the system tray |
| `Uninstall.cmd` | Removes PhoneDesk and undoes its one phone setting |
| `scrcpy\` | [scrcpy 4.1](https://github.com/Genymobile/scrcpy) by Genymobile (Apache-2.0, see `scrcpy\LICENSE.txt`). It streams the phone's second screen to the PC. It includes `adb` |
| `README.md` | This guide |

Nothing else needs to be downloaded.

## Requirements

- **PC:** Windows 10 or 11 (64-bit).
- **Phone:** a Samsung Galaxy phone on Android 11 or newer. A recent One UI works best; the DeX-style taskbar comes from One UI itself.
- **Cable:** a USB cable that carries **data**. Some cheap cables only charge.

---

## Installation

### Step 1: Turn on USB debugging on the phone (one time)

1. Open **Settings > About phone > Software information**.
2. Tap **Build number** 7 times. Enter your PIN if asked. You'll see "Developer mode has been turned on".
3. Go back to **Settings > Developer options** (at the bottom of Settings).
4. Turn on **USB debugging**.

### Step 2: Connect the phone

1. Plug the phone into the PC with the USB cable.
2. Unlock the phone. A prompt appears: **"Allow USB debugging?"**
3. Tick **Always allow from this computer**, then tap **Allow**.

> If the prompt doesn't appear, pull down the notification shade, tap the USB notification, and pick **Transferring files / Android Auto**. Then unplug and plug the cable back in.

### Step 3: Install PhoneDesk on the PC

1. Put the `PhoneDesk` folder somewhere permanent, for example `Documents\PhoneDesk`. The shortcuts point to this folder. If you move it later, run `Install.cmd` again.
2. Double-click **`Install.cmd`**. It:
   - finds scrcpy and adb (included in the folder),
   - creates a **PhoneDesk** shortcut on the Desktop and in the Start menu,
   - checks that the phone is connected.
3. Answer **Y** to "Start PhoneDesk now?".

> **Windows SmartScreen / "Windows protected your PC":** click **More info > Run anyway**. The scripts are plain text, so you can open them in Notepad and read them first.

### Step 4: Use it

- A blue monitor icon appears in the **system tray** (bottom-right; it may be under the **^** arrow). Drag it onto the taskbar to keep it visible.
- The desktop window opens by itself when the phone is connected and unlocked.
- Next time, just plug the phone in. If PhoneDesk isn't running, open it from the **PhoneDesk** Desktop or Start menu shortcut.
- If you want it always ready, turn on: tray icon > **Options > Start PhoneDesk with Windows**.

---

## Using the desktop

| Action | How |
|---|---|
| Open an app | **Double-click** a desktop icon, or **single-click** an app in the taskbar or app drawer (the grid icon) |
| **Minimize / maximize / close a window** | Use the grey bar just above each window: **— minimize**, **[] maximize** (click again to restore), **x close**. The app name is shown on the left |
| Bring back a minimized app | Open it again: desktop icon, taskbar or app drawer. It returns where it was |
| Move / resize a window | Drag the bar at the top of the window / drag its edges |
| Type | Click a text box and type on your PC keyboard. To show the phone's on-screen keyboard instead, turn on **tray > On-screen keyboard on desktop**. Turning it on or off restarts the desktop, so open apps move to the phone; open them again on the desktop |
| Context menu | **Right-click** |
| Back / Home | Taskbar buttons, or the mouse's side buttons |
| Copy / paste | **Ctrl+C / Ctrl+V**, shared between the PC and the phone |
| Copy a file to the phone | **Drag it onto the desktop window**. It goes to the phone's `Download` folder |
| Install an APK | Drag the `.apk` file onto the desktop window |

### Keyboard shortcuts

| Keys | Action |
|---|---|
| **Alt+F** | Full screen on / off |
| **Alt+O** | Turn the phone's own screen off (**Alt+Shift+O** turns it back on) |
| **Alt+H** / **Alt+B** | Home / Back |
| **Alt+S** | Recent apps |
| **Alt+Up / Alt+Down** | Volume |

### Tray menu (right-click the tray icon)

| Item | What it does |
|---|---|
| **Open / Show desktop** | Opens the desktop, or brings its window to the front. Left-clicking the icon does the same |
| **Close desktop** | Closes the desktop. Open apps move back to the phone |
| **Move phone app to desktop** | Takes the app you're using on the phone and puts it on the desktop as a window |
| **Send desktop app to phone** | Moves the front desktop window back to the phone |
| **Screen size** | 1280x720, 1600x900, 1920x1080 (default), 2560x1440, or your PC screen's size |
| **Text size** | Small / Normal / Large / Extra large (screen density 140 / 160 / 200 / 240 dpi) |
| **On-screen keyboard on desktop** | ON / OFF. ON (default for a new install) shows the phone keypad on the desktop when you click a text box. OFF hides it so you type with your PC keyboard |
| **Options** | Start in full screen; play phone sound on the PC; show the minimize / maximize / close bar on windows; turn the phone screen off while the desktop is open; open the desktop when the phone is plugged in; start PhoneDesk with Windows |
| **Help and shortcuts** | A quick reference |
| **Restore phone settings** | Puts back the phone setting PhoneDesk changed (see below) |
| **Exit** | Closes the desktop and PhoneDesk |

Changing the screen size, text size, sound or keyboard option restarts the desktop. Your open apps move to the phone when that happens.

---

## What PhoneDesk changes

**On the phone**
- It sets one developer option, **"Force activities to be resizable"** (`force_resizable_activities = 1`), so every app can be used as a resizable window. The original value is saved first. It's put back by **Restore phone settings** or `Uninstall.cmd`.
- While the desktop is open, the phone stays awake (it's plugged in anyway). This is undone automatically when the desktop closes.
- The desktop itself is a temporary second screen. It disappears when you close the desktop or unplug.

**On the PC**
- Shortcuts: Desktop, Start menu, and Startup (only if you turn that option on).
- Settings and a log in `%LOCALAPPDATA%\PhoneDesk\`.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| Tray says **"Phone not connected"** | Use a data cable and try another USB port. Check that USB debugging is on. Run `scrcpy\adb.exe devices` in the PhoneDesk folder; the phone should show as `device` |
| Tray says **"Allow USB debugging on the phone"** | Unlock the phone and tap **Allow**. If there's no prompt: **Developer options > Revoke USB debugging authorizations**, then reconnect |
| Desktop is black / blank | Unlock the phone. Close the desktop from the tray and open it again |
| Nothing happens when I close the window | That's intended. It won't reopen until you choose **Open desktop** or plug the phone in again |
| An app opens full-screen instead of as a window | Close it and open it again from the desktop. Some apps (games, camera) insist on full screen |
| No minimize / close buttons | The bar with the buttons sits just above each window. If it's missing, turn on tray > Options > **Show minimize / maximize / close bar on windows** |
| On-screen keyboard doesn't appear | Tray > **On-screen keyboard on desktop** must say **ON**. Click inside the text box once more |
| On-screen keyboard is too big | On the keyboard's toolbar click **... > Mode > Floating keyboard**. Drag its bottom bar to move it. Use **... > Keyboard size** to resize it or make it see-through. If your phone's own keyboard also turns floating, switch it back on the phone with **... > Mode > Standard** |
| Video apps (Netflix, Prime Video) show a black window | Protected (DRM) video can't be shown on a mirrored screen. This is a limitation of Android |
| No sound on the PC | Tray > **Options > Play phone sound on this PC**. Needs Android 11 or newer |
| Blurry or laggy | Pick a smaller **Screen size**, or a larger **Text size** if things look tiny |
| Desktop won't start (error message) | Read the log at `%LOCALAPPDATA%\PhoneDesk\scrcpy.log`. Close other scrcpy or Android tools and try again |
| `adb server version doesn't match` | Another adb (Android Studio or platform-tools) is running. Close it, or put that adb first in your PATH. PhoneDesk uses whichever adb is on PATH |
| I moved the PhoneDesk folder | Run `Install.cmd` again to fix the shortcuts |

**Run it with visible output (for debugging):**

```bat
powershell -NoProfile -ExecutionPolicy Bypass -File PhoneDesk.ps1
```

---

## Uninstall

1. Connect the phone, so its setting can be restored.
2. Double-click **`Uninstall.cmd`**. It closes PhoneDesk, restores the phone setting, and removes the shortcuts and `%LOCALAPPDATA%\PhoneDesk`.
3. Delete the `PhoneDesk` folder.

If the phone isn't available, you can restore the setting later on the phone: **Developer options > Force activities to be resizable > Off**.

---

## How it works

1. `scrcpy --new-display=1920x1080/160` creates a **virtual second screen** on the phone and streams it to a window on the PC. Mouse and keyboard input go back to the phone.
2. One UI treats that screen like an external monitor. It starts its DeX launcher on it (`com.honeyspace.dexservice.SecondaryLauncher`), which provides the taskbar and app drawer.
3. PhoneDesk runs `cmd window set-display-windowing-mode -d <id> 5`. This switches that screen to **freeform** mode, so apps open as windows.
4. `am display move-stack` moves apps between the phone's screen (display 0) and the desktop.
5. scrcpy is started with `--no-vd-destroy-content`, so apps survive the desktop closing and return to the phone.
