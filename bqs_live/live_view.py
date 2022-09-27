#!/usr/bin/env python3

from kafka import KafkaConsumer
import msgpack

import threading
import time

import numpy

from silx.gui import qt
from silx.gui.plot import Plot1D
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtWidgets import QWidget
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import QTimer


class ThreadSafePlot1D(Plot1D):
    """Add a thread-safe :meth:`addCurveThreadSafe` method to Plot1D.
    """

    _sigAddCurve = qt.Signal(tuple, dict)
    """Signal used to perform addCurve in the main thread.

    It takes args and kwargs as arguments.
    """

    def __init__(self, parent=None):
        super(ThreadSafePlot1D, self).__init__(parent)
        # Connect the signal to the method actually calling addCurve
        self._sigAddCurve.connect(self.__addCurve)

    def __addCurve(self, args, kwargs):
        """Private method calling addCurve from _sigAddCurve"""
        self.addCurve(*args, **kwargs)

    def addCurveThreadSafe(self, *args, **kwargs):
        """Thread-safe version of :meth:`silx.gui.plot.Plot.addCurve`

        This method takes the same arguments as Plot.addCurve.

        WARNING: This method does not return a value as opposed to Plot.addCurve
        """
        self._sigAddCurve.emit(args, kwargs)


class UpdateThread(threading.Thread):
    """Thread updating the curve of a :class:`ThreadSafePlot1D`

    :param plot1d: The ThreadSafePlot1D to update."""

    def __init__(self, plot1d, detector, motor):
        self.plot1d = plot1d
        self.running = False
        self.counters_data = []
        self.motors_data = []
        self.detector = detector
        self.motor = motor
        self.consumer = KafkaConsumer("bluesky", value_deserializer=msgpack.unpackb)
        super(UpdateThread, self).__init__()

    def start(self):
        """Start the update thread"""
        self.running = True
        super(UpdateThread, self).start()

    def get_data(self) -> dict:
        for message in self.consumer:
            # message value and key are raw bytes -- decode if necessary!
            # e.g., for unicode: `message.value.decode('utf-8')`
            if message.value[0] == "event":
                self.counters_data.append(message.value[1]["data"][self.detector])
                self.motors_data.append(message.value[1]["data"][self.motor])
                return self.motors_data, self.counters_data


    def run(self):
        """Method implementing thread loop that updates the plot"""
        while self.running:
            time.sleep(.1)
            x, y = self.get_data()
            self.plot1d.addCurveThreadSafe(
                x, y)

    def stop(self):
        """Stop the update thread"""
        self.running = False
        self.join(2)

class MyWindow(QWidget):

    run_start_signal = QtCore.pyqtSignal()
    run_stop_signal = QtCore.pyqtSignal()

    def __init__(self):
        super(MyWindow, self).__init__()
        self.consumer = KafkaConsumer("bluesky", value_deserializer=msgpack.unpackb)
        self.tab_dict = {}
        self.initUI()
        self.make_connections()
        t = threading.Thread(target=self.get_new_scan)
        t.daemon = True  # Dies when main thread (only non-daemon thread) exits.
        t.start()

    def get_new_scan(self):
        for message in self.consumer:
            # message value and key are raw bytes -- decode if necessary!
            # e.g., for unicode: `message.value.decode('utf-8')`
            # print(message)
            if message.value[0] == "start":
                self.run_start_signal.emit()
                self.detectors = message.value[1]["detectors"]
                self.motors = message.value[1]["motors"]
                print(self.detectors, self.motors)
            elif message.value[0] == "stop":
                self.run_stop_signal.emit()

    def initUI(self):
        """Init base UI components"""
        self.title = "Queue Server Live View"
        self.setWindowTitle(self.title)
        self.verticalLayout = QtWidgets.QVBoxLayout(self)
        self.verticalLayout.setObjectName("verticalLayout")
        self.tab_widget = QtWidgets.QTabWidget(self)
        self.verticalLayout.addWidget(self.tab_widget)

    def make_connections(self): 
        self.run_start_signal.connect(self.update_gui)
        self.run_stop_signal.connect(self.stop_plot_threads)

    def stop_plot_threads(self):
        """Stop all plot thread after the scan ended"""
        for key in self.tab_dict.keys():
            self.tab_dict[key]["plot_thread"].stop()

    def plot_tab(self, detector: str, motor: str):
        """Manage all plot tab and load an embedded display for it chunk of files selected in browser file menu"""
        self.tab_dict[detector] = {"widget": QtWidgets.QWidget()}
        self.tab_dict[detector]["tab_index"] = self.tab_widget.addTab(self.tab_dict[detector]["widget"], detector)
        self.tab_dict[detector]["layout"] = QtWidgets.QHBoxLayout()
        self.tab_dict[detector]["widget"].setLayout(self.tab_dict[detector]["layout"])
        self.tab_dict[detector]["plot"] = ThreadSafePlot1D()
        self.tab_dict[detector]["plot_thread"] = UpdateThread(self.tab_dict[detector]["plot"], detector, motor)
        self.tab_dict[detector]["plot_thread"].start()
        self.tab_dict[detector]["layout"].addWidget(self.tab_dict[detector]["plot"])
        # self.tab_widget.setCurrentIndex(self.tab_dict[detector]["tab_index"])

    def update_gui(self):
        self.delete_tab()
        for detector in self.detectors:
            self.plot_tab(detector, self.motors[0])

    def delete_tab(self):
        """Delte a tab from the tabWidget"""
        for i in range(len(self.tab_dict.keys())):
            self.tab_widget.removeTab(0)
        self.tab_dict = {}




def main():
    # global app
    app = qt.QApplication([])
    window = MyWindow()
    window.show()
    app.exec_()

    window.updateThread.stop()  # Stop updating the plot


if __name__ == '__main__':
    main()