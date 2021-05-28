import tms_exceptions as tms_exc
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
                if record[0] == "load db file":
                    self.connect_db(record[1])
                elif record[0] == "draw opto":
                    self._ctrl_model_q.put(record)
                else:
                    logging.info("unrecognizable input from gui: {}".format(record))

    def connect_db(self, db_fpath):
        self._ctrl_model_q.put(('connect to db', db_fpath))
        self.draw_ec()

    def draw_ec(self):
        self._ctrl_model_q.put(('draw ec'))

    def draw_opto(self):
        self._ctrl_model_q.put('draw opto')

    @staticmethod
    def read_csv(filename):
        try:
            data = np.genfromtxt(filename, delimiter=',')
            return data
        except OSError:
            pass

