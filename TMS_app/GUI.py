#!/usr/bin/env python

import tkinter
import logging
import threading
import matplotlib
import matplotlib.ticker as mtick
import matplotlib.patches as patches
import tms_exceptions as tms_exc
import os
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

        # data structures
        self.optical_data = None
        self.ec_data = None

        # optical items
        self.opto_figure = None
        self.opto_bg = None
        self.lambda_from_slider = None
        self.opto_slider = None
        self.lambda_label = None
        # duck items
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
        # min items
        self.min_figure = None
        self.param_option_string = None

        self.window = tkinter.Tk()
        self.window.title("TechMatStrateg")
        self.window.minsize(width=1200, height=400)
        self.setup_window()
        self.initialdir = "C:/Users/aerial triceratops/PycharmProjects/TechMatStrateg/dane/"
        logging.info("GUI running thread {}".format(threading.get_ident()))

        self.window.mainloop()

    def poll_data_queue(self):
        # Check every 400ms if there is a new message in the queue
        while True:
            try:
                record = self._model_gui_q.get(block=False)
            except Empty:
                break
            try:
                order, data = record
            except ValueError:
                logging.info("order misshap: {}".format(record))
            else:
                if order == "draw ec":
                    self.ec_data = data
                    self.electrochemical_teardown()
                    self.draw_electrochemical()
                elif order == "draw opto":
                    self.optical_data = data
                    self.opto_teardown()
                    try:
                        self.draw_optical()
                    except ValueError:
                        logging.error("cannot draw optical data. is ec file loaded?")
                elif order == "send ec ranges":
                    ec_ranges = self.find_ec_range()
                    self._gui_model_q.put(("ec range", ec_ranges))
                elif order == "IODM(V)":
                    self.draw_iodm_v(data)
                # elif order == "IODM(meas)":
                #     self.draw_iodm_meas(data)
                elif order == 'λ(V)':
                    self.min_draw(data)
                # elif order == 'λ(meas)':
                #     self.min_meas_draw(data)
                elif order == 'λ(V)+IODM(V)':
                    self.min_iodm_draw(data)
                else:
                    logging.info("unrecognized order from model: {}".format(order))
        self.window.after(400, self.poll_data_queue)

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
        self.opto_bg = self.opto_figure.canvas.copy_from_bbox(self.opto_figure.bbox)
        x = 600
        dx = 170
        y = opto_ax.get_ylim()[0]
        dy = opto_ax.get_ylim()[1]
        opto_rect = patches.Rectangle((x, y), dx, dy,
                                      linewidth=1,
                                      edgecolor=View.seaborn_colors[0],
                                      facecolor=View.seaborn_colors[0],
                                      alpha=0.25)
        opto_ax.add_artist(opto_rect)
        opto_ax.draw_artist(opto_rect)
        self.opto_figure.canvas.draw()

        self.lambda_start = tkinter.DoubleVar()
        self.lambda_start.set(x)
        self.lambda_from_slider = tkinter.DoubleVar()
        self.lambda_from_slider.set(dx)
        self.opto_slider = ttk.Scale(self.optoframe,
                                     from_=0.0,
                                     to_=self.optical_data.wavelength[-1]-self.optical_data.wavelength[0],
                                     length=300,
                                     command=self.resize_wavelength_range,
                                     variable=self.lambda_from_slider)
        string_label = "{:.2f} nm".format(self.lambda_from_slider.get())
        self.lambda_label = tkinter.Label(self.optoframe, text=string_label)
        self.lambda_label.pack(side=tkinter.LEFT, padx=3)
        self.opto_slider.pack(side=tkinter.RIGHT)
        self.opto_dr = DraggableRectangle(opto_rect, self.lambda_start, self.opto_bg)
        self.opto_dr.connect()

    def draw_optical_old(self):
        logging.info("please wait, drawing optical data")
        opto_ax = self.opto_figure.add_subplot(111)
        for meas in self.optical_data.opto_set:
            opto_ax.plot(self.optical_data.wavelength, self.optical_data.opto_set[meas].transmission)
        opto_ax.yaxis.set_major_formatter(mtick.FormatStrFormatter('%.1e'))
        opto_ax.set_xlabel('$\lambda$ [nm]')
        opto_ax.set_ylabel('T [dB]')
        self.opto_figure.tight_layout()
        self.opto_figure.canvas.draw()
        self.opto_bg = self.opto_figure.canvas.copy_from_bbox(self.opto_figure.bbox)
        self.lambda_from_slider = tkinter.DoubleVar()
        self.opto_slider = ttk.Scale(self.optoframe,
                                     from_=self.optical_data.wavelength[0],
                                     to_=self.optical_data.wavelength[-1],
                                     length=300,
                                     command=self.resize_wavelength_range,
                                     variable=self.lambda_from_slider,
                                     value=self.optical_data.wavelength[0])
        string_label = "{:.2f} nm".format(self.optical_data.wavelength[0])
        self.lambda_label = tkinter.Label(self.optoframe, text=string_label)
        self.lambda_label.pack(side=tkinter.LEFT, padx=3)
        self.opto_slider.pack(side=tkinter.RIGHT)

    def opto_teardown(self):
        try:
            self.opto_slider.destroy()
            self.lambda_label.destroy()
            self.opto_figure.clf()
        except AttributeError:
            pass

    def draw_optical_line(self, lambda_nm):
        # obsolete
        self.opto_figure.canvas.restore_region(self.opto_bg)
        lambda_float = float(lambda_nm)
        [opto_ax, ] = self.opto_figure.axes
        yrange = opto_ax.get_ylim()
        [ln, ] = opto_ax.plot([float(lambda_float), float(lambda_float)], [yrange[0], yrange[1]],
                              color=self.seaborn_colors[0], animated=True)
        opto_ax.draw_artist(ln)
        self.opto_figure.canvas.blit(self.opto_figure.bbox)
        self.lambda_label.configure(text="{:.2f} nm".format(lambda_float))

    def resize_wavelength_range(self, lambda_nm):
        self.opto_figure.canvas.restore_region(self.opto_bg)
        lambda_float = float(lambda_nm)
        self.opto_dr.reshape_x(lambda_float)
        self.lambda_label.configure(text="{:.2f} nm".format(lambda_float))

    def electrochemical_teardown(self):
        self.duck_figure.clf()
        self.duck_slider_v.destroy()
        self.duck_slider_ua.destroy()
        self.current_from_slider = None
        self.voltage_from_slider = None
        self.duck_bg = None
        self.duck_dr = None
        try:
            self.current_max_label.destroy()
            self.current_min_label.destroy()
            self.voltage_max_label.destroy()
            self.voltage_min_label.destroy()
        except AttributeError:
            pass

    def draw_electrochemical(self):
        logging.info("please wait, drawing electrochemical data")
        duck_ax = self.duck_figure.add_subplot(111)
        duck_ax.plot(self.ec_data.V, self.ec_data.uA)
        duck_ax.set_xlabel('U [V]')
        duck_ax.set_ylabel('I [uA]')
        self.duck_figure.tight_layout()
        self.duck_figure.canvas.draw()
        self.duck_bg = self.duck_figure.canvas.copy_from_bbox(self.duck_figure.bbox)
        x = min(self.ec_data.V); dx = -x+max(self.ec_data.V)
        y = min(self.ec_data.uA); dy = -y+max(self.ec_data.uA)
        rect = patches.Rectangle((x, y), dx, dy,
                                 linewidth=1,
                                 edgecolor=View.seaborn_colors[0],
                                 facecolor=View.seaborn_colors[0],
                                 alpha=0.25)
        duck_ax.add_artist(rect)
        duck_ax.draw_artist(rect)
        self.duck_figure.canvas.draw()

        self.voltage_from_slider = RoundedDoubleVar(self.duckframe, dx)
        self.current_from_slider = tkinter.DoubleVar(self.duckframe, dy)
        self.voltage_from_dr = RoundedDoubleVar(self.duckframe, x)
        self.current_from_dr = tkinter.DoubleVar(self.duckframe, y)

        self.voltage_from_slider.trace_add('write',
                                           lambda *args: self.update_max_voltage(self.voltage_from_slider, *args))
        self.current_from_slider.trace_add('write',
                                           lambda *args: self.update_max_current(self.current_from_slider, *args))
        self.voltage_from_dr.trace_add('write', lambda *args: self.update_min_voltage(self.voltage_from_dr, *args))
        self.current_from_dr.trace_add('write', lambda *args: self.update_min_current(self.current_from_dr, *args))

        self.duck_dr = DraggableRectangle(rect, self.voltage_from_dr, self.duck_bg, self.current_from_dr)
        self.duck_dr.connect()

        self.current_max_label = tkinter.Label(self.top_duckframe, text='{:.3f}'.format(dy/self.micro), width=8)
        self.current_min_label = tkinter.Label(self.top_duckframe, text='{:.3f}'.format(y/self.micro), width=8)
        self.voltage_max_label = tkinter.Label(self.duckframe, text='{:.2f}'.format(dx))
        self.voltage_min_label = tkinter.Label(self.duckframe, text='{:.2f}'.format(x))

        self.duck_slider_v = ttk.Scale(self.duckframe,
                                       from_=0,
                                       to_=max(self.ec_data.V)-min(self.ec_data.V),
                                       length=300,
                                       variable=self.voltage_from_slider)
        self.duck_slider_ua = ttk.Scale(self.top_duckframe,
                                        length=250,
                                        from_=max(self.ec_data.uA)-min(self.ec_data.uA),
                                        to_=0,
                                        variable=self.current_from_slider,
                                        orient=tkinter.VERTICAL)

        self.current_max_label.pack()
        self.current_min_label.pack(side=tkinter.BOTTOM)
        self.voltage_min_label.pack(side=tkinter.LEFT)
        self.voltage_max_label.pack(side=tkinter.RIGHT)

        self.duck_slider_ua.pack(side=tkinter.LEFT)
        self.duck_slider_v.pack()

    def find_ec_range(self):
        logging.info("calculating ec ranges")
        if self.in_rectangle(self.ec_data.id[0]):
            ec_start_inside = 0
        else:
            ec_start_inside = None
        for ec_id in self.ec_data.id[1:-1]:
            if not ec_start_inside and self.in_rectangle(ec_id):
                ec_start_inside = ec_id
            elif ec_start_inside and not self.in_rectangle(ec_id):
                yield ec_start_inside, ec_id
                ec_start_inside = None
        if ec_start_inside:
            if self.in_rectangle(self.ec_data.id[-1]):
                yield ec_start_inside, self.ec_data.id[-1]
            else:
                yield ec_start_inside, self.ec_data.id[-2]

    def in_rectangle(self, ec_id):
        point_x = self.ec_data.V[ec_id]
        point_y = self.ec_data.uA[ec_id]
        dx = self.voltage_from_slider.get()
        dy = self.current_from_slider.get()
        x = self.voltage_from_dr.get()
        y = self.current_from_dr.get()
        if x <= point_x <= x + dx and y <= point_y <= y + dy:
            return True
        else:
            return False

    def update_ec_range(self):
        ec_range = self.find_ec_range()
        self._gui_model_q.put(("ec range", ec_range))

    def update_max_voltage(self, v, *args):
        voltage = self.voltage_from_slider.get()
        self.duck_dr.reshape_x(float(voltage))
        self.voltage_max_label.configure(text="{} V".format(v.round_string()))
        self.update_ec_range()

    def update_min_voltage(self, v, *args):
        self.voltage_min_label.configure(text="{} V".format(v.round_string()))
        self.update_ec_range()

    def update_max_current(self, ua, *args):
        current = ua.get()
        self.duck_dr.reshape_y(float(current))
        self.current_max_label.configure(text="{:.3f} uA".format(current/self.micro))
        self.update_ec_range()

    def update_min_current(self, ua, *args):
        current = ua.get()
        self.current_min_label.configure(text="{:.3f} uA".format(current/self.micro))
        self.update_ec_range()

    def draw_ec_vline(self, voltage):
        self.duck_dr.reshape_x(float(voltage))
        self.voltage_max_label.configure(text="{} V".format(self.voltage_from_slider.round_string()))

    def draw_ec_ualine(self, current):
        self.duck_dr.reshape_y(float(current))
        self.current_max_label.configure(text="{} uA".format(self.current_from_slider.round_string()))

    def setup_frames(self):
        self.topframe = tkinter.Frame(self.window, pady=3)
        self.bottomframe = tkinter.Frame(self.window, pady=3)

        self.duckframe = tkinter.Frame(self.topframe)
        self.optoframe = tkinter.Frame(self.topframe)
        self.minframe = tkinter.Frame(self.topframe)

        self.top_duckframe = tkinter.Frame(self.topframe)
        self.top_optoframe = tkinter.Frame(self.topframe)
        self.top_minframe = tkinter.Frame(self.topframe)

        self.bottom_optoframe = tkinter.Frame(self.optoframe)

        set_theme()

        self.topframe.pack(side=tkinter.TOP, anchor='e')
        self.bottomframe.pack(side=tkinter.BOTTOM)

        self.duckframe.grid(sticky="E", row=1, column=0)
        self.optoframe.grid(sticky="E", row=1, column=1)
        self.minframe.grid(sticky="E", row=1, column=2)

        self.top_duckframe.grid(sticky="E", row=0, column=0)
        self.top_optoframe.grid(sticky="E", row=0, column=1)
        self.top_minframe.grid(sticky="E", row=0, column=2)

        self.bottom_optoframe.pack(side=tkinter.BOTTOM)

    def setup_window(self):
        self.setup_frames()
        self.setup_logger()

        self.setup_duck_frame()
        self.setup_opto_frame()
        self.setup_min_frame()

        self.window.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.window.after(100, self.poll_log_queue)
        # self.window.after(400, self.poll_ctrl_queue)
        self.window.after(401, self.poll_data_queue)

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

        ec_file_button = ttk.Button(self.duckframe, text="Browse for ec data", command=self.askopenfile_ec_csv)
        ec_file_button.pack(side=tkinter.BOTTOM)

        # label_vertical
        # label horizontal

    def setup_opto_frame(self):
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
                                              text="Browse for optical data",
                                              command=self.askopenfile_opto_csv)

        optical_file_button.pack(side=tkinter.LEFT, padx=3)
        optical_reference_button.pack(side=tkinter.RIGHT, padx=3)

    def redraw_opto(self):
        logging.info("redrawing optical data")
        ec_range = self.find_ec_range()
        self._gui_model_q.put(("ec range", ec_range))
        self._gui_model_q.put(("draw opto", None))

    def askopenfile_opto_csv(self):
        logging.info("loading optical file")
        filename = filedialog.askopenfilename(initialdir=self.initialdir, title="Select file",
                                              filetypes=(("csv files", "*.csv"), ("all files", "*.*")))
        if not filename:
            pass
        else:
            self._gui_model_q.put(("load opto csv", filename))
            self.initialdir = os.path.dirname(filename)

    def parameter_teardown(self):
        self.min_figure.clf()

    def model_send_params(self):
        logging.info("collecting data for plotting")
        param = self.param_option_string.get()
        wvlgth_range = [self.lambda_start.get(), self.lambda_from_slider.get()]
        self._gui_model_q.put((param, wvlgth_range))

    @staticmethod
    def find_nearest_lambda(lambda_nm, wavelength_array):
        # find nearest value, return index
        diff = [abs(item - lambda_nm) for item in wavelength_array]
        idx = diff.index(min(diff))
        return idx

    def cross_section_draw(self):
        logging.info("please wait, drawing cross section data")
        lambda_nm = self.lambda_start.get()
        min_idx = self.find_nearest_lambda(lambda_nm, self.optical_data.wavelength)
        min_array = []
        ec_id_array = self.ec_items_from_ranges()
        print(ec_id_array)
        ec_V = [self.ec_data.V[x] for x in ec_id_array]
        for item in self.optical_data.transmission:
            min_array.append(self.optical_data.transmission[item][min_idx])
        self.parameter_plotting(ec_V, min_array)

    def min_iodm_draw(self, data):
        logging.info("please wait, drawing min+iodm data")
        ec_V, iodm, lbd_min_dir = data
        _, lbd_min_array = zip(*lbd_min_dir.items())
        self.two_parameter_plotting(ec_V, iodm, lbd_min_array)

    def min_draw(self, data):
        logging.info("please wait, drawing min data")
        ec_V, lbd_min_dir = data
        _, lbd_min_array = zip(*lbd_min_dir.items())
        self.parameter_plotting(ec_V, lbd_min_array)

    def draw_iodm_v(self, data):
        logging.info("please wait, drawing min data")
        ec_V, iodm_array = data
        self.parameter_plotting(ec_V, iodm_array)

    def IODM_draw(self):
        logging.info("please wait, drawing IODM data")
        wvlgth_range = [self.lambda_start, self.lambda_from_slider]  # get wavelength range
        self._gui_model_q.put(("calc iodm", wvlgth_range))
        ec_data, iodm_data = self.optical_data.calc_IODM(wvlgth_range)
        self.parameter_plotting(ec_data, iodm_data)

    def two_parameter_plotting(self, ec_V, iodm, lbd_min):
        self.parameter_teardown()
        min_ax = self.min_figure.add_subplot(111)
        color = 'b'
        min_ax.plot(ec_V, lbd_min, '.', color=color)
        min_ax.set_xlabel('U [V]')
        min_ax.set_ylabel('λ [nm]', color=color)

        color = 'r'
        iodm_ax = min_ax.twinx()
        iodm_ax.plot(ec_V, iodm, '.', color=color)
        iodm_ax.set_ylabel('IODM', color=color)

        self.min_figure.tight_layout()
        self.min_figure.canvas.draw()


    def parameter_plotting(self, x, y):
        self.parameter_teardown()
        min_ax = self.min_figure.add_subplot(111)
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
        self.min_figure.tight_layout()
        self.min_figure.canvas.draw()

    def setup_min_frame(self):
        self.min_figure = Figure(figsize=(4, 3))
        self.min_figure.patch.set_facecolor('#f0f0f0')
        canvas = FigureCanvasTkAgg(self.min_figure, master=self.top_minframe)
        canvas.get_tk_widget().pack(side=tkinter.TOP)
        canvas.draw()

        min_redraw_button = ttk.Button(self.minframe, text="Redraw", command=self.model_send_params)
        self.param_option_string = tkinter.StringVar()
        min_option = ttk.Combobox(self.minframe, textvariable=self.param_option_string)
        min_option['values'] = ('λ(V)+IODM(V)', 'λ(V)', 'IODM(V)')
        min_redraw_button.pack(side=tkinter.RIGHT)
        min_option.pack(side=tkinter.LEFT, padx=3)
        min_option.current(0)

    def setup_logger(self):
        self.logger_text = scrolledtext.ScrolledText(self.bottomframe, state='disabled', height=8)
        self.logger_text.tag_config('INFO', foreground='black')
        self.logger_text.tag_config('DEBUG', foreground='gray')
        self.logger_text.tag_config('WARNING', foreground='orange')
        self.logger_text.tag_config('ERROR', foreground='red')
        self.logger_text.tag_config('CRITICAL', foreground='red', underline=1)
        self.logger_text.grid()

    def askopenfile_ec_csv(self):
        filename = filedialog.askopenfilename(initialdir=self.initialdir, title="Select file",
                                              filetypes=(("csv files", "*.csv"), ("all files", "*.*")))
        if not filename:
            pass
        else:
            self._gui_model_q.put(("load ec csv", filename))
            self.initialdir = os.path.dirname(filename)

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


class RoundedDoubleVar(tkinter.DoubleVar):

    def round_string(self):
        return "{:.2f}".format(self.get())


class DraggableRectangle:
    def __init__(self, rect, x, background, y=None):
        self.rect = rect
        self.bg = background
        self.press = None
        self.x = x
        self.y = y

    def connect(self):
        'connect to all the events we need'
        self.cidpress = self.rect.figure.canvas.mpl_connect(
            'button_press_event', self.on_press)
        self.cidrelease = self.rect.figure.canvas.mpl_connect(
            'button_release_event', self.on_release)
        self.cidmotion = self.rect.figure.canvas.mpl_connect(
            'motion_notify_event', self.on_motion)

    def on_press(self, event):
        'on button press we will see if the mouse is over us and store some data'
        if event.inaxes != self.rect.axes: return

        contains, attrd = self.rect.contains(event)
        if not contains: return
        # print('event contains', self.rect.xy)
        x0, y0 = self.rect.xy
        self.press = x0, y0, event.xdata, event.ydata

    def on_motion(self, event):
        'on motion we will move the rect if the mouse is over us'
        if self.press is None: return
        if event.inaxes != self.rect.axes: return
        x0, y0, xpress, ypress = self.press
        dx = event.xdata - xpress
        dy = event.ydata - ypress
        #print('x0=%f, xpress=%f, event.xdata=%f, dx=%f, x0+dx=%f' %
        #      (x0, xpress, event.xdata, dx, x0+dx))
        self.rect.set_x(x0+dx)
        self.x.set(x0+dx)

        if self.y:
            self.rect.set_y(y0+dy)
            self.y.set(y0+dy)
        self.rect.figure.canvas.restore_region(self.bg)
        self.rect.axes.draw_artist(self.rect)
        self.rect.figure.canvas.blit(self.rect.figure.bbox)

    def on_release(self, event):
        'on release we reset the press data'
        self.press = None
        self.rect.figure.canvas.restore_region(self.bg)
        self.rect.axes.draw_artist(self.rect)
        self.rect.figure.canvas.blit(self.rect.figure.bbox)

    def disconnect(self):
        'disconnect all the stored connection ids'
        self.rect.figure.canvas.mpl_disconnect(self.cidpress)
        self.rect.figure.canvas.mpl_disconnect(self.cidrelease)
        self.rect.figure.canvas.mpl_disconnect(self.cidmotion)

    def reshape_x(self, reshape_x):
        self.rect.set_width(reshape_x)
        self.rect.figure.canvas.restore_region(self.bg)
        self.rect.axes.draw_artist(self.rect)
        self.rect.figure.canvas.blit(self.rect.figure.bbox)

    def reshape_y(self, reshape_y):
        self.rect.set_height(reshape_y)
        self.rect.figure.canvas.restore_region(self.bg)
        self.rect.axes.draw_artist(self.rect)
        self.rect.figure.canvas.blit(self.rect.figure.bbox)


if __name__ == '__main__':
    pass
