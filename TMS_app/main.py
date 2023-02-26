#!/usr/bin/env python

from Application import View
from model import Model
from queue import Queue
from logger import logger_setup
import tkinter as tk


def main():
    gui_log_queue = logger_setup()

    model_gui_queue = Queue()
    gui_model_queue = Queue()

    model = Model(model_gui_queue=model_gui_queue,
                  gui_model_queue=gui_model_queue)
    gui_queues = {'log_stream': gui_log_queue,
                  'model_gui_queue': model_gui_queue,
                  'gui_model_queue': gui_model_queue}

    root = tk.Tk()
    View(root, gui_queues).pack(side="top", fill='both', expand=True)
    root.mainloop()


if __name__ == '__main__':
    main()
