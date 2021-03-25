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

    def poll_ctrl_queue(self):
        # Check every 400ms if there is a new message in the queue
        while True:
            try:
                record = self._ctrl_gui_q.get(block=False)
            except Empty:
                break
            else:
                if record[0] == "draw ec":  # todo:remove
                    self.electrochemical_teardown()
                    self.draw_electrochemical()
                elif record[0] == "draw opto":  # todo:remove
                    self.opto_teardown()
                    self.draw_optical()
                else:
                    logging.info("unrecognized order from ctrl: {}".format(record))
        self.window.after(400, self.poll_ctrl_queue)

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
        self.window.after(400, self.poll_ctrl_queue)
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

    def electrochemical_teardown(self):
        self.duck_figure.clf()
        self.duck_slider_v.destroy()
        self.duck_slider_ua.destroy()
        self.current_from_slider = None
        self.voltage_from_slider = None
        self.duck_bg = None
        self.duck_dr = None

    def draw_electrochemical(self):
        logging.info("please wait, drawing electrochemical data")
        duck_ax = self.duck_figure.add_subplot(111)
        duck_ax.plot(self.ec_data.V, self.ec_data.uA)
        duck_ax.set_xlabel('U [V]')
        duck_ax.set_ylabel('I [uA]')
        self.duck_figure.tight_layout()
        self.duck_figure.canvas.draw()
        self.duck_bg = self.duck_figure.canvas.copy_from_bbox(self.duck_figure.bbox)
        x = 0.0; dx = 1.0
        y = 0.0; dy = 1*10**(-5)
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

        self.duck_dr = DraggableRectangle(rect, self.voltage_from_dr, self.current_from_dr, self.duck_bg)
        self.duck_dr.connect()

        self.current_max_label = tkinter.Label(self.top_duckframe, text='{:.2f}'.format(dy/self.micro), width=8)
        self.current_min_label = tkinter.Label(self.top_duckframe, text='{:.2f}'.format(y/self.micro), width=8)
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
        for ec_id in self.ec_data.id[1:]:
            if not ec_start_inside and self.in_rectangle(ec_id):
                ec_start_inside = ec_id
            elif ec_start_inside and not self.in_rectangle(ec_id):
                yield ec_start_inside, ec_id
                ec_start_inside = None

    def in_rectangle(self, ec_id):
        point_x = self.ec_data.V[ec_id]
        point_y = self.ec_data.uA[ec_id]
        (x, y) = self.duck_dr.rect.get_xy()
        dx, dy = self.duck_dr.rect.get_width(), self.duck_dr.rect.get_height()
        if x <= point_x <= x + dx and y <= point_y <= y + dy:
            return True
        else:
            return False


    def update_max_voltage(self, v, *args):
        voltage = self.voltage_from_slider.get()
        self.duck_dr.reshape_x(float(voltage))
        self.voltage_max_label.configure(text="{} V".format(v.round_string()))
        # todo: redraw optics

    def update_min_voltage(self, v, *args):
        self.voltage_min_label.configure(text="{} V".format(v.round_string()))
        # todo: redraw optics

    def update_max_current(self, ua, *args):
        current = ua.get()
        self.duck_dr.reshape_y(float(current))
        self.current_max_label.configure(text="{:.2f} uA".format(current/self.micro))
        # todo: redraw optics

    def update_min_current(self, ua, *args):
        current = ua.get()
        self.current_min_label.configure(text="{:.2f} uA".format(current/self.micro))
        # todo: redraw optics

    def draw_ec_vline(self, voltage):
        self.duck_dr.reshape_x(float(voltage))
        self.voltage_max_label.configure(text="{} V".format(self.voltage_from_slider.round_string()))
        # todo: redraw optics

    def draw_ec_ualine(self, current):
        self.duck_dr.reshape_y(float(current))
        self.current_max_label.configure(text="{} uA".format(self.current_from_slider.round_string()))
        # todo: redraw optics


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

    def draw_optical(self, optical_data, ec_range):
        logging.info("please wait, drawing optical data")
        opto_ax = self.opto_figure.add_subplot(111)
        drawing_data = optical_data.generate_data_for_plotting(ec_range)
        for meas in optical_data.transmission:
            opto_ax.plot(optical_data.wavelength, optical_data.transmission[meas])
        opto_ax.yaxis.set_major_formatter(mtick.FormatStrFormatter('%.1e'))
        opto_ax.set_xlabel('$\lambda$ [nm]')
        opto_ax.set_ylabel('T [dB]')
        self.opto_figure.tight_layout()
        self.opto_figure.canvas.draw()
        self.opto_bg = self.opto_figure.canvas.copy_from_bbox(self.opto_figure.bbox)
        self.lambda_from_slider = tkinter.DoubleVar()
        self.opto_slider = ttk.Scale(self,
                                     from_=optical_data.wavelength[0],
                                     to_=optical_data.wavelength[-1],
                                     length=300,
                                     command=self.draw_optical_line,
                                     variable=self.lambda_from_slider,
                                     value=optical_data.wavelength[0])
        string_label = "{:.2f} nm".format(optical_data.wavelength[0])
        self.lambda_label = tkinter.Label(self, text=string_label)
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
        self.opto_figure.canvas.restore_region(self.opto_bg)
        lambda_float = float(lambda_nm)
        [opto_ax, ] = self.opto_figure.axes
        yrange = opto_ax.get_ylim()
        [ln, ] = opto_ax.plot([float(lambda_float), float(lambda_float)], [yrange[0], yrange[1]],
                              color=self.seaborn_colors[0], animated=True)
        opto_ax.draw_artist(ln)
        self.opto_figure.canvas.blit(self.opto_figure.bbox)
        self.lambda_label.configure(text="{:.2f} nm".format(lambda_float))

    def redraw_opto(self):
        logging.info("redrawing optical data")
        self.ec_range = self.find_ec_range()
        self._gui_ctrl_q.put(("draw opto", self.ec_range))


class ParamFrame(tkinter.Frame):
    def __init__(self, root, *args, **kwargs):
        tkinter.Frame.__init__(self, root, *args, **kwargs)
        self.min_figure = None
        self.param_option_string = None

    def cross_section_draw(self):
        logging.info("please wait, drawing cross section data")
        lambda_nm = self.lambda_from_slider.get()
        min_idx = self.find_nearest_lambda(lambda_nm, self.optical_data.wavelength)
        min_array = []
        ec_id_array = self.optical_data.transmission.keys()
        ec_V = [self.ec_data.V[x] for x in ec_id_array]
        for item in self.optical_data.transmission:
            min_array.append(self.optical_data.transmission[item][min_idx])
        self.parameter_plotting(ec_V, min_array)

    def min_draw(self):
        logging.info("please wait, drawing min data")
        # get lambda range from draggable rectangle
        range = [1000, 1500]  # in id
        min_array = []
        ec_id_array = self.optical_data.transmission.keys()
        ec_V = [self.ec_data.V[x] for x in ec_id_array]
        for item in self.optical_data.transmission:
            min_array.append(min(self.optical_data.transmission[item][range[0]:range[1]]))
        self.parameter_plotting(ec_V, min_array)

    def IODM_draw(self):
        logging.info("please wait, drawing IODM data")
        range = [1000, 1500]  # get wavelength range
        ec_data, iodm_data = self.optical_data.calc_IODM(range)
        self.parameter_plotting(ec_data, iodm_data)

    def parameter_plotting(self, x, y):
        min_ax = self.min_figure.add_subplot(111)
        min_ax.plot(x, y, '.')
        min_ax.set_xlabel('U [V]')
        min_ax.set_ylabel('T [dB]')
        self.min_figure.tight_layout()
        self.min_figure.canvas.draw()

    def setup_min_frame(self):
        self.min_figure = Figure(figsize=(4, 3))
        self.min_figure.patch.set_facecolor('#f0f0f0')
        canvas = FigureCanvasTkAgg(self.min_figure, master=self.top_minframe)
        canvas.get_tk_widget().pack(side=tkinter.TOP)
        canvas.draw()

        min_redraw_button = ttk.Button(self.minframe, text="Redraw", command=self.parameter_redraw)
        self.param_option_string = tkinter.StringVar()
        min_option = ttk.Combobox(self.minframe, textvariable=self.param_option_string)
        min_option['values'] = ('min', 'cross section', 'IODM')

        min_redraw_button.pack(side=tkinter.RIGHT)
        min_option.pack(side=tkinter.LEFT, padx=3)
        min_option.current(0)

    def parameter_teardown(self):
        self.min_figure.clf()

    def parameter_redraw(self):
        self.parameter_teardown()
        if self.param_option_string == "min":
            self.min_draw()
        elif self.param_option_string == "cross section":
            self.cross_section_draw()
        elif self.param_option_string == "IODM":
            self.IODM_draw()

    @staticmethod
    def find_nearest_lambda(lambda_nm, wavelength_array):
        # find nearest value, return index
        diff = [abs(item - lambda_nm) for item in wavelength_array]
        idx = diff.index(min(diff))
        return idx


class RoundedDoubleVar(tkinter.DoubleVar):

    def round_string(self):
        return "{:.2f}".format(self.get())


class DraggableRectangle:
    def __init__(self, rect, x, y, background):
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
        self.rect.set_y(y0+dy)

        self.x.set(x0+dx)
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
