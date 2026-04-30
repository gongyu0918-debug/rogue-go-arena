"""
Create rogue-go-arena desktop shortcut
"""
import os
import sys

def create_shortcut():
    try:
        import win32com.client
        shell = win32com.client.Dispatch("WScript.Shell")
        desktop = shell.SpecialFolders("Desktop")
        lnk_path = os.path.join(desktop, "rogue-go-arena.lnk")

        work_dir  = os.path.dirname(os.path.abspath(__file__))
        exe_path = os.path.join(work_dir, "rogue-go-arena.exe")
        if not os.path.exists(exe_path):
            exe_path = os.path.join(work_dir, "dist", "rogue-go-arena.exe")
        icon_path = os.path.join(work_dir, "rogue-go-arena.ico")

        shortcut = shell.CreateShortCut(lnk_path)
        shortcut.Targetpath      = exe_path
        shortcut.WorkingDirectory = work_dir
        shortcut.IconLocation    = icon_path + ",0"
        shortcut.Description     = "rogue-go-arena - KataGo arena"
        shortcut.save()
        print(f"快捷方式已创建: {lnk_path}")
        return True
    except Exception as e:
        print(f"创建快捷方式失败: {e}")
        return False

if __name__ == "__main__":
    if create_shortcut():
        print("桌面快捷方式创建成功！")
    else:
        print("请手动将 dist\\rogue-go-arena.exe 发送到桌面快捷方式")
