$ErrorActionPreference = 'SilentlyContinue'

$python = "..\..\.venv\Scripts\python.exe"

$wtCmd = "wt -w 0 "
# First tab for control and logs
$wtCmd += "`"new-tab`" --title `"Courier Control`" -d `"C:\Users\lol\2026-workspace\2026-courier`" "
$wtCmd += "`; `"split-pane`" --title `"Courier Logs`" -d `"C:\Users\lol\2026-workspace\2026-courier`" "

$slotId = 1
for ($tab = 1; $tab -le 8; $tab++) {
    $title1 = "MUSE-{0:D2}" -f $slotId
    $wtCmd += "`; `"new-tab`" --title `"Group $tab`" -d `"C:\Users\lol\2026-workspace\2026-courier\scripts\windows_muse_wall`" $python watcher.py $title1 "
    $slotId++

    for ($pane = 2; $pane -le 8; $pane++) {
        $title2 = "MUSE-{0:D2}" -f $slotId
        $wtCmd += "`; `"split-pane`" -d `"C:\Users\lol\2026-workspace\2026-courier\scripts\windows_muse_wall`" $python watcher.py $title2 "
        $slotId++
    }
}

Invoke-Expression $wtCmd
