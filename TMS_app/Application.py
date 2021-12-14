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
                if record[0] == "draw ec":
                    self.ec_data = data
                    self.duck_frame.electrochemical_teardown()
                    self.duck_frame.draw_electrochemical()
                elif record[0] == "draw opto":
                    self.optical_data = data
                    self.opto_frame.opto_teardown()
                    try:
                        self.opto_frame.draw_optical()
                    except ValueError:
                        logging.error("cannot draw optical data. is ec file loaded?")
                elif record[0] == 'send ec ranges':
                    ec_ranges = self.duck_frame.find_ec_range()
                    self.gui_model_q.put(("ec range", ec_ranges))
                else:
                    logging.info("unrecognized order from ctrl: {}".format(record))
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
        canvas = FigureCanvasTkAgg(self.duck_figure, master=self)
        canvas.get_tk_widget().grid(row=0, column=2, rowspan=2, columnspan=2)
        canvas.draw()
        self.duck_slider_v = ttk.Scale(self, length=350, from_=-0.5, to_=1.5)
        self.duck_slider_ua = ttk.Scale(self, length=250, from_=-0.5, to_=1.5, orient=tkinter.VERTICAL)

        self.duck_slider_v.grid(row=2, column=2)
        self.duck_slider_ua.grid(row=0, column=1)

        ec_file_button = ttk.Button(self, text="Browse for ec data", command=self.askopenfile_ec_csv)
        ec_file_button.grid(row=4, column=2)

    def askopenfile_ec_csv(self):
        filename = filedialog.askopenfilename(initialdir=self.parent.initialdir, title="Select file",
                                              filetypes=(("csv files", "*.csv"), ("all files", "*.*")))
        if not filename:
            pass
        else:
            self.parent.gui_model_q.put(("load ec csv", filename))
            self.initialdir = os.path.dirname(filename)

    def draw_electrochemical(self):
        logging.info("please wait, drawing electrochemical data")
        duck_ax = self.duck_figure.add_subplot(111)
        duck_ax.plot(self.parent.ec_data.V, self.parent.ec_data.uA)
        duck_ax.set_xlabel('U [V]')
        duck_ax.set_ylabel('I [uA]')
        self.duck_figure.tight_layout()
        self.duck_figure.canvas.draw()
        self.duck_bg = self.duck_figure.canvas.copy_from_bbox(self.duck_figure.bbox)
        x = min(self.parent.ec_data.V)
        dx = -x + max(self.parent.ec_data.V)
        y = min(self.parent.ec_data.uA)
        dy = -y + max(self.parent.ec_data.uA)
        rect = patches.Rectangle((x, y), dx, dy,
                                 linewidth=1,
                                 edgecolor=View.seaborn_colors[0],
                                 facecolor=View.seaborn_colors[0],
                                 alpha=0.25)
        duck_ax.add_artist(rect)
        duck_ax.draw_artist(rect)
        self.duck_figure.canvas.draw()

        self.voltage_from_slider = RoundedDoubleVar(self, dx)
        self.current_from_slider = tkinter.DoubleVar(self, dy)
        self.voltage_from_dr = RoundedDoubleVar(self, x)
        self.current_from_dr = tkinter.DoubleVar(self, y)

        self.voltage_from_slider.trace_add('write',
                                           lambda *args: self.update_max_voltage(self.voltage_from_slider, *args))
        self.current_from_slider.trace_add('write',
                                           lambda *args: self.update_max_current(self.current_from_slider, *args))
        self.voltage_from_dr.trace_add('write', lambda *args: self.update_min_voltage(self.voltage_from_dr, *args))
        self.current_from_dr.trace_add('write', lambda *args: self.update_min_current(self.current_from_dr, *args))

        self.duck_dr = DraggableRectangle(rect, self.voltage_from_dr, self.duck_bg, self.current_from_dr)
        self.duck_dr.connect()

        self.current_max_label = tkinter.Label(self, text='{:.3f}'.format(dy / self.parent.micro), width=8)
        self.current_min_label = tkinter.Label(self, text='{:.3f}'.format(y / self.parent.micro), width=8)
        self.voltage_max_label = tkinter.Label(self, text='{:.2f}'.format(dx))
        self.voltage_min_label = tkinter.Label(self, text='{:.2f}'.format(x))

        self.duck_slider_v = ttk.Scale(self,
                                       from_=0,
                                       to_=max(self.parent.ec_data.V) - min(self.parent.ec_data.V),
                                       length=300,
                                       variable=self.voltage_from_slider)
        self.duck_slider_ua = ttk.Scale(self,
                                        length=250,
                                        from_=max(self.parent.ec_data.uA) - min(self.parent.ec_data.uA),
                                        to_=0,
                                        variable=self.current_from_slider,
                                        orient=tkinter.VERTICAL)

        self.current_max_label.grid(row=0, column=0)
        self.current_min_label.grid(row=1, column=0)
        self.voltage_min_label.grid(row=3, column=2)
        self.voltage_max_label.grid(row=3, column=3)

        self.duck_slider_ua.grid(row=0, column=1, rowspan=2)
        self.duck_slider_v.grid(row=2, column=2, columnspan=2)

    def find_ec_range(self):
        logging.info("calculating ec ranges")
        if self.in_rectangle(self.parent.ec_data.id[0]):
            ec_start_inside = 0
        else:
            ec_start_inside = None
        for ec_id in self.parent.ec_data.id[1:-1]:
            if not ec_start_inside and self.in_rectangle(ec_id):
                ec_start_inside = ec_id
            elif ec_start_inside and not self.in_rectangle(ec_id):
                yield ec_start_inside, ec_id
                ec_start_inside = None
        if ec_start_inside:
            if self.in_rectangle(self.parent.ec_data.id[-1]):
                yield ec_start_inside, self.parent.ec_data.id[-1]
            else:
                yield ec_start_inside, self.parent.ec_data.id[-2]

    def in_rectangle(self, ec_id):
        point_x = self.parent.ec_data.V[ec_id]
        point_y = self.parent.ec_data.uA[ec_id]
        dx = self.voltage_from_slider.get()
        dy = self.current_from_slider.get()
        x = self.voltage_from_dr.get()
        y = self.current_from_dr.get()
        if x <= point_x <= x + dx and y <= point_y <= y + dy:
            return True
        else:
            return False

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

    def update_ec_range(self):
        ec_range = self.find_ec_range()
        self.parent.gui_model_q.put(("ec range", ec_range))

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
        self.current_max_label.configure(text="{:.3f} uA".format(current/self.parent.micro))
        self.update_ec_range()

    def update_min_current(self, ua, *args):
        current = ua.get()
        self.current_min_label.configure(text="{:.3f} uA".format(current/self.parent.micro))
        self.update_ec_range()

    def draw_ec_vline(self, voltage):
        self.duck_dr.reshape_x(float(voltage))
        self.voltage_max_label.configure(text="{} V".format(self.voltage_from_slider.round_string()))

    def draw_ec_ualine(self, current):
        self.duck_dr.reshape_y(float(current))
        self.current_max_label.configure(text="{} uA".format(self.current_from_slider.round_string()))



class OptoFrame(tkinter.Frame):
    def __init__(self, root, *args, **kwargs):
        tkinter.Frame.__init__(self, root, *args, **kwargs)
        self.parent = root
        self.opto_figure = Figure(figsize=(5, 3))
        self.opto_figure.patch.set_facecolor('#f0f0f0')
        canvas = FigureCanvasTkAgg(self.opto_figure, master=self)
        canvas.get_tk_widget().grid(row=1, columnspan=2)
        canvas.draw()

        self.opto_slider = ttk.Scale(self, from_=344, to_=1041, length=300)
        self.opto_slider.grid(row=2, columnspan=2)

        optical_file_button = ttk.Button(self,
                                         text="Redraw",
                                         command=self.redraw_opto)
        optical_reference_button = ttk.Button(self,
                                              text="Browse for optical data",
                                              command=self.askopenfile_opto_csv)

        optical_file_button.grid(row=3, column=0)
        optical_reference_button.grid(row=3, column=1)

    def redraw_opto(self):
        logging.info("redrawing optical data")
        # ec_range = self.find_ec_range()
        # self.parent.gui_model_q.put(("ec range", ec_range))
        self.parent.gui_model_q.put(("draw opto", None))

    def setup(self):
        pass

    def askopenfile_opto_csv(self):
        filename = filedialog.askopenfilename(initialdir=self.parent.initialdir, title="Select file",
                                              filetypes=(("csv files", "*.csv"), ("all files", "*.*")))
        if not filename:
            pass
        else:
            self.parent.gui_model_q.put(("load opto csv", filename))
            self.initialdir = os.path.dirname(filename)


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
