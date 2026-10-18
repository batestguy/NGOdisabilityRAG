"""OS-level keystrokes via SendInput, so NVDA's keyboard hook sees them.
usage: python oskeys.py "insert+down" "tab" "h" ...   (each arg = one chord)
"""
import ctypes, sys, time

VK = {"insert": 0x2D, "down": 0x28, "up": 0x26, "tab": 0x09, "shift": 0x10, "enter": 0x0D,
      "escape": 0x1B, "space": 0x20, "control": 0x11, "home": 0x24, "end": 0x23, "f6": 0x75}
EXT = {0x2D, 0x28, 0x26, 0x24, 0x23}


def vk(name):
    return VK[name] if name in VK else ord(name.upper())


def press(code, up=False):
    flags = (0x0001 if code in EXT else 0) | (0x0002 if up else 0)
    scan = ctypes.windll.user32.MapVirtualKeyW(code, 0)
    ctypes.windll.user32.keybd_event(code, scan, flags, 0)


for chord in sys.argv[1:]:
    if chord.startswith("sleep:"):
        time.sleep(float(chord[6:]))
        continue
    keys = [vk(k) for k in chord.split("+")]
    for k in keys:
        press(k)
        time.sleep(0.03)
    for k in reversed(keys):
        press(k, up=True)
        time.sleep(0.03)
    time.sleep(0.25)
