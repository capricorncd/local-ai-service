"""Move generated task directories into the OS trash; never fall back to unlink."""
import os
import time
from pathlib import Path


# Shell reports source/destination sharing violations as HRESULTs.
_SHARING_ERRORS = {32, 33, 0x80070020, 0x80070021, 0x80270027, 0x80270028}


def _is_sharing_violation(error):
    codes = [getattr(error, 'hresult', None), getattr(error, 'winerror', None)]
    if error.args:
        codes.append(error.args[0])
    return any(isinstance(code, int) and (code & 0xffffffff) in _SHARING_ERRORS for code in codes)


def recycle_directory(directory):
    directory = Path(directory).resolve(strict=True)
    for attempt, delay in enumerate((0, .15, .3, .6, 1.2)):
        if delay:
            time.sleep(delay)
        try:
            _recycle_once(directory)
            return
        except Exception as error:
            if not _is_sharing_violation(error):
                raise
            if attempt == 4 or not directory.exists():
                raise OSError('目录或文件仍被占用，请停止播放或关闭占用该目录的程序后重试。') from error


def _recycle_once(directory):
    if os.name != 'nt':
        from send2trash import send2trash
        send2trash(str(directory))
    else:
        import pythoncom
        from win32com.shell import shell, shellcon
        from send2trash.win.IFileOperationProgressSink import FileOperationProgressSink

        class RecycleOnlySink(FileOperationProgressSink):
            def PreDeleteItem(self, flags, item):
                if not flags & shellcon.TSF_DELETE_RECYCLE_IF_POSSIBLE:
                    raise pythoncom.com_error(-2147467259, 'Recycle Bin unavailable', None, None)
                return 0

        pythoncom.CoInitialize()
        try:
            operation = pythoncom.CoCreateInstance(shell.CLSID_FileOperation, None,
                pythoncom.CLSCTX_ALL, shell.IID_IFileOperation)
            operation.SetOperationFlags(shellcon.FOF_NOCONFIRMATION | shellcon.FOF_NOERRORUI |
                shellcon.FOF_SILENT | shellcon.FOFX_EARLYFAILURE | 0x20000000 | 0x00080000)
            sink = pythoncom.WrapObject(RecycleOnlySink(), shell.IID_IFileOperationProgressSink)
            item = shell.SHCreateItemFromParsingName(str(directory), None, shell.IID_IShellItem)
            operation.DeleteItem(item, sink)
            result = operation.PerformOperations()
            if result or operation.GetAnyOperationsAborted():
                raise OSError('系统未完成回收站操作')
        finally:
            pythoncom.CoUninitialize()
    if directory.exists():
        raise OSError('生成目录仍存在，请稍后重试')
