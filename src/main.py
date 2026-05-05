import ctypes 
from gui import GUI

def main():
    GUI()

if __name__ == "__main__":
    if hasattr(ctypes, "windll"):
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Daily Dose of Cosmos") # Set the taskbar icon of the application
    main()
