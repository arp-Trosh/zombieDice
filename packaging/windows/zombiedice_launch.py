"""Starts Zombie Dice inside the Windows release.

The release's ZombieDice.exe is python.exe from the official embeddable Python
package, renamed. It is Microsoft-trusted, signed by the Python Software
Foundation, so neither SmartScreen nor Defender has an unknown program to warn
about. Renaming leaves the signature intact.

python.exe runs a program named on its command line, but a double-clicked exe
gets no arguments, so the game starts from here instead: ZombieDice._pth turns
on the site module, site runs every .pth file in Lib/site-packages, and
zombiedice.pth there says `import zombiedice_launch`. We then run the game and
exit, before Python would reach its interactive prompt.

Set ZOMBIEDICE_SELFTEST=1 to render a few frames off-screen and print a report
instead (the release build runs this to check the package works).
"""
import os
import sys
import traceback


def loaded_dll(name):
    """Full path of a DLL loaded into this process, or None (Windows only)."""
    import ctypes
    from ctypes import wintypes
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.GetModuleHandleW.restype = wintypes.HMODULE
    k32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
    k32.GetModuleFileNameW.argtypes = [wintypes.HMODULE, wintypes.LPWSTR, wintypes.DWORD]
    handle = k32.GetModuleHandleW(name)
    if not handle:
        return None
    buf = ctypes.create_unicode_buffer(1024)
    k32.GetModuleFileNameW(handle, buf, len(buf))
    return buf.value


def selftest():
    import time

    import numba
    import numpy as np

    import unicode3d
    from unicode3d.console import WindowsConsole
    from unicode3d.terminal import Screen
    from zombie.graphics import DiceTray, KeptDice
    from zombie.horde import Graveyard, LobbyTable
    from zombie.rules import BRAIN, FEET, GREEN, RED, SHOTGUN, YELLOW

    print(f"Python {sys.version.split()[0]} at {sys.executable}; numpy {np.__version__}, numba {numba.__version__}, "
          f"unicode3d {unicode3d.__version__}")
    start = time.perf_counter()
    unicode3d.compile_kernels()
    print(f"  kernels compiled or loaded in {time.perf_counter() - start:.1f} s, on {numba.get_num_threads()} threads "
          f"({numba.threading_layer()} threading layer)")
    if os.name == "nt":
        # Numba needs the C++ runtime and, for its OpenMP thread pool, the OpenMP runtime: both must be
        # the release's own copies, or PCs without the Visual C++ Redistributable would fail to start
        # (MSVCP140) or run on another thread pool than the one tested here (VCOMP140).
        here = os.path.dirname(os.path.abspath(sys.executable))
        for dll in ("msvcp140.dll", "vcomp140.dll"):
            path = loaded_dll(dll)
            print(f"  {dll}: {path}")
            assert path and os.path.dirname(os.path.abspath(path)).lower() == here.lower(), path
        assert numba.threading_layer() == "omp", numba.threading_layer()
    dice = [(GREEN, BRAIN), (YELLOW, FEET), (RED, SHOTGUN)]
    for glyphs in ("half", "quad", "sextant", "ascii"):
        for color in ("truecolor", "256", "16"):
            screen = Screen(glyphs=glyphs, color=color, size=(40, 120))
            yard, tray, kept, table = Graveyard(seed=1), DiceTray(np.random.default_rng(1)), KeptDice(), LobbyTable()
            yard.update(2.0)
            yard.render(screen, 0, 0, 100, 18, 8)
            tray.set_cup({GREEN: 3, YELLOW: 2, RED: 2})
            tray.roll(dice)
            tray.update(10.0)
            tray.render(screen, 18, 12, 70, 16)
            kept.render(screen, 18, 0, 12, 21, dice)
            table.seat([{"name": "Smoke", "bot": False}], 3, lambda name: 0)
            table.render(screen, 34, 12, 70, 6)
            drawn = int((screen.chars != " ").sum())
            out = screen.render_updates()
            assert drawn > 500 and len(out) > 1000, (glyphs, color, drawn, len(out))
        print(f"  {glyphs:8} ok ({drawn} cells drawn)")
    if os.name == "nt":
        WindowsConsole()  # the console API bindings load
    print("SELFTEST OK")
    return 0


def play():
    # The exe can't take command-line options (python.exe would read them), so they come from the environment.
    sys.argv = ["ZombieDice"]
    if os.environ.get("ZOMBIEDICE_NAME"):
        sys.argv += ["--name", os.environ["ZOMBIEDICE_NAME"]]
    from zombie.__main__ import main
    main()
    return 0


def launch():
    try:
        code = selftest() if os.environ.get("ZOMBIEDICE_SELFTEST") else play()
    except SystemExit as e:
        code = e.code if isinstance(e.code, int) else (0 if e.code is None else 1)
    except BaseException:
        traceback.print_exc()
        code = 1
        if not os.environ.get("ZOMBIEDICE_SELFTEST"):
            try:
                input("\nZombie Dice stopped with the error above. Press Enter to close this window.")
            except BaseException:
                pass
    sys.stdout.flush()
    sys.stderr.flush()
    # We are still inside Python's startup (the site module); leave now, rather than
    # returning into it and on to the interactive prompt.
    os._exit(code)


launch()
