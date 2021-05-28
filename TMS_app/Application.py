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


class View:
    seaborn_colors = ['#4878d0', '#ee854a', '#6acc64', '#d65f5f', '#956cb4',
                      '#8c613c', '#dc7ec0', '#797979', '#d5bb67', '#82c6e2']
    micro = 10**(-3)

    def __init__(self, **kwargs):
        self.log_q = kwargs['log_stream']

        self._gui_ctrl_q = kwargs['gui_ctrl_queue']
        self._ctrl_gui_q = kwargs['ctrl_gui_queue']
        self._gui_model_q = kwargs['gui_model_queue']
        self._model_gui_q = kwargs['model_gui_queue']

        self.opto_frame = None
        self.duck_frame = None
        self.param_frame = None

        # data structures
        self.optical_data = None
        self.ec_data = None
        self.ec_range = None

        self.window = tkinter.Tk()
        self.window.title("TechMatStrateg")
        self.window.minsize(width=1200, height=400)
        self.setup_window()
        logging.info("GUI running thread {}".format(threading.get_ident()))

        self.window.mainloop()

    def poll_data_queue(self):
        # Check every 400ms if there is a new message in the queue
        while True:
            try:
                record = self._model_gui_q.get(block=False)
            except Empty:
                break
            else:
                if record[0] == "draw ec":
                    self.ec_data = record[1]
                    self.electrochemical_teardown()
                    self.draw_electrochemical()
                elif record[0] == "draw opto":
                    self.optical_data = record[1]
                    self.opto_teardown()
                    self.draw_optical()
                else:
                    logging.info("unrecognized order from ctrl: {}".format(record))
        self.window.after(400, self.poll_data_queue)

    def setup_frames(self):
        self.topframe = tkinter.Frame(self.window, pady=3)
        self.bottomframe = tkinter.Frame(self.window, pady=3)

        # self.duckframe = tkinter.Frame(self.topframe)
        # self.optoframe = tkinter.Frame(self.topframe)
        # self.minframe = tkinter.Frame(self.topframe)

        self.duck_frame = DuckFrame(self.topframe)
        self.opto_frame = OptoFrame(self.topframe)
        self.param_frame = ParamFrame(self.topframe)

        self.top_duckframe = tkinter.Frame(self.topframe)
        self.top_optoframe = tkinter.Frame(self.topframe)
        self.top_minframe = tkinter.Frame(self.topframe)

        self.bottom_optoframe = tkinter.Frame(self.optoframe)

        set_theme()

        self.topframe.pack(side=tkinter.TOP)
        self.bottomframe.pack(side=tkinter.BOTTOM)

        self.duckframe.grid(row=1, column=0)
        self.optoframe.grid(row=1, column=1)
        self.minframe.grid(row=1, column=2)

        self.top_duckframe.grid(row=0, column=0)
        self.top_optoframe.grid(row=0, column=1)
        self.top_minframe.grid(row=0, column=2)

        self.bottom_optoframe.pack(side=tkinter.BOTTOM)

    def setup_window(self):
        self.setup_frames()
        self.setup_logger()

        self.setup_duck_frame()
        self.setup_opto_frame()
        self.setup_min_frame()

        self.window.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.window.after(100, self.poll_log_queue)
        self.window.after(401, self.poll_data_queue)

    def askopenfile_ref(self):
        logging.info("loading reference file: not operational yet")
        # filename = filedialog.askopenfilename(initialdir="/", title="Select file",
        #                                       filetypes=(("csv files", "*.csv"), ("all files", "*.*")))
        # if not filename:
        #     pass
        # else:
        #     self._gui_ctrl_q.put(("load ref file", filename))

    def setup_logger(self):
        self.logger_text = scrolledtext.ScrolledText(self.bottomframe, state='disabled', height=8)
        self.logger_text.tag_config('INFO', foreground='black')
        self.logger_text.tag_config('DEBUG', foreground='gray')
        self.logger_text.tag_config('WARNING', foreground='orange')
        self.logger_text.tag_config('ERROR', foreground='red')
        self.logger_text.tag_config('CRITICAL', foreground='red', underline=1)
        self.logger_text.grid()

    def askopenfile_opto(self):
        filename = filedialog.askopenfilename(initialdir="/", title="Select file",
                                              filetypes=(("csv files", "*.csv"), ("all files", "*.*")))
        if not filename:
            pass
        else:
            self._gui_ctrl_q.put(("load opto file", filename))

    def askopenfile_db(self):
        filename = filedialog.askopenfilename(initialdir="/", title="Select file",
                                              filetypes=(("sqlite3 files", "*.sqlite3"), ("all files", "*.*")))
        if not filename:
            pass
        else:
            self._gui_ctrl_q.put(("load db file", filename))

    def on_closing(self):
        if messagebox.askokcancel("Quit", "Do you want to quit?"):
            logging.info("Bye")
            self.window.destroy()

    def display_log(self, record):
        self.logger_text.configure(state='normal')
        self.logger_text.insert(tkinter.END, record)
        self.logger_text.configure(state='disabled')
        # Autoscroll to the bottom
        self.logger_text.yview(tkinter.END)

    def poll_log_queue(self):
        # Check every 100ms if there is a new message in the queue to display
        while True:
            record = self.log_q.get()
            if record is None:
                break
            else:
                self.display_log(record)
        self.window.after(100, self.poll_log_queue)


class DuckFrame(tkinter.Frame):
    def __init__(self, root, *args, **kwargs):
        tkinter.Frame.__init__(self, root, *args, **kwargs)
        self.duck_figure = None
        self.duck_bg = None
        self.duck_dr = None
        self.duck_slider_v = None
        self.duck_slider_ua = None
        self.current_from_slider = None
        self.voltage_from_slider = None
        self.current_from_dr = None
        self.voltage_from_dr = None
        self.current_max_label = None
        self.current_min_label = None
        self.voltage_max_label = None
        self.voltage_min_label = None

    def setup_duck_frame(self):
        self.duck_figure = Figure(figsize=(4, 3))
        self.duck_figure.patch.set_facecolor('#f0f0f0')
        canvas = FigureCanvasTkAgg(self.duck_figure, master=self.top_duckframe)
        canvas.get_tk_widget().pack(side=tkinter.RIGHT)
        canvas.draw()

        self.duck_slider_v = ttk.Scale(self.duckframe, length=350, from_=-0.5, to_=1.5)
        self.duck_slider_ua = ttk.Scale(self.top_duckframe, length=250, from_=-0.5, to_=1.5, orient=tkinter.VERTICAL)

        self.duck_slider_v.pack()
        self.duck_slider_ua.pack(side=tkinter.LEFT)

        ec_file_button = ttk.Button(self.duckframe, text="Browse for database", command=self.askopenfile_db)
        ec_file_button.pack(side=tkinter.BOTTOM)

        # label_vertical
        # label horizontal


class OptoFrame(tkinter.Frame):
    def __init__(self, root, *args, **kwargs):
        tkinter.Frame.__init__(self, root, *args, **kwargs)
        self.opto_figure = None
        self.opto_bg = None
        self.lambda_from_slider = None
        self.opto_slider = None
        self.lambda_label = None

    def setup(self):
        self.opto_figure = Figure(figsize=(5, 3))
        self.opto_figure.patch.set_facecolor('#f0f0f0')
        canvas = FigureCanvasTkAgg(self.opto_figure, master=self.top_optoframe)
        canvas.get_tk_widget().pack(side=tkinter.LEFT)
        canvas.draw()

        self.opto_slider = ttk.Scale(self.optoframe, from_=344, to_=1041, length=300)
        self.opto_slider.pack()

        optical_file_button = ttk.Button(self.bottom_optoframe,
                                         text="Redraw",
                                         command=self.redraw_opto)
        optical_reference_button = ttk.Button(self.bottom_optoframe,
                                              text="Browse for optical reference",
                                              command=self.askopenfile_ref)

        optical_file_button.pack(side=tkinter.LEFT, padx=3)
        optical_reference_button.pack(side=tkinter.RIGHT, padx=3)


class ParamFrame(tkinter.Frame):
    def __init__(self, root, *args, **kwargs):
        tkinter.Frame.__init__(self, root, *args, **kwargs)
        self.min_figure = None
        self.param_option_string = None




if __name__ == '__main__':
    pass
