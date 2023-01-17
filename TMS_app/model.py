#!/usr/bin/env python
import threading
import logging
from ec_dataset import ElectroChemSet, ElectroChemCycle
from queue import Empty
from opto_dataset import OptoCycleDataset
import numpy as np
import os


class Model(threading.Thread):

    def __init__(self, **kwargs):
        """
        self.filename - string with full path to file
        self.opto_cycles - dictionary with optical data cycles (max 3 cycles)
        self.ec_cycles - dictionary with ec data cycles (max 3 cycles)
        self.ec_dataset - ElectroChemSet - TO REMOVE
        self.cycles - dictionary; keys are cycles, values are ranges of ec measurements indices
        self.current_cycle - string; self.opto_cycles key pointing to current cycle
        self.iodm_range - list with first and last wavelength of iodm range
        self.iodm_window_size - approximate size of iodm wavelength window
        """
        threading.Thread.__init__(self)
        self.daemon = True
        self.filename = None
        self.opto_cycles = None
        self.ec_cycles = {}
        self.ec_dataset = None
        self.cycles = None
        self.current_cycle = None
        self.data_saving = None

        self.iodm_range = None  # nm
        self.iodm_window_size = 100  # nm

        self._gui_model_queue = kwargs['gui_model_queue']
        self._model_gui_queue = kwargs['model_gui_queue']

        self.start()

    def run(self):
        logging.info("model running thread {}".format(threading.get_ident()))
        while True:
            try:
                order, data = self._gui_model_queue.get()
            except Empty:
                pass
            else:
                if order == 'fit λ(V)':
                    try:
                        self.send_lbd_v()
                    except KeyError:
                        logging.error("optical file out of scope")
                elif order == "IODM(V)":
                    self.send_iodm_v()
                elif order == 'fit λ(V)+IODM(V)':
                    self.send_iodm_lbd()
                elif order == "draw opto cycle":
                    self.draw_opto_cycle()
                elif order == "draw ec cycle":
                    self.current_cycle = "Cycle {}".format(data)
                    self.ec_items_from_cycle(data)
                elif order == "load opto csv":
                    if len(self.ec_cycles) < 1:
                        logging.info("ec file not loaded")
                        return
                    try:
                        success = self.read_opto_cycle_csv(data)
                    except (UnicodeDecodeError, ValueError) as e:
                        logging.error("optical file corrupted")
                    if success:
                        self._model_gui_queue.put(("opto file loaded", 0))
                elif order == "load ec csv":
                    self.read_ec_csv(data)
                elif order == "save data":
                    if self.data_saving and self.data_saving['cycle'] == self.current_cycle:
                        self.write_csv()
                        self.save_boundary_spectra()
                    else:
                        logging.error("no data to save yet for the current cycle")
                else:
                    logging.info("unrecognizable order: {}".format(order))

    def send_iodm_v(self):
        cycle = self.opto_cycles[self.current_cycle]
        cycle_ec_V = self.ec_cycles[self.current_cycle].V
        if self.iodm_range is None:
            iodm_dict, wavelength_start, wavelength_stop = cycle.automatic_IODM(cycle.transmission.keys(),
                                                                                self.iodm_window_size)
            self.iodm_range = [wavelength_start, wavelength_stop]
        else:
            iodm_dict = cycle.send_IODM(cycle.transmission.keys(), self.iodm_range)
        _, iodm = zip(*iodm_dict.items())
        self._model_gui_queue.put(("IODM(V)", (cycle_ec_V, iodm, self.current_cycle)))

    def send_iodm_lbd(self):
        cycle = self.opto_cycles[self.current_cycle]
        fit_lbd_dict = cycle.calc_auto_fit()
        if self.iodm_range is None:
            iodm_dict, iodm_wavelength_start, iodm_wavelength_stop = cycle.automatic_IODM(cycle.transmission.keys(),
                                                                                          self.iodm_window_size)
            self.iodm_range = [iodm_wavelength_start, iodm_wavelength_stop]
        else:
            iodm_dict = cycle.send_IODM(cycle.transmission.keys(), self.iodm_range)
        _, iodm = zip(*iodm_dict.items())
        _, fit_lbd = zip(*fit_lbd_dict.items())
        cycle_ec_V = self.ec_cycles[self.current_cycle].V
        if len(cycle_ec_V) == len(iodm) == len(fit_lbd):
            self._model_gui_queue.put(('fit λ(V)+IODM(V)', (cycle_ec_V, iodm, fit_lbd, self.current_cycle)))
            self.data_saving = dict({"v": cycle_ec_V,
                                     "cycle": self.current_cycle,
                                     "iodm": iodm,
                                     "fit_lbd_dict": fit_lbd_dict})
        else:
            logging.error("lengths of data arrays don't match")

    def save_boundary_spectra(self):
        cycle_opto = self.opto_cycles[self.current_cycle]
        cycle_ec = self.ec_cycles[self.current_cycle]
        cycle_ec_idx0 = cycle_ec.id[0]
        cycle_ec.pick_significant_points()
        boundary_opto, boundary_keys = [], []
        for boundary_point in cycle_ec.id_dict:
            boundary_meas_idx = cycle_ec.id_dict[boundary_point]
            for idx in boundary_meas_idx:
                boundary_opto.append(cycle_opto.transmission[cycle_ec_idx0+idx])
                boundary_keys.append("{}={}[V],".format(boundary_point, cycle_ec.V[idx]))
        boundary_opto_np = np.array(boundary_opto)
        data_vertical = boundary_opto_np.transpose()
        header = "".join(boundary_keys)
        filename = self.filename.replace(".csv", f"_boundary_spectra_{self.current_cycle}.csv")
        try:
            np.savetxt(filename, data_vertical, delimiter=',', header=header, fmt="%d")
        except (PermissionError, FileNotFoundError) as e:
            if e == PermissionError:
                logging.error("close file before saving")
            else:
                logging.error("unable to save data to file. file path may be too long")

    def write_csv(self):
        v = self.data_saving['v']
        fit_lbd_dict = self.data_saving['fit_lbd_dict']
        iodm = self.data_saving['iodm']
        cycle = self.data_saving['cycle']
        _, lbd_min_array = zip(*fit_lbd_dict.items())
        uA = self.ec_cycles[self.current_cycle].uA
        data = [v, uA, lbd_min_array, iodm]
        data_np = np.array(data)
        data_vertical = data_np.transpose()
        str_range = f"{self.iodm_range[0]:.2f}-{self.iodm_range[1]:.2f}"
        header = f"U[V],I[A],lbd[nm],IODM (range={str_range}[nm])"
        filename = self.filename.replace(".csv", f"_{cycle}.csv")
        # U= "%.6f", I= "%.10e", lbd= "%.4f", IODM= "%.6f"
        precision = ["%.6f", "%.10e", "%.4f", "%.6f"]
        try:
            np.savetxt(filename, data_vertical, delimiter=',', header=header, fmt=precision)
        except PermissionError:
            logging.error("close all files before saving")

    def send_lbd_v(self):
        cycle = self.opto_cycles[self.current_cycle]
        fit_lbd_dict = cycle.calc_auto_fit()
        fit_lbd = fit_lbd_dict.values()
        cycle_ec_V = self.ec_cycles[self.current_cycle].V
        if len(cycle_ec_V) == len(fit_lbd):
            logging.info(f"plotting lbd(V) for {self.current_cycle}")
            self._model_gui_queue.put(("fit λ(V)", (cycle_ec_V, fit_lbd, self.current_cycle)))
        else:
            logging.warning("number of ec and optical measurements don't match")

    def convert_filename(self, filename):
        root = os.path.dirname(os.path.abspath(filename))
        prefix, filename = os.path.basename(filename).split('_', 1)
        result_fname = os.path.join(root, filename)
        return result_fname

    @staticmethod
    def read_wavelengths(length):
        try:
            path = os.getcwd()
            wavelength = np.genfromtxt(path + r'\wavelength.txt', delimiter=',')[2:]
        except OSError:
            logging.error("no wavelength file, generating wavelength vector automatically")
            wavelength = np.linspace(344.6122, 1041.1877, num=length)
        return wavelength

    def read_opto_cycle_csv(self, filename):
        """
        reading optical file into separate cycles
        :param filename: string path to file
        :return: bool success
        """
        logging.info("reading file: {}".format(filename))
        self.filename = self.convert_filename(filename)
        data = open(filename)

        self.opto_cycles = dict.fromkeys(self.ec_cycles.keys())
        tmp = dict.fromkeys(self.ec_cycles.keys())

        for cycle in self.ec_cycles:
            tmp[cycle] = []

        for num, row in enumerate(data):
            for cycle in self.ec_cycles:
                if self.ec_cycles[cycle].id[0] <= num <= self.ec_cycles[cycle].id[1]:
                    row = row.split(',')
                    try:
                        row = [int(x) for x in row]
                        tmp[cycle].append(row)
                    except ValueError:
                        logging.warning("This doesn't look like the right type of file")
                        return False
                else:
                    pass

        for cycle in tmp:
            if tmp[cycle]:
                tmp_array = np.array(tmp[cycle])[:, 2:]
                _, length = tmp_array.shape
                wavelength = self.read_wavelengths(length)
                new_cycle = OptoCycleDataset()
                new_cycle.wavelength = wavelength
                new_cycle.insert_opto_from_csv(tmp_array, self.ec_cycles[cycle].id)
                self.opto_cycles[cycle] = new_cycle
            else:
                logging.warning(f"missing {cycle}; generating empty cycle")
                self.opto_cycles[cycle] = self.insert_empty_cycle(self.cycles[cycle])

        logging.info("optical file loaded")
        return True

    @staticmethod
    def insert_empty_cycle(cycles):
        new_cycle = OptoCycleDataset()
        new_cycle.wavelength = [600, 700, 800, 900]
        input = [[0.1, -0.1, -0.1, 0.1]] * len(cycles)
        input = np.array(input)
        new_cycle.insert_opto_from_csv(input, cycles)
        return new_cycle

    def draw_opto_cycle(self):
        logging.info("drawing optical data for {}".format(self.current_cycle))
        if self.opto_cycles:
            opto_cycle = self.opto_cycles[self.current_cycle]
            self._model_gui_queue.put(("draw opto", (opto_cycle, self.current_cycle)))
        else:
            logging.info("optical file not loaded")

    def read_ec_csv_old(self, filename):
        logging.info("reading file: {}".format(filename))
        new_ec_dataset = ElectroChemSet()
        success = new_ec_dataset.insert_ec_data(filename)
        if success:
            self.ec_dataset = new_ec_dataset
            self.cycles = self.ec_dataset.cycles
            self._model_gui_queue.put(("number of cycles", len(self.ec_dataset.cycles)))
            self.ec_items_from_cycle(0)
            self.current_cycle = "Cycle 0"
        else:
            pass

    def read_ec_csv(self, filename):
        logging.info("reading file: {}".format(filename))
        success = self.read_ec_cycles_csv(filename)
        if success:
            self._model_gui_queue.put(("number of cycles", len(self.ec_cycles)))
            self.ec_items_from_cycle(0)
            self.current_cycle = "Cycle 0"
        else:
            pass

    def read_ec_cycles_csv(self, filename):
        data = open(filename)
        cycles_count = 0
        V, uA = [], []
        key, first_meas_id = None, None
        for num, row in enumerate(data):
            try:
                tmp_v, tmp_ua = row.split(', ')
                V.append(float(tmp_v))
                uA.append(float(tmp_ua))
            except ValueError:
                if row.startswith('Cycle'):
                    cycles_count = cycles_count + 1
                    row_number = num - cycles_count
                    if key:
                        # create a new cycle, populate ec_cycles_dict
                        new_ec_cycle = ElectroChemCycle(key, V=V, uA=uA, id=[first_meas_id, row_number])
                        self.ec_cycles[key] = new_ec_cycle
                        V, uA = [], []
                    key = row.split(', ')[0]
                    first_meas_id = row_number + 1
                else:
                    logging.warning("this doesn't seem like the right type of file")
                    return False
        if key:
            # adding last cycle to the cycles dictionary
            new_ec_cycle = ElectroChemCycle(key, V=V, uA=uA, id=[first_meas_id, num-cycles_count])
            self.ec_cycles[key] = new_ec_cycle
        else:
            # if ec file has no info on cycles then a single "cycle 0" is created
            new_ec_cycle = ElectroChemCycle('Cycle 0', V=V, uA=uA, id=[0, num])
            self.ec_cycles['Cycle 0'] = new_ec_cycle
        return True

    def ec_items_from_cycle(self, cycle_number=0):
        cycle = f'Cycle {cycle_number}'
        if len(self.ec_cycles) > 0:
            cycle_ec_uA = self.ec_cycles[cycle].uA
            cycle_ec_V = self.ec_cycles[cycle].V
            self._model_gui_queue.put(("draw ec", (cycle_ec_uA, cycle_ec_V, cycle)))
        else:
            logging.info("ec file not loaded")

    @staticmethod
    def find_nearest_lambda(lambda_nm, wavelength_array):
        # find nearest value, return index
        diff = [abs(item - lambda_nm) for item in wavelength_array]
        idx = diff.index(min(diff))
        return idx
