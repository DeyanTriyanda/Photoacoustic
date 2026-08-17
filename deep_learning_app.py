"""
Aplikasi Deep Learning mandiri (opsional).
Tab yang sama juga ada di python main.py → tab "Deep Learning".
"""

import tkinter as tk

from frontend.deep_learning_widget import DeepLearningWidget


class DeepLearningApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Deep Learning - Citra Fotoakustik")
        self.minsize(700, 480)
        widget = DeepLearningWidget(self)
        widget.pack(fill="both", expand=True, padx=6, pady=6)


def run():
    app = DeepLearningApp()
    app.mainloop()


if __name__ == "__main__":
    run()
