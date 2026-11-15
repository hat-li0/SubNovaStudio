import os
import sys
import subprocess

def create_shortcut():
    desktop = os.path.normpath(os.path.expanduser("~/Desktop"))
    path = os.path.join(desktop, "SubNova Studio.lnk")
    
    python_dir = os.path.dirname(sys.executable)
    pythonw_exe = os.path.join(python_dir, "pythonw.exe")
    if not os.path.exists(pythonw_exe):
        pythonw_exe = sys.executable
    
    current_dir = os.path.dirname(os.path.abspath(__file__))
    onedir_exe = os.path.join(current_dir, "dist", "SubNovaStudio", "SubNovaStudio.exe")
    onefile_exe = os.path.join(current_dir, "dist", "SubNovaStudio_Standalone.exe")
    legacy_exe = os.path.join(current_dir, "dist", "SubNovaStudio.exe")
    target_script = os.path.join(current_dir, "main.py")
    icon_file = os.path.join(current_dir, "app", "resources", "icons", "subnova_icon.ico")
    
    if os.path.exists(onedir_exe):
        target_path = onedir_exe
        args_str = ""
        icon_location = f"{onedir_exe},0"
        work_dir = os.path.dirname(onedir_exe)
    elif os.path.exists(onefile_exe):
        target_path = onefile_exe
        args_str = ""
        icon_location = f"{onefile_exe},0"
        work_dir = os.path.dirname(onefile_exe)
    elif os.path.exists(legacy_exe):
        target_path = legacy_exe
        args_str = ""
        icon_location = f"{legacy_exe},0"
        work_dir = os.path.dirname(legacy_exe)
    else:
        target_path = pythonw_exe
        args_str = f'"{target_script}"'
        icon_location = f"{icon_file},0" if os.path.exists(icon_file) else sys.executable
        work_dir = current_dir

    try:
        import win32com.client
        shell = win32com.client.Dispatch("WScript.Shell")
        shortcut = shell.CreateShortCut(path)
        shortcut.Targetpath = target_path
        shortcut.Arguments = args_str
        shortcut.WorkingDirectory = work_dir
        shortcut.IconLocation = icon_location
        shortcut.Description = "SubNova Studio - AI Subtitle Translator & Improver | Hatim Alharbi 2026"
        shortcut.WindowStyle = 1
        shortcut.save()
        print(f"Shortcut created successfully at: {path}")
    except Exception:
        # Fallback using powershell safely without shell=True or os.system
        icon_arg = f';$s.IconLocation="{icon_location}"'
        args_arg = f';$s.Arguments="`"{args_str}`""' if args_str else ';$s.Arguments=""'
        cmd = f'$s=(New-Object -COM WScript.Shell).CreateShortcut("{path}");$s.TargetPath="{target_path}"{args_arg};$s.WorkingDirectory="{work_dir}"{icon_arg};$s.Description="SubNova Studio | Hatim Alharbi";$s.Save()'
        subprocess.run(["powershell", "-NoProfile", "-Command", cmd], shell=False, check=False)
        print(f"Shortcut created at: {path}")

if __name__ == "__main__":
    create_shortcut()
