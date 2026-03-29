"""
Create GoAI desktop shortcut
"""
import os
import sys

def create_shortcut():
    try:
        import win32com.client
        shell = win32com.client.Dispatch("WScript.Shell")
        desktop = shell.SpecialFolders("Desktop")
        lnk_path = os.path.join(desktop, "GoAI 围棋AI.lnk")

        exe_path  = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dist", "GoAI.exe")
        work_dir  = os.path.dirname(os.path.abspath(__file__))
        icon_path = os.path.join(work_dir, "goai.ico")

        shortcut = shell.CreateShortCut(lnk_path)
        shortcut.Targetpath      = exe_path
        shortcut.WorkingDirectory = work_dir
        shortcut.IconLocation    = icon_path + ",0"
        shortcut.Description     = "GoAI 围棋AI — KataGo + RTX 5090"
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
        print("请手动将 dist\\GoAI.exe 发送到桌面快捷方式")
