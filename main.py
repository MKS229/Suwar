"""Suwar Irrigation System - run this file:  python main.py"""
import tkinter as tk
from tkinter import messagebox

from suwar import config
from suwar.gui import SuwarApp
from suwar.mysql_repository import DatabaseError, MySQLRepository
from suwar.controller import SystemController


def main():
    root = tk.Tk()
    repo = MySQLRepository(config.DB_CONFIG)
    try:
        repo.check_connection()
        controller = SystemController(repo)
        controller.initialize_system()
    except DatabaseError as exc:
        messagebox.showerror(
            "Suwar - database error",
            f"{exc}\n\nChecklist:\n"
            "1. Is MySQL running?\n"
            "2. Did you run  python setup_database.py ?\n"
            "3. Are the user/password in suwar/config.py correct?")
        root.destroy()
        return
    SuwarApp(root, controller)
    root.mainloop()


if __name__ == "__main__":
    main()
