#!/usr/bin/env python

import tkinter
import logging
import threading
import matplotlib
import os
import matplotlib.ticker as mtick
import matplotlib.patches as patches
import tms_exceptions as tms_exc
from tkinter import filedialog, messagebox, scrolledtext, ttk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from queue import Empty
from seaborn import set_theme
from ec_dataset import ElectroChemSet

matplotlib.use('TkAgg')


class View(tkinter.Frame):
    seaborn_colors = ['#4878d0', '#ee854a', '#6acc64', '#d65f5f', '#956cb4',
                      '#8c613c', '#dc7ec0', '#797979', '#d5bb67', '#82c6e2']
    micro = 10 ** (-3)

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

        self.initialdir = "C:/Users/aerial triceratops/PycharmProjects/TechMatStrateg/dane/"
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
            try:
                order, data = record
            except ValueError:
                logging.info("order misshap: {}".format(record))
            else:
                if order == "draw ec":
                    self.ec_data = ElectroChemSet()
                    self.ec_data.uA = data[0]
                    self.ec_data.V = data[1]
                    self.duck_frame.electrochemical_teardown()
                    self.duck_frame.draw_electrochemical()
                elif order == "opto file loaded":
                    self.gui_model_q.put(("draw opto cycle", None))
                elif order == "draw opto":
                    self.opto_frame.optical_data = data
                    self.opto_frame.opto_teardown()
                    try:
                        self.opto_frame.draw_optical()
                    except ValueError:
                        logging.error("cannot draw optical data. ec file not loaded or opto file missing cycle")
                elif order == 'number of cycles':
                    self.duck_frame.update_no_cycles(data)
                elif order == 'send ec ranges':
                    logging.info("ec range request")
                    ec_ranges = self.duck_frame.find_ec_range()
                    self.gui_model_q.put(("ec range", ec_ranges))
                else:
                    logging.info("unrecognized order from model: {}".format(record))
        self.after(400, self.poll_data_queue)

    def setup_frames(self):
        self.duck_frame = DuckFrame(self, borderwidth=1)
        self.opto_frame = OptoFrame(self, borderwidth=1)
        self.analysis_frame = AnalysisFrame(self, borderwidth=1)
        self.param_frame = ParamFrame(self, borderwidth=1)

        self.duck_frame.grid(row=0, column=0)
        self.opto_frame.grid(row=0, column=1)
        self.analysis_frame.grid(row=1, column=0)
        self.param_frame.grid(row=1, column=1)


class DuckFrame(tkinter.Frame):
    def __init__(self, root, *args, **kwargs):
        tkinter.Frame.__init__(self, root, *args, **kwargs)
        self.parent = root
        self.duck_figure = Figure(figsize=(5, 3))
        self.duck_figure.patch.set_facecolor('#f0f0f0')
        self.cycles = 1     # number of cycles
        self.current_cycle = 0
        canvas = FigureCanvasTkAgg(self.duck_figure, master=self)
        canvas.get_tk_widget().grid(row=0, column=1, rowspan=3, columnspan=2)
        canvas.draw()

        self.ec_file_button = ttk.Button(self, text="Browse for ec data", command=self.askopenfile_ec_csv)
        self.ec_file_button.grid(row=4, column=1)

        self.ec_cycle1_button = CycleButton(self, cycle=0)
        self.ec_cycle1_button.grid(row=0, column=0)
        self.ec_cycle2_button = CycleButton(self, cycle=1)
        self.ec_cycle2_button.state(["disabled"])
        self.ec_cycle2_button.grid(row=1, column=0)
        self.ec_cycle3_button = CycleButton(self, cycle=2)
        self.ec_cycle3_button.state(["disabled"])
        self.ec_cycle3_button.grid(row=2, column=0)

    def askopenfile_ec_csv(self):
        filename = filedialog.askopenfilename(initialdir=self.parent.initialdir, title="Select file",
                                              filetypes=(("csv files", "*.csv"), ("all files", "*.*")))
        if not filename:
            pass
        else:
            self.parent.gui_model_q.put(("load ec csv", filename))
            self.parent.initialdir = os.path.dirname(filename)

    def draw_electrochemical(self):
        logging.info("please wait, drawing electrochemical data")
        duck_ax = self.duck_figure.add_subplot(111)
        duck_ax.plot(self.parent.ec_data.V, self.parent.ec_data.uA)
        duck_ax.set_xlabel('U [V]')
        duck_ax.set_ylabel('I [uA]')
        self.duck_figure.tight_layout()
        self.duck_figure.canvas.draw()

    def find_ec_range(self, cycle=0):
        logging.info(f"plotting cycle {cycle+1}")
        self.current_cycle = cycle
        self.parent.gui_model_q.put(("draw ec cycle", cycle))

    def electrochemical_teardown(self):
        self.duck_figure.clf()

    def update_no_cycles(self, num_cycles):
        if num_cycles == 1:
            self.ec_cycle1_button.state(["!disabled"])
            self.ec_cycle2_button.state(["disabled"])
            self.ec_cycle3_button.state(["disabled"])
        elif num_cycles == 2:
            self.ec_cycle1_button.state(["!disabled"])
            self.ec_cycle2_button.state(["!disabled"])
            self.ec_cycle3_button.state(["disabled"])
        elif num_cycles == 3:
            self.ec_cycle1_button.state(["!disabled"])
            self.ec_cycle2_button.state(["!disabled"])
            self.ec_cycle3_button.state(["!disabled"])
        elif num_cycles > 3:
            self.ec_cycle1_button.state(["!disabled"])
            self.ec_cycle2_button.state(["!disabled"])
            self.ec_cycle3_button.state(["!disabled"])
            logging.info("more than 3 cycles")
        else:
            logging.info(f"unrecognizable cycles number: {num_cycles}")


class OptoFrame(tkinter.Frame):
    def __init__(self, root, *args, **kwargs):
        tkinter.Frame.__init__(self, root, *args, **kwargs)
        self.parent = root
        self.opto_figure = Figure(figsize=(5, 3))
        self.opto_figure.patch.set_facecolor('#f0f0f0')
        canvas = FigureCanvasTkAgg(self.opto_figure, master=self)
        canvas.get_tk_widget().grid(row=1, columnspan=2)
        canvas.draw()

        optical_file_button = ttk.Button(self,
                                         text="Redraw",
                                         command=self.redraw_opto)
        optical_reference_button = ttk.Button(self,
                                              text="Browse for optical data",
                                              command=self.askopenfile_opto_csv)

        optical_file_button.grid(row=3, column=0)
        optical_reference_button.grid(row=3, column=1)
        self.optical_data = None

    def redraw_opto(self):
        logging.info("redrawing optical data")
        # ec_range = self.find_ec_range()
        # self.parent.gui_model_q.put(("ec range", ec_range))
        self.parent.gui_model_q.put(("draw opto cycle", None))

    def opto_teardown(self):
        self.opto_figure.clf()

    def draw_optical(self):
        logging.info("please wait, drawing optical data")
        opto_ax = self.opto_figure.add_subplot(111)
        transmission, wavelength = self.optical_data.generate_data_for_plotting()
        for meas in transmission:
            opto_ax.plot(wavelength, transmission[meas])
        opto_ax.yaxis.set_major_formatter(mtick.FormatStrFormatter('%.1e'))
        opto_ax.set_xlabel('$\lambda$ [nm]')
        opto_ax.set_ylabel('T [dB]')
        self.opto_figure.tight_layout()
        self.opto_figure.canvas.draw()

    def setup(self):
        pass

    def askopenfile_opto_csv(self):
        filename = filedialog.askopenfilename(initialdir=self.parent.initialdir, title="Select file",
                                              filetypes=(("csv files", "*.csv"), ("all files", "*.*")))
        if not filename:
            pass
        else:
            self.parent.gui_model_q.put(("load opto csv", filename))
            self.parent.initialdir = os.path.dirname(filename)


class ParamFrame(tkinter.Frame):
    def __init__(self, root, *args, **kwargs):
        tkinter.Frame.__init__(self, root, *args, **kwargs)
        self.parent = root
        self.setup_logger()
        self.after(100, self.poll_log_queue)

    def setup_logger(self):
        self.logger_text = scrolledtext.ScrolledText(self, state='disabled', height=8, width=60)
        self.logger_text.tag_config('INFO', foreground='black')
        self.logger_text.tag_config('DEBUG', foreground='gray')
        self.logger_text.tag_config('WARNING', foreground='orange')
        self.logger_text.tag_config('ERROR', foreground='red')
        self.logger_text.tag_config('CRITICAL', foreground='red', underline=1)
        self.logger_text.grid()

    def display_log(self, record):
        self.logger_text.configure(state='normal')
        self.logger_text.insert(tkinter.END, record)
        self.logger_text.configure(state='disabled')
        # Autoscroll to the bottom
        self.logger_text.yview(tkinter.END)

    def poll_log_queue(self):
        # Check every 100ms if there is a new message in the queue to display
        while True:
            record = self.parent.log_q.get()
            if record is None:
                break
            else:
                self.display_log(record)
        self.after(100, self.poll_log_queue)


class CycleButton(ttk.Button):
    def __init__(self, parent, cycle):
        """
        :param parent: DuckFrame obj
        :param cycle: int with cycle number
        :param state: bool True==on, False==off
        """
        self.parent = parent
        self.cycle = cycle
        button_text = "Cycle {}".format(self.cycle+1)
        ttk.Button.__init__(self, parent, text=button_text, command=self.button_command)

    def button_command(self):
        self.parent.parent.gui_model_q.put(("draw ec cycle", self.cycle))


class AnalysisFrame(tkinter.Frame):
    def __init__(self, root, *args, **kwargs):
        self.parent = root
        tkinter.Frame.__init__(self, root, *args, **kwargs)

        self.anls_figure = Figure(figsize=(5, 3))
        self.anls_figure.patch.set_facecolor('#f0f0f0')
        canvas = FigureCanvasTkAgg(self.anls_figure, master=self)
        canvas.get_tk_widget().grid()
        canvas.draw()

        anls_redraw_button = ttk.Button(self, text="Redraw", command=self.model_send_params)
        self.param_option_string = tkinter.StringVar()
        anls_option = ttk.Combobox(self, textvariable=self.param_option_string)
        anls_option['values'] = ('λ(V)+IODM(V)', 'λ(V)', 'IODM(V)')
        anls_redraw_button.grid()
        anls_option.grid()
        anls_option.current(0)

    def model_send_params(self):
        logging.info("collecting data for plotting")
        param = self.param_option_string.get()
        # wvlgth_range = [self.lambda_start.get(), self.lambda_from_slider.get()]
        # self.parent.gui_model_q.put((param, wvlgth_range))

    def parameter_teardown(self):
        self.anls_figure.clf()

    def two_parameter_plotting(self, ec_V, iodm, lbd_min):
        self.parameter_teardown()
        min_ax = self.anls_figure.add_subplot(111)
        color = 'b'
        min_ax.plot(ec_V, lbd_min, '.', color=color)
        min_ax.set_xlabel('U [V]')
        min_ax.set_ylabel('λ [nm]', color=color)

        color = 'r'
        iodm_ax = min_ax.twinx()
        iodm_ax.plot(ec_V, iodm, '.', color=color)
        iodm_ax.set_ylabel('IODM', color=color)

        self.anls_figure.tight_layout()
        self.anls_figure.canvas.draw()

    def parameter_plotting(self, x, y):
        self.parameter_teardown()
        min_ax = self.anls_figure.add_subplot(111)
        min_ax.plot(x, y, '.')
        param = self.param_option_string.get()
        if param == 'λ(V)':
            min_ax.set_xlabel('U [V]')
            min_ax.set_ylabel('λ [nm]')
        elif param == 'λ(meas)':
            min_ax.set_xlabel('measurement [samples]')
            min_ax.set_ylabel('λ [nm]')
        elif param == 'IODM(V)':
            min_ax.set_xlabel('U [V]')
            min_ax.set_ylabel('IODM')
        elif param == 'IODM(meas)':
            min_ax.set_xlabel('measurement [samples]')
            min_ax.set_ylabel('IODM')
        self.anls_figure.tight_layout()
        self.anls_figure.canvas.draw()


class RoundedDoubleVar(tkinter.DoubleVar):

    def round_string(self):
        return "{:.2f}".format(self.get())



if __name__ == '__main__':
    pass
