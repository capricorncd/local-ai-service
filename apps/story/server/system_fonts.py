"""Read installed Windows font families through GDI, including per-user fonts."""
import os
from functools import lru_cache


@lru_cache(maxsize=1)
def system_fonts():
    if os.name != 'nt':
        return {'fonts': [], 'available': False}
    import ctypes
    from ctypes import wintypes

    class LOGFONTW(ctypes.Structure):
        _fields_ = [(name, wintypes.LONG) for name in ('height','width','escapement','orientation','weight')] + [
            (name, wintypes.BYTE) for name in ('italic','underline','strikeout','charset','outprecision','clipprecision','quality','pitchandfamily')
        ] + [('face', wintypes.WCHAR * 32)]

    callback_type = ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.POINTER(LOGFONTW), ctypes.c_void_p, wintypes.DWORD, wintypes.LPARAM)
    user = ctypes.WinDLL('user32', use_last_error=True)
    gdi = ctypes.WinDLL('gdi32', use_last_error=True)
    user.GetDC.argtypes = [wintypes.HWND]
    user.GetDC.restype = wintypes.HDC
    user.ReleaseDC.argtypes = [wintypes.HWND,wintypes.HDC]
    user.ReleaseDC.restype = ctypes.c_int
    gdi.EnumFontFamiliesExW.argtypes = [wintypes.HDC,ctypes.POINTER(LOGFONTW),callback_type,wintypes.LPARAM,wintypes.DWORD]
    gdi.EnumFontFamiliesExW.restype = ctypes.c_int
    names = set()

    @callback_type
    def collect(font, metrics, kind, data):
        name = font.contents.face
        if name and not name.startswith('@'): names.add(name)
        return 1

    dc = user.GetDC(None)
    if not dc: raise OSError('无法读取系统字体')
    try:
        query = LOGFONTW()
        query.charset = 1  # DEFAULT_CHARSET enumerates all installed charsets.
        gdi.EnumFontFamiliesExW(dc,ctypes.byref(query),collect,0,0)
    finally:
        user.ReleaseDC(None,dc)
    return {'fonts': sorted(names,key=str.casefold), 'available': True}
