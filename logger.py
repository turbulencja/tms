import logging
import queue
from os import makedirs
from logging.handlers import QueueHandler, QueueListener
from datetime import datetime


class LogQueue(object):
    def __init__(self):
        self.logs = queue.Queue()

    def write(self, string):
        self.logs.put(string)

    def flush(self):
        pass

    def get(self):
        try:
            msg = self.logs.get(block=False)
        except queue.Empty:
            return None
        else:
            return msg

    def __str__(self):
        return self.logs


def logger_setup():
    gui_log_queue = LogQueue()

    formatter = logging.Formatter('%(asctime)s: %(threadName)s: %(message)s')
    logging.basicConfig(stream=gui_log_queue, level=logging.INFO, format='%(asctime)s: %(threadName)s: %(message)s')
    logger = logging.getLogger()

    log_queue = queue.Queue()
    queue_handler = QueueHandler(log_queue)
    queue_handler.setLevel(logging.DEBUG)
    logger.addHandler(queue_handler)

    try:
        makedirs('TMS logs')
    except FileExistsError:
        pass

    now = datetime.now()
    dt_string = now.strftime("%Y.%m.%d")
    file_handler = logging.FileHandler("TMS logs/"+dt_string+"_TMS log.log")
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.DEBUG)

    listener = QueueListener(log_queue, file_handler)
    listener.start()
    #todo: stop listener on closing window
    return gui_log_queue
