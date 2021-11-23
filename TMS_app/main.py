#!/usr/bin/env python

# from GUI import View
from Application import View
from controller import Controller
from model import Model
from queue import Queue
from logger import logger_setup
import tkinter as tk

def main():
    gui_log_queue = logger_setup()

    ctrl_model_queue = Queue()
    ctrl_gui_queue = Queue()
    model_ctrl_queue = Queue()
    model_gui_queue = Queue()
    gui_ctrl_queue = Queue()
    gui_model_queue = Queue()

    model = Model(ctrl_model_queue=ctrl_model_queue, model_ctrl_queue=model_ctrl_queue, model_gui_queue=model_gui_queue,
                  gui_model_queue=gui_model_queue)
    controller = Controller(ctrl_model_queue=ctrl_model_queue, ctrl_gui_queue=ctrl_gui_queue,
                            model_ctrl_queue=model_ctrl_queue, gui_ctrl_queue=gui_ctrl_queue)
    gui_queues = {'log_stream':gui_log_queue,
                  'ctrl_gui_queue':ctrl_gui_queue,
                  'model_gui_queue':model_gui_queue,
                  'gui_ctrl_queue':gui_ctrl_queue,
                  'gui_model_queue':gui_model_queue}
    # tkinter_gui = View(log_stream=gui_log_queue, ctrl_gui_queue=ctrl_gui_queue,
    #                    model_gui_queue=model_gui_queue, gui_ctrl_queue=gui_ctrl_queue, gui_model_queue=gui_model_queue)

    root = tk.Tk()
    View(root, gui_queues).pack(side="top",fill='both',expand=True)
    root.mainloop()

if __name__ == '__main__':
    main()
