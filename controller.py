# import TMS_exceptions as tms_exc
import numpy as np
import threading
import logging
from queue import Empty


class Controller(threading.Thread):

    def __init__(self, **kwargs):
        threading.Thread.__init__(self)
        self.daemon = True

        self._ctrl_model_q = kwargs['ctrl_model_queue']
        self._ctrl_gui_q = kwargs['ctrl_gui_queue']
        self._model_ctrl_q = kwargs['model_ctrl_queue']
        self._gui_ctrl_q = kwargs['gui_ctrl_queue']

        self.start()

    def run(self):
        logging.info("controller running thread {}".format(threading.get_ident()))
        while True:
            try:
                record = self._gui_ctrl_q.get(block=False)
            except Empty:
                pass
            else:
                if record[0] == "load opto file":
                    self.open_opto_csv_file(record[1])
                elif record[0] == "load ec file":
                    self.open_ec_csv_file(record[1])
                else:
                    logging.info("unrecognizable input from gui: {}".format(record))

    def open_opto_csv_file(self, filename):
        opto_fname = filename.split("/")[-1]
        logging.info("reading opto file {}".format(opto_fname))
        # data = self.read_csv(filename)
        data = np.genfromtxt(filename, delimiter=',')
        wavelength = np.linspace(344.6, 1041.2, num=data.shape[1]-2)
        opto_record = ("opto file in", (opto_fname, wavelength, data))
        self._ctrl_model_q.put(opto_record)
        self.draw_opto(opto_fname)

    def open_ec_csv_file(self, filename):
        ec_fname = filename.split("/")[-1]
        logging.info("reading ec file {}".format(ec_fname))
        # data = self.read_csv(filename)
        data = np.genfromtxt(filename, delimiter=',')
        ec_record = ("ec data in", (ec_fname, data))
        self._ctrl_model_q.put(ec_record)
        self.draw_ec(ec_fname)

    def draw_ec(self, ec_fname):
        self._ctrl_model_q.put(('draw ec', ec_fname))

    def draw_opto(self, opto_fname):
        self._ctrl_model_q.put(('draw opto', opto_fname))

    @staticmethod
    def read_csv(filename):
        try:
            data = np.genfromtxt(filename, delimiter=',')
            return data
        except OSError:
            pass

