#!/usr/bin/env python

import tkinter
import logging
import threading
import matplotlib
import os
import matplotlib.ticker as mtick
from tkinter import filedialog, scrolledtext, ttk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from queue import Empty
from ec_dataset import ElectroChemCycle

matplotlib.use('TkAgg')


class View(tkinter.Frame):
    seaborn_colors = ['#4878d0', '#ee854a', '#6acc64', '#d65f5f', '#956cb4',
                      '#8c613c', '#dc7ec0', '#797979', '#d5bb67', '#82c6e2']
    micro = 10 ** (-3)

    def __init__(self, parent, arg_dict):
        tkinter.Frame.__init__(self, parent)
        self.parent = parent
        self.automatic_mode = False
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
                    self.ec_data = ElectroChemCycle(data[2], uA=data[0], V=data[1], id=[None, None])
                    cycle = self.cycle_number_increment(data[2])
                    self.duck_frame.electrochemical_teardown()
                    self.duck_frame.draw_electrochemical(cycle)
                elif order == "all done":
                    self.param_frame.all_done()
                elif order == "opto file loaded":
                    self.gui_model_q.put(("draw opto cycle", None))
                elif order == "draw opto":
                    self.opto_frame.optical_data = data[0]
                    cycle = self.cycle_number_increment(data[1])
                    self.opto_frame.opto_teardown()
                    try:
                        self.opto_frame.draw_optical(cycle)
                    except ValueError:
                        logging.error("cannot draw optical data. ec file not loaded or opto file missing cycle")
                elif order == 'number of cycles' and not self.automatic_mode:
                    self.param_frame.cycle_buttons.no_cycles = data
                    self.param_frame.cycle_buttons.update_no_cycles(data)
                elif order == 'number of cycles' and self.automatic_mode:
                    self.param_frame.cycle_buttons.no_cycles = data
                elif order in ['fit λ(V)', 'IODM(V)']:
                    cycle = self.cycle_number_increment(data[2])
                    self.analysis_frame.parameter_plotting(order, data[0], data[1], cycle)
                elif order == 'fit λ(V)+IODM(V)':
                    cycle = self.cycle_number_increment(data[3])
                    self.analysis_frame.two_parameter_plotting(data[0], data[1], data[2], cycle)
                else:
                    logging.info("unrecognized order from model: {}".format(record))
        self.after(400, self.poll_data_queue)

    @staticmethod
    def cycle_number_increment(cycle):
        return cycle[:-1] + str(int(cycle[-1]) + 1)

    def setup_frames(self):
        self.duck_frame = DuckFrame(self, borderwidth=1)
        self.opto_frame = OptoFrame(self, borderwidth=1)
        self.analysis_frame = AnalysisFrame(self, borderwidth=1)
        self.param_frame = ParamFrame(self, borderwidth=1)

        self.duck_frame.grid(row=0, column=0)
        self.opto_frame.grid(row=0, column=1)
        self.param_frame.grid(row=1, column=0)
        self.analysis_frame.grid(row=1, column=1)

    def set_automatic_mode(self, on):
        if on:
            self.automatic_mode = True
            self.duck_frame.automatic_mode_on()
            self.opto_frame.automatic_mode_on()
            self.analysis_frame.automatic_mode_on()
            self.param_frame.automatic_mode_on()
            logging.info("automatic mode: on")
        else:
            self.automatic_mode = False
            self.duck_frame.automatic_mode_off()
            self.opto_frame.automatic_mode_off()
            self.analysis_frame.automatic_mode_off()
            self.param_frame.automatic_mode_off()
            logging.info("automatic mode: off")


class DuckFrame(tkinter.Frame):
    def __init__(self, root, *args, **kwargs):
        tkinter.Frame.__init__(self, root, *args, **kwargs)
        self.parent = root
        self.duck_figure = Figure(figsize=(5, 3))
        self.duck_figure.patch.set_facecolor('#f0f0f0')
        self.cycles = 1  # number of cycles
        self.current_cycle = 0
        canvas = FigureCanvasTkAgg(self.duck_figure, master=self)
        canvas.get_tk_widget().grid(row=0)
        canvas.draw()

        self.ec_file_button = ttk.Button(self, text="Browse for ec data", command=self.askopenfile_ec_csv)
        self.ec_file_button.grid(row=4)

    def automatic_mode_on(self):
        self.ec_file_button.state(["disabled"])

    def automatic_mode_off(self):
        self.ec_file_button.state(["!disabled"])

    def askopenfile_ec_csv(self):
        filename = filedialog.askopenfilename(initialdir=self.parent.initialdir, title="Select file",
                                              filetypes=(("csv files", "*.csv"), ("all files", "*.*")))
        if not filename:
            pass
        else:
            self.parent.gui_model_q.put(("load ec csv", filename))
            self.parent.initialdir = os.path.dirname(filename)

    def draw_electrochemical(self, cycle):
        logging.info("drawing electrochemical data")
        duck_ax = self.duck_figure.add_subplot(111)
        duck_ax.plot(self.parent.ec_data.V, self.parent.ec_data.uA)
        duck_ax.set_xlabel('U [V]')
        duck_ax.set_ylabel('I [uA]')
        duck_ax.set_title(cycle)
        self.duck_figure.tight_layout()
        self.duck_figure.canvas.draw()

    def find_ec_range(self, cycle=0):
        logging.info(f"plotting cycle {cycle + 1}")
        self.current_cycle = cycle
        self.parent.gui_model_q.put(("draw ec cycle", cycle))

    def electrochemical_teardown(self):
        self.duck_figure.clf()


class OptoFrame(tkinter.Frame):
    def __init__(self, root, *args, **kwargs):
        tkinter.Frame.__init__(self, root, *args, **kwargs)
        self.parent = root
        self.opto_figure = Figure(figsize=(5, 3))
        self.opto_figure.patch.set_facecolor('#f0f0f0')
        canvas = FigureCanvasTkAgg(self.opto_figure, master=self)
        canvas.get_tk_widget().grid(row=1, columnspan=2)
        canvas.draw()

        self.refresh_button = ttk.Button(self,
                                         text="Redraw",
                                         command=self.redraw_opto)
        self.optical_reference_button = ttk.Button(self,
                                                   text="Browse for optical data",
                                                   command=self.askopenfile_opto_csv)

        self.refresh_button.grid(row=3, column=0)
        self.optical_reference_button.grid(row=3, column=1)
        self.optical_data = None

    def redraw_opto(self):
        logging.info("redrawing optical data")
        self.parent.gui_model_q.put(("draw opto cycle", None))

    def opto_teardown(self):
        self.opto_figure.clf()

    def draw_optical(self, cycle):
        logging.info("please wait, drawing optical data")
        opto_ax = self.opto_figure.add_subplot(111)
        transmission, wavelength = self.optical_data.generate_data_for_plotting()
        for meas in transmission:
            opto_ax.plot(wavelength, transmission[meas])
        opto_ax.yaxis.set_major_formatter(mtick.FormatStrFormatter('%.1e'))
        opto_ax.set_xlabel('$\lambda$ [nm]')
        opto_ax.set_ylabel('intensity [counts]')
        opto_ax.set_title(cycle)
        self.opto_figure.tight_layout()
        self.opto_figure.canvas.draw()

    def automatic_mode_on(self):
        self.refresh_button.state(["disabled"])
        self.optical_reference_button.state(["disabled"])

    def automatic_mode_off(self):
        self.refresh_button.state(["!disabled"])
        self.optical_reference_button.state(["!disabled"])

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
        self.running_experiment = False
        self.start_stop_stringvar = tkinter.StringVar()
        self.dirname = None
        self.setup_frame()
        self.after(100, self.poll_log_queue)

    def set_automatic_mode(self):
        if not self.parent.automatic_mode:
            self.parent.set_automatic_mode(True)
            self.mode_radio.state(["selected"])
        else:
            self.parent.set_automatic_mode(False)
            self.mode_radio.state(["!selected"])

    def automatic_mode_on(self):
        self.start_experiment_button.state(["!disabled"])
        self.browse_exp_button.state(["!disabled"])
        self.cycle_buttons.automatic_mode_on()

    def automatic_mode_off(self):
        self.start_experiment_button.state(["disabled"])
        self.browse_exp_button.state(["disabled"])
        self.cycle_buttons.automatic_mode_off()

    def setup_logger(self):
        self.logger_text = scrolledtext.ScrolledText(self, state='disabled', height=8, width=60)
        self.logger_text.tag_config('INFO', foreground='black')
        self.logger_text.tag_config('DEBUG', foreground='gray')
        self.logger_text.tag_config('WARNING', foreground='orange')
        self.logger_text.tag_config('ERROR', foreground='red')
        self.logger_text.tag_config('CRITICAL', foreground='red', underline=True)
        self.logger_text.grid(row=3, columnspan=3)

    def setup_frame(self):
        self.setup_logger()

        self.mode_radio = ttk.Radiobutton(self, command=self.set_automatic_mode, text="automatic mode")
        self.mode_radio.grid(row=2, column=0)

        self.cycle_buttons = CycleButtonsGroup(self)
        self.cycle_buttons.grid(row=0, columnspan=3)

        self.browse_exp_button = ttk.Button(self, text="Browse for experiment", command=self.askopenfile_exp)
        self.browse_exp_button.state(["disabled"])
        self.browse_exp_button.grid(row=2, column=1)

        self.start_experiment_button = ttk.Button(self, text="start experiment", command=self.on_off_experiment)
        self.start_experiment_button.state(["disabled"])
        self.start_experiment_button.grid(row=2, column=2)

    def all_done(self):
        self.start_experiment_button.state(['!disabled'])

    def on_off_experiment(self):
        if not self.running_experiment and self.dirname:
            self.start_experiment()
            logging.info("experiment started")
        elif not self.running_experiment and not self.dirname:
            logging.warning("no experiment directory")

    def start_experiment(self):
        # request list of cycles from CycleButtonsGroup
        # inform model to start experiment
        self.running_experiment = True
        self.parent.gui_model_q.put(("start experiment", self.dirname))
        self.start_experiment_button.state(['disabled'])

    def askopenfile_exp(self):
        self.dirname = filedialog.askdirectory(initialdir=self.parent.initialdir, title="Select directory")
        if not self.dirname:
            pass
        else:
            logging.info("experiment {}".format(self.dirname))
            # self.parent.initialdir = os.path.dirname(filename)
            # todo: send to View for display

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
        """
        self.parent = parent
        self.cycle = cycle
        self.on = False
        #########################
        self.style = ttk.Style()
        self.style.configure(style="cycle_{}.TButton".format(self.cycle))
        self.color_on = "#0000ff"
        self.color_off = "#000000"
        #########################
        button_text = "Cycle {}".format(self.cycle + 1)
        ttk.Button.__init__(self, parent, text=button_text,
                            style="cycle_{}.TButton".format(self.cycle),
                            command=self.button_command)

    def change_button_color(self, color: str) -> None:
        # configure the style with a background color
        self.style.configure("cycle_{}.TButton".format(self.cycle), foreground=color)

    def button_command(self):
        if self.on:
            self.button_off()
        else:
            self.button_on()

    def button_on(self):
        self.change_button_color(self.color_on)
        self.parent.button_on(self.cycle)
        self.on = True

    def button_off(self):
        self.change_button_color(self.color_off)
        self.parent.button_off(self.cycle)
        self.on = False


class CycleButtonsGroup(tkinter.Frame):
    def __init__(self, root, *args, **kwargs):
        tkinter.Frame.__init__(self, root, *args, **kwargs)
        self.parent = root
        self.no_cycles = 1
        self.automatic_mode = False
        self.cycle_buttons_dict = {}
        self.buttons_on = []
        self.setup_frame()

    def setup_frame(self):
        for num in range(3):
            cycle = CycleButton(self, cycle=num)
            cycle.grid(row=0, column=num)
            if num >= 1:
                cycle.state(["disabled"])
            self.cycle_buttons_dict[num] = cycle

    def button_on(self, cycle):
        if self.automatic_mode:
            self.buttons_on.append(cycle)
        else:
            for item in self.buttons_on:
                self.cycle_buttons_dict[item].button_off()
            self.buttons_on = [cycle]
            self.parent.parent.gui_model_q.put(("ec cycle", cycle))

    def button_off(self, cycle):
        self.buttons_on.remove(cycle)

    def update_no_cycles(self, num_cycles):
        # disable all buttons
        for cycle_button in self.cycle_buttons_dict:
            self.cycle_buttons_dict[cycle_button].state(["disabled"])

        # enable valid buttons
        if num_cycles > 0:
            try:
                for num in range(num_cycles):
                    self.cycle_buttons_dict[num].state(["!disabled"])
            except KeyError:
                logging.warning(f"unrecognizable cycle number: {num_cycles}")
        else:
            self.cycle_buttons_dict[0].state(["!disabled"])

    def automatic_mode_on(self):
        # multiple choice
        # default: all cycles on
        self.automatic_mode = True
        self.update_no_cycles(3)
        for num in range(3):
            self.cycle_buttons_dict[num].button_on()

    def automatic_mode_off(self):
        # single choice
        # default: check number of cycles
        self.automatic_mode = False
        for num in range(3):
            self.cycle_buttons_dict[num].button_off()
        self.update_no_cycles(self.no_cycles)


class AnalysisFrame(tkinter.Frame):
    def __init__(self, root, *args, **kwargs):
        self.parent = root
        tkinter.Frame.__init__(self, root, *args, **kwargs)

        self.anls_figure = Figure(figsize=(5, 3))
        self.anls_figure.patch.set_facecolor('#f0f0f0')
        canvas = FigureCanvasTkAgg(self.anls_figure, master=self)
        canvas.get_tk_widget().grid(row=1, columnspan=2)
        canvas.draw()

        self.anls_redraw_button = ttk.Button(self, text="Redraw", command=self.model_send_params)
        self.anls_savedata_button = ttk.Button(self, text="Save data", command=self.save_data)
        self.param_option_string = tkinter.StringVar()
        anls_option = ttk.Combobox(self, textvariable=self.param_option_string)
        anls_option['values'] = ('fit λ(V)+IODM(V)', 'fit λ(V)', 'IODM(V)')

        anls_option.grid(row=2, columnspan=2)
        anls_option.current(0)
        self.anls_redraw_button.grid(row=3, column=0)
        self.anls_savedata_button.grid(row=3, column=1)

    def automatic_mode_on(self):
        self.anls_redraw_button.state(["disabled"])
        self.anls_savedata_button.state(["disabled"])

    def automatic_mode_off(self):
        self.anls_redraw_button.state(["!disabled"])
        self.anls_savedata_button.state(["!disabled"])

    def save_data(self):
        logging.info("saving data to files")
        self.parent.gui_model_q.put(("save data", 0))

    def model_send_params(self):
        logging.info("collecting data for plotting")
        param = self.param_option_string.get()
        self.parent.gui_model_q.put((param, 0))

    def parameter_teardown(self):
        self.anls_figure.clf()

    def two_parameter_plotting(self, ec_V, iodm, lbd_min, cycle):
        self.parameter_teardown()
        min_ax = self.anls_figure.add_subplot(111)
        color = 'b'
        min_ax.plot(ec_V, lbd_min, '.', color=color)
        min_ax.set_xlabel('U [V]')
        min_ax.set_ylabel('λ [nm]', color=color)
        min_ax.set_title(cycle)

        color = 'r'
        iodm_ax = min_ax.twinx()
        iodm_ax.plot(ec_V, iodm, '.', color=color)
        iodm_ax.set_ylabel('IODM', color=color)

        self.anls_figure.tight_layout()
        self.anls_figure.canvas.draw()

    def parameter_plotting(self, param, x, y, cycle):
        self.parameter_teardown()
        min_ax = self.anls_figure.add_subplot(111)
        min_ax.plot(x, y, '.')
        min_ax.set_title(cycle)
        if param == 'fit λ(V)':
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
