#!/usr/bin/env python
import threading
import logging
import sqlite3
from ec_dataset import ElectroChemSet
from queue import Empty
from opto_dataset import OptoDatasetB
import numpy as np
import pandas as pd
import tms_exceptions as tms_exc
import os


class Model(threading.Thread):

    def __init__(self, **kwargs):
        threading.Thread.__init__(self)
        self.daemon = True
        self.db_name = None
        self.opto_dataset = None
        self.ec_dataset = None

        self.ec_items = None
        self.wavelength_range = None

        self._ctrl_model_queue = kwargs['ctrl_model_queue']
        self._model_ctrl_queue = kwargs['model_ctrl_queue']
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
                elif order == "cross section":
                    self.wavelength_range = data
                    pass
                elif order == "draw ec" and self.ec_dataset:
                    # todo fix
                    self.send_ec_data()
                elif order == "draw opto" and self.opto_dataset:
                    self.opto_dataset.ec_ids = self.ec_items
                    self._model_gui_queue.put(("draw opto", self.opto_dataset))
                elif order == "draw opto" and not self.opto_dataset:
                    logging.info("load optical data before drawing")
                elif order == "ec range":
                    self.ec_items_from_range(data)
                elif order == "wavelength range":
                    self.wavelength_range = data
                elif order == "load opto csv":
                    try:
                        self.read_opto_csv(data)
                    except UnicodeDecodeError:
                        logging.error("optical file corrupted")
                elif order == "load ec csv":
                    self.read_ec_csv(data)
                else:
                    logging.info("unrecognizable order: {}".format(order))

    def send_iodm_meas(self):
        wavelength_range_ids = self.calc_wavelength_range_ids()
        iodm = self.opto_dataset.send_IODM(self.ec_items, wavelength_range_ids, reference=0)
        self._model_gui_queue.put(("IODM(meas)", iodm))

    def send_iodm_v(self):
        wavelength_range_ids = self.calc_wavelength_range_ids()
        iodm_dict = self.opto_dataset.send_IODM(self.ec_items, wavelength_range_ids, reference=0)
        _, iodm = zip(*iodm_dict.items())
        v = [self.ec_dataset.V[item] for item in self.ec_items]
        self._model_gui_queue.put(("IODM(V)", (v, iodm)))

    def send_lbd_meas(self):
        # todo: refactor; should be done by opto_dataset
        ec_ids_transmission = {k: self.opto_dataset.transmission[k] for k in self.ec_items}
        wavelength_range_ids = self.calc_wavelength_range_ids()
        min_lbd_dict = self.opto_dataset.calc_min(ec_ids_transmission, wavelength_range_ids)
        self._model_gui_queue.put(("λ(meas)", min_lbd_dict))

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

    def read_opto_csv(self, filename):
        # filename = "dane/Kasia_2021.02.01/opto_2021_02_01_11_46_26.csv"
        logging.info("reading file: {}".format(filename))
        # df = pd.read_csv(filename)
        # data = df.to_numpy()
        data = np.genfromtxt(filename, delimiter=',', encoding='utf-8', dtype=int)
        logging.info("the shape of you {}".format(data.shape))
        new_opto_dataset = OptoDatasetB()
        new_opto_dataset.insert_opto_from_csv(data)
        path = os.getcwd()
        try:
            new_opto_dataset.wavelength = np.genfromtxt(path+r'\wavelengths.csv', delimiter=',')
        except OSError:
            logging.error("no wavelength file, generating wavelength vector automatically")
            new_opto_dataset.wavelength = np.linspace(344.6122, 1041.1877, num=len(data[0])-2)
        if self.ec_items:
            new_opto_dataset.ec_ids = self.ec_items
        else:
            new_opto_dataset.ec_ids = list(new_opto_dataset.transmission.keys())
        self.opto_dataset = new_opto_dataset
        logging.info("optical file loaded, drawing...")
        self._model_gui_queue.put(("draw opto", self.opto_dataset))

    def read_ec_csv(self, filename):
        # filename = "dane/Kasia_2021.02.01/ech_pr_2021_02_01_11_46_26.csv"
        logging.info("reading file: {}".format(filename))
        # df = pd.read_csv(filename)
        # data = df.to_numpy()
        data = np.genfromtxt(filename, delimiter=',')
        new_ec_dataset = ElectroChemSet()
        new_ec_dataset.insert_ec_csv(data)
        self.ec_dataset = new_ec_dataset
        self._model_gui_queue.put(("draw ec", self.ec_dataset))
        self._model_gui_queue.put(("send ec ranges", None))

    def ec_items_from_range(self, ec_ranges):
        ec_items = []
        for ec_range in ec_ranges:
            ec_items.extend(list(range(ec_range[0], ec_range[1])))
        self.ec_items = ec_items

    @staticmethod
    def find_nearest_lambda(lambda_nm, wavelength_array):
        # find nearest value, return index
        diff = [abs(item - lambda_nm) for item in wavelength_array]
        idx = diff.index(min(diff))
        return idx
