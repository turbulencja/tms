#!/usr/bin/env python

import tkinter
import logging
import threading
import matplotlib
import matplotlib.ticker as mtick
import matplotlib.patches as patches
import tms_exceptions as tms_exc
from tkinter import filedialog, messagebox, scrolledtext, ttk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from queue import Empty
from seaborn import set_theme
matplotlib.use('TkAgg')


class View(tkinter.Frame):
    seaborn_colors = ['#4878d0', '#ee854a', '#6acc64', '#d65f5f', '#956cb4',
                      '#8c613c', '#dc7ec0', '#797979', '#d5bb67', '#82c6e2']
    micro = 10**(-3)

    def __init__(self, parent, arg_dict):
        tkinter.Frame.__init__(self, parent)
        self.parent = parent
        self.log_q = arg_dict['log_stream']
        self.gui_model_q = arg_dict['gui_model_queue']
        self.model_gui_q = arg_dict['model_gui_queue']

        self.opto_frame = None
        self.duck_frame = None
        self.param_frame = None
        self.analysis_frame = None

        # data structures
        self.optical_data = None
        self.ec_data = None
        self.ec_range = None

        self.setup_window()
        logging.info("GUI running thread {}".format(threading.get_ident()))


    def setup_window(self):
        self.setup_frames()
        self.after(401, self.poll_data_queue)

    def poll_data_queue(self):
        # Check every 400ms if there is a new message in the queue
        while True:
            try:
                record = self.model_gui_q.get(block=False)
            except Empty:
                break
            else:
                if record[0] == "draw ec":
                    pass
                elif record[0] == "draw opto":
                    pass
                else:
                    logging.info("unrecognized order from ctrl: {}".format(record))
        self.after(400, self.poll_data_queue)

    def setup_frames(self):
        self.duck_frame = DuckFrame(self, borderwidth = 1)
        self.opto_frame = OptoFrame(self, borderwidth = 1)
        self.analysis_frame = AnalysisFrame(self, borderwidth = 1)
        self.param_frame = ParamFrame(self, borderwidth = 1)

        self.duck_frame.grid(row=0, column=0)
        self.opto_frame.grid(row=0, column=1)
        self.analysis_frame.grid(row=1, column=0)
        self.param_frame.grid(row=1, column=1)


class DuckFrame(tkinter.Frame):
    def __init__(self, root, *args, **kwargs):
        tkinter.Frame.__init__(self, root, *args, **kwargs)
        self.root = root
        label = ttk.Label(text='duck')
        label.pack()
        # ec_file_button = ttk.Button(self, text="Browse for ec data", command=self.askopenfile_ec_csv)
        # ec_file_button.pack(side=tkinter.BOTTOM)

    def askopenfile_ec_csv(self):
        filename = filedialog.askopenfilename(initialdir="/", title="Select file",
                                              filetypes=(("csv files", "*.csv"), ("all files", "*.*")))
        if not filename:
            pass
        else:
            self.root.gui_model_q.put(("load ec file", filename))

class OptoFrame(tkinter.Frame):
    def __init__(self, root, *args, **kwargs):
        tkinter.Frame.__init__(self, root, *args, **kwargs, bg='blue')
        self.root = root
        label = ttk.Label(text='opto')
        label.pack()

    def setup(self):
        pass

    def askopenfile_opto(self):
        filename = filedialog.askopenfilename(initialdir="/", title="Select file",
                                              filetypes=(("csv files", "*.csv"), ("all files", "*.*")))
        if not filename:
            pass
        else:
            self.root.gui_ctrl_q.put(("load opto file", filename))


class ParamFrame(tkinter.Frame):
    def __init__(self, root, *args, **kwargs):
        tkinter.Frame.__init__(self, root, *args, **kwargs)
        label = ttk.Label(text='param')
        label.pack()


class AnalysisFrame(tkinter.Frame):
    def __init__(self, root, *args, **kwargs):
        tkinter.Frame.__init__(self, root, *args, **kwargs)
        label = ttk.Label(text='anlys')
        label.pack()


class Plot:
    def __init__(self, width=5, height=4):
        self.f = Figure(figsize=(width, height), dpi=125)
        self.a = self.f.add_subplot(111)
        self.f.set_facecolor('lightgray')
        self.f.subplots_adjust(left=0.16, bottom=0.15, right=0.93)

    def update_axes_opto(self):
        self.a.cla()
        self.a.set_xlabel('Wavelength [nm]')
        self.a.set_ylabel('kCounts [-]')

    def update_axes_ech(self):
        self.a.cla()
        self.a.set_xlabel('Potential [V]')
        self.a.set_ylabel('Current [A]')

    def update_axes_anlys(self):
        self.a.cla()
        self.a.set_xlabel('Potential [V]')
        self.a.set_ylabel('lbd [nm]')

        #twinx



if __name__ == '__main__':
    pass
