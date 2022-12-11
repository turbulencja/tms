#!/usr/bin/env python
import threading
import logging
from ec_dataset import ElectroChemSet
from queue import Empty
from opto_dataset import OptoCycleDataset
import numpy as np
import os


class Model(threading.Thread):

    def __init__(self, **kwargs):
        threading.Thread.__init__(self)
        self.daemon = True
        self.filename = None
        self.opto_cycles = None
        self.ec_dataset = None
        self.cycles = None
        self.current_cycle = None

        self.wavelength_range = None
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
                elif order == "wavelength range":
                    self.wavelength_range = data
                elif order == "load opto csv":
                    if not self.ec_dataset:
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
                else:
                    logging.info("unrecognizable order: {}".format(order))

    def send_iodm_meas(self):
        wavelength_range_ids = self.calc_wavelength_range_ids()
        iodm = self.opto_dataset.send_IODM(self.ec_items, wavelength_range_ids)
        self._model_gui_queue.put(("IODM(meas)", iodm))

    def send_iodm_v(self):
        cycle = self.opto_cycles[self.current_cycle]
        cycle_ec_V = self.ec_dataset.V[self.cycles[self.current_cycle][0]:
                                       self.cycles[self.current_cycle][1]]
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
        cycle_ec_V = self.ec_dataset.V[self.cycles[self.current_cycle][0]:
                                       self.cycles[self.current_cycle][1]]
        if len(cycle_ec_V) == len(iodm) == len(fit_lbd):
            self._model_gui_queue.put(('fit λ(V)+IODM(V)', (cycle_ec_V, iodm, fit_lbd, self.current_cycle)))
            self.write_csv(cycle_ec_V, iodm, fit_lbd_dict)
        else:
            logging.error("lengths of data arrays don't match")

    def write_csv(self, v, iodm, min_lbd_dict):
        _, lbd_min_array = zip(*min_lbd_dict.items())
        uA = self.ec_dataset.uA[self.cycles[self.current_cycle][0]:
                                self.cycles[self.current_cycle][1]]
        data = [v, uA, lbd_min_array, iodm]
        data_np = np.array(data)
        data_vertical = data_np.transpose()
        str_range = f"{self.iodm_range[0]:.2f}-{self.iodm_range[1]:.2f}"
        header = f"U[V],I[A],lbd[nm],IODM (range={str_range}[nm])"
        filename = self.filename.replace(".csv", f"_{self.current_cycle}.csv")
        np.savetxt(filename, data_vertical, delimiter=',', header=header)

    def send_lbd_v(self):
        cycle = self.opto_cycles[self.current_cycle]
        fit_lbd_dict = cycle.calc_auto_fit()
        fit_lbd = fit_lbd_dict.values()
        cycle_ec_V = self.ec_dataset.V[self.cycles[self.current_cycle][0]:
                                       self.cycles[self.current_cycle][1]]
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
        :param filename: path to file
        :return:
        """
        logging.info("reading file: {}".format(filename))
        self.filename = self.convert_filename(filename)
        data = open(filename)

        self.opto_cycles = dict.fromkeys(self.cycles.keys())
        tmp = dict.fromkeys(self.cycles.keys())

        for cycle in self.cycles:
            tmp[cycle] = []

        for num, row in enumerate(data):
            for cycle in self.cycles:
                if self.cycles[cycle][0] <= num <= self.cycles[cycle][1]:
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
                new_cycle.insert_opto_from_csv(tmp_array, self.cycles[cycle])
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

    def read_ec_csv(self, filename):
        logging.info("reading file: {}".format(filename))
        new_ec_dataset = ElectroChemSet()
        success = new_ec_dataset.insert_ec_data2(filename)
        if success:
            self.ec_dataset = new_ec_dataset
            self.cycles = self.ec_dataset.cycles
            self._model_gui_queue.put(("number of cycles", len(self.ec_dataset.cycles)))
            self.ec_items_from_cycle(0)
            self.current_cycle = "Cycle 0"
        else:
            pass

    def ec_items_from_cycle(self, cycle_number=0):
        cycle = f'Cycle {cycle_number}'
        if self.ec_dataset:
            cycle_ec_uA = self.ec_dataset.uA[self.cycles[cycle][0]:
                                             self.cycles[cycle][1]]
            cycle_ec_V = self.ec_dataset.V[self.cycles[cycle][0]:
                                           self.cycles[cycle][1]]
            self._model_gui_queue.put(("draw ec", (cycle_ec_uA, cycle_ec_V, cycle)))
        else:
            logging.info("ec file not loaded")

    @staticmethod
    def find_nearest_lambda(lambda_nm, wavelength_array):
        # find nearest value, return index
        diff = [abs(item - lambda_nm) for item in wavelength_array]
        idx = diff.index(min(diff))
        return idx
