#!/usr/bin/env python
import threading
import logging
import sqlite3
from ec_dataset import ElectroChemSet, ElectroChemSetB
from queue import Empty
from opto_dataset import OptoDataset
from os import path, listdir
import numpy as np
# import TMS_exceptions as tms_exc


class Model(threading.Thread):

    def __init__(self, **kwargs):
        threading.Thread.__init__(self)
        self.daemon = True
        self.db_name = None

        self.db_names_list = []
        self._optical_data = {}
        self._optical_reference = []
        self._ec_data = {}

        self._ctrl_model_queue = kwargs['ctrl_model_queue']
        self._model_ctrl_queue = kwargs['model_ctrl_queue']
        self._gui_model_queue = kwargs['gui_model_queue']
        self._model_gui_queue = kwargs['model_gui_queue']

        self.start()

    def run(self):
        logging.info("model running thread {}".format(threading.get_ident()))
        while True:
            try:
                record = self._ctrl_model_queue.get()
            except Empty:
                pass
            else:
                if record[0] == "ec data in":
                    self.load_ec_data(record[1])
                    self.zip_ec_opto_dataset()
                elif record[0] == "opto file in":
                    self.load_opto_file(record[1])
                    self.zip_ec_opto_dataset()
                elif record[0] == "draw ec":
                    self.send_ec_data(record)
                elif record[0] == "draw opto":
                    self.send_opto_data(record)
                else:
                    logging.info("unrecognizable order from ctrl: {}".format(record))

    def check_databases(self):
        ''' checks dbs in directory '''
        f_names = [f for f in listdir('.') if path.isfile(f)]
        for f in f_names:
            if f.endswith('.sqlite3'):
                self.db_names_list.append(f)
            else:
                pass

    def setup_database(self, name):
        self.db_name = name + '.sqlite3'
        db_connection = sqlite3.connect(name+'.sqlite3')
        cursor = db_connection.cursor()
        ech_sql = """
        CREATE TABLE electrochemical_measurement(
            id integer PRIMARY KEY,
            current float NOT NULL,
            voltage float NOT NULL)"""
        cursor.execute(ech_sql)

        wvlngth_sql = """
        CREATE TABLE wavelength(
            id integer PRIMARY KEY,
            lambda float NOT NULL,
            UNIQUE (lambda))"""
        cursor.execute(wvlngth_sql)

        opto_sql = """
        CREATE TABLE optical_measurement(
            id integer PRIMARY KEY,
            ec_point_id integer NOT NULL,
            wavelength_id integer NOT NULL,
            transmission float NOT NULL,
            FOREIGN KEY (ec_point_id) REFERENCES electrochemical_measurement(id),
            FOREIGN KEY (wavelength_id) REFERENCES wavelength(id))"""
        cursor.execute(opto_sql)
        db_connection.close()

    def load_ec_data(self, ec_in):
        if ec_in[0] in self.db_names_list:
            db_connection = sqlite3.connect(ec_in[0]+'.sqlite3')
        else:
            self.setup_database(ec_in[0])
            db_connection = sqlite3.connect(ec_in[0]+'.sqlite3')

        cursor = db_connection.cursor()
        ech_records = [[num, uA, V] for num, [uA, V] in enumerate(ec_in[1])]
        cursor.executemany('INSERT INTO electrochemical_measurement VALUES(?,?,?);', ech_records)
        db_connection.commit()
        db_connection.close()

    def load_opto_data(self, opto_in):
        if opto_in[0] in self.db_names_list:
            db_connection = sqlite3.connect(opto_in[0]+'.sqlite3')
        else:
            self.setup_database(opto_in[0])
            db_connection = sqlite3.connect(opto_in[0]+'.sqlite3')
        cursor = db_connection.cursor()
        data_cut = opto_in[2][:, 2:]
        o_measurements = np.zeros([data_cut.size, 4])
        for meas_num, meas in enumerate(data_cut):
            for meas_point_num, meas_point in enumerate(meas):
                meas_point_abs_num = meas_num * data_cut.shape[1] + meas_point_num
                o_measurements[meas_point_abs_num] = [meas_point_abs_num, meas_num, meas_point_num, meas_point]
        cursor.executemany('INSERT INTO optical_measurement VALUES(?,?,?,?);', o_measurements)
        db_connection.commit()
        db_connection.close()

    def load_wavelength(self, wavelength, db_name):
        if db_name in self.db_names_list:
            db_connection = sqlite3.connect(db_name)
        else:
            self.setup_database(db_name)
            db_connection = sqlite3.connect(db_name)
        cursor = db_connection.cursor()
        wvlngth_records = [[num, lambda_nm] for num, lambda_nm in enumerate(wavelength)]
        cursor.executemany('INSERT INTO wavelength VALUES(?,?);', wvlngth_records)
        db_connection.commit()
        db_connection.close()

    def load_ec_data_(self, ec_in):
        new_ec = ElectroChemSet(ec_in[0])
        new_ec.V = ec_in[1][:, 0]
        new_ec.uA = ec_in[1][:, 1]
        self._ec_data[ec_in[0]] = new_ec

    def load_ec_data__(self, ec_in):
        new_ec = ElectroChemSetB(ec_in[0])
        new_ec.load_ec_data(ec_in[1][:, 1], ec_in[1][:, 0])

    def send_ec_data(self, order):
        ec_fname = order[1]
        try:
            ec_data = self._ec_data[ec_fname]
        except KeyError:
            logging.warning("no ec data under {}".format(ec_fname))
        else:
            self._model_gui_queue.put((order[0], ec_data))

    def load_opto_file(self, opto_in):
        new_opto = OptoDataset()
        new_opto.name = opto_in[0]
        new_opto.wavelength = opto_in[1]
        transmission = opto_in[2][:, 2:]
        new_opto.load_transmission_matrix(transmission)
        self._optical_data[new_opto.name] = new_opto

    def send_opto_data(self, order):
        opto_fname = order[1]
        try:
            opto_data = self._optical_data[opto_fname]
        except KeyError:
            logging.warning("no optical data under {}".format(opto_fname))
        else:
            self._model_gui_queue.put((order[0], opto_data))

    @staticmethod
    def connect_ec_opto_data(opto_meas, ec_point):
        opto_meas.ec_point = ec_point
        ec_point.opto_meas = opto_meas

    def zip_ec_opto_dataset(self):
        pass
        # for key in self._ec_data.keys():
            # print(self._ec_data[key].ec_set.keys())
        # for key in self._optical_data.keys():
            # print(self._optical_data[key].opto_set.keys())



