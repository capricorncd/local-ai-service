"""Move generated task directories into the OS trash; never fall back to unlink."""
import os
from pathlib import Path


def recycle_directory(directory):
    directory = Path(directory).resolve(strict=True)
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
