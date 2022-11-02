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

        self.ec_items = None
        self.wavelength_range = None
        self.iodm_range = None  # todo!!!
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
                if order == 'λ(V)':
                    self.wavelength_range = data
                    try:
                        self.send_lbd_v()
                    except KeyError:
                        logging.error("optical file out of scope")
                elif order == 'lbd(V)':
                    self.wavelength_range = data
                    try:
                        self.send_lbd_v()
                    except KeyError:
                        logging.error("optical file out of scope")
                elif order == 'λ(meas)':
                    self.wavelength_range = data
                    try:
                        self.send_lbd_meas()
                    except KeyError:
                        logging.error("optical file out of scope")
                elif order == "IODM(V)":
                    self.wavelength_range = data
                    self.send_iodm_v()
                elif order == "IODM(meas)":
                    self.wavelength_range = data
                    self.send_iodm_meas()
                elif order == 'λ(V)+IODM(V)':
                    self.wavelength_range = data
                    self.send_iodm_lbd()
                elif order == 'lbd(V), IODM(V)':
                    self.wavelength_range = data
                    self.send_iodm_lbd()
                elif order == "draw opto cycle":
                    self.draw_opto_cycle()
                elif order == "draw opto" and not self.opto_dataset:
                    logging.info("load optical data before drawing")
                elif order == "draw ec cycle":
                    self.current_cycle = "Cycle {}".format(data)
                    self.ec_items_from_cycle(data)
                elif order == "wavelength range":
                    self.wavelength_range = data
                elif order == "load opto csv":
                    if self.ec_dataset:
                        try:
                            self.read_opto_cycle_csv(data)
                            self._model_gui_queue.put(("opto file loaded", 0))
                        except UnicodeDecodeError:
                            logging.error("optical file corrupted")
                    else:
                        logging.info("ec file not loaded")
                elif order == "load ec csv":
                    self.read_ec_csv(data)
                else:
                    logging.info("unrecognizable order: {}".format(order))

    def send_iodm_meas(self):
        wavelength_range_ids = self.calc_wavelength_range_ids()
        iodm = self.opto_dataset.send_IODM(self.ec_items, wavelength_range_ids)
        self._model_gui_queue.put(("IODM(meas)", iodm))

    def send_iodm_v(self):
        # wavelength_range_ids = self.calc_wavelength_range_ids()  # not used for automatic_IODM
        iodm_dict, wavelength_start = self.opto_dataset.automatic_IODM(self.ec_items, self.iodm_window_size)
        _, iodm = zip(*iodm_dict.items())
        v = [self.ec_dataset.V[item] for item in self.ec_items]
        self._model_gui_queue.put(("IODM(V)", (v, iodm)))

    def send_iodm_lbd(self):
        wavelength_range_ids = self.calc_wavelength_range_ids()
        fit_lbd_dict = self.opto_dataset.calc_auto_fit()
        if self.iodm_range is None:
            iodm_dict, iodm_wavelength_start, iodm_wavelength_stop = self.opto_dataset.automatic_IODM(self.ec_items, self.iodm_window_size)
            self.iodm_range = [iodm_wavelength_start, iodm_wavelength_stop]
        else:
            iodm_dict = self.opto_dataset.send_IODM(self.ec_items, self.iodm_range)
            iodm_wavelength_start = self.iodm_range[0]
            iodm_wavelength_stop = self.iodm_range[1]
        _, iodm = zip(*iodm_dict.items())
        v = [self.ec_dataset.V[item] for item in self.ec_items]
        #
        # ec_ids_transmission = {k: self.opto_dataset.transmission[k] for k in self.ec_items}
        # min_lbd_dict = self.opto_dataset.calc_min(ec_ids_transmission, wavelength_range_ids)
        self._model_gui_queue.put(('λ(V)+IODM(V)', (v, iodm, fit_lbd_dict)))
        self.write_csv(v, iodm, fit_lbd_dict, iodm_wavelength_start, iodm_wavelength_stop)

    def send_iodm_lbd_old(self):
        wavelength_range_ids = self.calc_wavelength_range_ids()
        if self.iodm_range is None:
            iodm_dict, iodm_wavelength_start, iodm_wavelength_stop = self.opto_dataset.automatic_IODM(self.ec_items, self.iodm_window_size)
            self.iodm_range = [iodm_wavelength_start, iodm_wavelength_stop]
        else:
            iodm_dict = self.opto_dataset.send_IODM(self.ec_items, self.iodm_range)
            iodm_wavelength_start = self.iodm_range[0]
            iodm_wavelength_stop = self.iodm_range[1]
        _, iodm = zip(*iodm_dict.items())
        v = [self.ec_dataset.V[item] for item in self.ec_items]
        #
        ec_ids_transmission = {k: self.opto_dataset.transmission[k] for k in self.ec_items}
        min_lbd_dict = self.opto_dataset.calc_min(ec_ids_transmission, wavelength_range_ids)
        self._model_gui_queue.put(('λ(V)+IODM(V)', (v, iodm, min_lbd_dict)))
        self.write_csv(v, iodm, min_lbd_dict, iodm_wavelength_start, iodm_wavelength_stop)

    def write_csv(self, v, iodm, min_lbd_dict, iodm_wavelength_start, iodm_wavelength_stop):
        _, lbd_min_array = zip(*min_lbd_dict.items())
        iodm_start = [iodm_wavelength_start]*len(self.ec_items)
        iodm_stop = [iodm_wavelength_stop] * len(self.ec_items)
        uA = [self.ec_dataset.uA[item] for item in self.ec_items]
        data = [v, uA, lbd_min_array, iodm, iodm_start, iodm_stop]
        data_np = np.array(data)
        data_vertical = data_np.transpose()
        header = 'U[V],I[A],lbd[nm],IODM,IODM range 1[nm], IODM range 2[nm]'
        np.savetxt(self.filename, data_vertical, delimiter=',', header=header)

    # def send_lbd_meas(self):
        # ec_ids_transmission = {k: self.opto_dataset.transmission[k] for k in self.ec_items}
        # wavelength_range_ids = self.calc_wavelength_range_ids()
        # min_lbd_dict = self.opto_dataset.calc_min(ec_ids_transmission, wavelength_range_ids)
        # self._model_gui_queue.put(("λ(meas)", min_lbd_dict))

    def calc_wavelength_range_ids(self):
        wvlgth_start = self.find_nearest_lambda(self.wavelength_range[0], self.opto_dataset.wavelength)
        wvlgth_stop = self.find_nearest_lambda(self.wavelength_range[0] + self.wavelength_range[1],
                                               self.opto_dataset.wavelength)
        wavelength_range_ids = [wvlgth_start, wvlgth_stop]
        return wavelength_range_ids

    def send_lbd_v(self):
        ec_ids_transmission = {k: self.opto_dataset.transmission[k] for k in self.ec_items}
        wavelength_range_ids = self.calc_wavelength_range_ids()
        min_lbd_dict = self.opto_dataset.calc_min(ec_ids_transmission, wavelength_range_ids)
        v = [self.ec_dataset.V[item] for item in self.ec_items]
        self._model_gui_queue.put(("λ(V)", (v, min_lbd_dict)))

    def convert_filename(self, filename):
        root = os.path.dirname(os.path.abspath(filename))
        prefix, filename = os.path.basename(filename).split('_',1)
        result_fname = os.path.join(root, filename)
        return result_fname

    @staticmethod
    def read_wavelengths():
        try:
            path = os.getcwd()
            wavelength = np.genfromtxt(path+r'\wavelength.txt', delimiter=',')[2:]
        except OSError:
            logging.error("no wavelength file, generating wavelength vector automatically")
            # todo data[0]
            wavelength = np.linspace(344.6122, 1041.1877, num=len(data[0])-2)
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
        wavelength = self.read_wavelengths()

        self.opto_cycles = dict.fromkeys(self.cycles.keys())
        tmp = dict.fromkeys(self.cycles.keys())

        for cycle in self.cycles:
            tmp[cycle] = []

        for num, row in enumerate(data):
            for cycle in self.cycles:
                if self.cycles[cycle][0] <= num <= self.cycles[cycle][1]:
                    row = row.split(',')
                    row = [int(x) for x in row]
                    tmp[cycle].append(row)
                else:
                    pass
        for cycle in tmp:
            if tmp[cycle]:
                new_cycle = OptoCycleDataset()
                new_cycle.wavelength = wavelength
                new_cycle.insert_opto_from_csv(tmp[cycle], self.cycles[cycle])
                self.opto_cycles[cycle] = new_cycle
            else:
                self.opto_cycles[cycle] = self.insert_placeholder_cycle(self.cycles[cycle])

        logging.info("optical file loaded")

    @staticmethod
    def insert_placeholder_cycle(cycles):
        new_cycle = OptoCycleDataset()
        new_cycle.wavelength = [600, 700, 800, 900]
        input = [[0.1, -0.1, -0.1, 0.1]] * len(cycles)
        new_cycle.insert_opto_from_csv(input, cycles)
        return new_cycle

    def draw_opto_cycle(self):
        logging.info("drawing optical data for {}".format(self.current_cycle))
        if self.opto_cycles:
            opto_cycle = self.opto_cycles[self.current_cycle]
            self._model_gui_queue.put(("draw opto", opto_cycle))
        else:
            logging.info("optical file not loaded")

    def read_ec_csv(self, filename):
        logging.info("reading file: {}".format(filename))
        new_ec_dataset = ElectroChemSet()
        new_ec_dataset.insert_ec_data2(filename)
        self.ec_dataset = new_ec_dataset
        self.cycles = self.ec_dataset.cycles
        self._model_gui_queue.put(("number of cycles", len(self.ec_dataset.cycles)))
        self.ec_items_from_cycle(0)
        self.current_cycle = "Cycle 0"

    def ec_items_from_cycle(self, cycle_number=0):
        cycle = f'Cycle {cycle_number}'
        if self.ec_dataset:
            cycle_ec_uA = self.ec_dataset.uA[self.cycles[cycle][0]:
                                             self.cycles[cycle][1]]
            cycle_ec_V = self.ec_dataset.V[self.cycles[cycle][0]:
                                           self.cycles[cycle][1]]
            self._model_gui_queue.put(("draw ec", (cycle_ec_uA, cycle_ec_V)))
        else:
            logging.info("ec file not loaded")

    @staticmethod
    def find_nearest_lambda(lambda_nm, wavelength_array):
        # find nearest value, return index
        diff = [abs(item - lambda_nm) for item in wavelength_array]
        idx = diff.index(min(diff))
        return idx
