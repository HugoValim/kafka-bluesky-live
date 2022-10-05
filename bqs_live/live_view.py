#!/usr/bin/env python3

from os import path
import threading
import time

from silx.gui import qt
from silx.gui.plot import Plot1D
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtWidgets import QWidget
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import Qt

from kafka import KafkaConsumer
import msgpack
import numpy

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

    def __init__(self, kafka_topic: str, plot1d: Plot1D, detector: str, motor: str):
        self.plot1d = plot1d
        self.running = False
        self.counters_data = []
        self.motors_data = []
        self.detector = detector
        self.motor = motor
        self.consumer = KafkaConsumer(kafka_topic, value_deserializer=msgpack.unpackb)
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

class LiveView(QWidget):

    run_start_signal = QtCore.pyqtSignal()
    run_stop_signal = QtCore.pyqtSignal()

    def __init__(self, kafka_topic: str):
        super(LiveView, self).__init__()
        self.kafka_topic = kafka_topic
        self.consumer = KafkaConsumer(self.kafka_topic, value_deserializer=msgpack.unpackb)
        self.tab_dict = {}
        self.initUI()
        self.make_connections()
        t = threading.Thread(target=self.get_new_scan)
        t.daemon = True  # Dies when main thread (only non-daemon thread) exits.
        t.start()

    def get_new_scan(self) -> None:
        """Keep checking kafka message to know when a scan started/end. Emit signal for both cases"""
        for message in self.consumer:
            if message.value[0] == "start":
                self.run_start_signal.emit()
                self.detectors = message.value[1]["detectors"]
                self.motors = message.value[1]["motors"]
                print(self.detectors, self.motors)
            elif message.value[0] == "stop":
                self.run_stop_signal.emit()

    def initUI(self) ->  None:
        """Init base UI components"""
        self.title = "Queue Server Live View"
        height = 800
        width = int(height*16/9)
        self.resize(width, height)
        self.setWindowTitle(self.title)
        self.verticalLayout = QtWidgets.QVBoxLayout(self)
        self.verticalLayout.setObjectName("verticalLayout")
        self.tab_widget = QtWidgets.QTabWidget(self)
        self.verticalLayout.addWidget(self.tab_widget)
        self.build_initial_screen_tab()

    def build_icons_pixmap(self):
        """Build used icons"""
        img_size = 150
        pixmap_path = path.join(path.dirname(path.realpath(__file__)), "icons")
        self.cnpem_icon = QtGui.QPixmap(path.join(pixmap_path, "cnpem.png"))
        self.cnpem_icon = self.cnpem_icon.scaled(img_size, img_size, QtCore.Qt.KeepAspectRatio)
        self.lnls_icon = QtGui.QPixmap(path.join(pixmap_path, "lnls-sirius.png"))
        self.lnls_icon = self.lnls_icon.scaled(img_size, img_size, QtCore.Qt.KeepAspectRatio)

    def build_initial_screen_tab(self) ->  None:
        """Build the main screen to be displayed before a scan start"""
        self.build_icons_pixmap()
        grid_layout = QtWidgets.QGridLayout()
        title_label = QtWidgets.QLabel(self)
        title_label.setText("Bluesky Queueserver Live View")
        title_label.setStyleSheet("font-weight: bold; font-size: 30pt")
        title_label.setAlignment(Qt.AlignCenter)
        waiting_label = QtWidgets.QLabel(self)
        waiting_label.setText("Wainting for a scan to begin ...")
        waiting_label.setStyleSheet("font-weight: bold; font-size: 18pt")
        waiting_label.setAlignment(Qt.AlignCenter)
        cnpem_img_label = QtWidgets.QLabel(self)
        cnpem_img_label.setPixmap(self.cnpem_icon)
        cnpem_img_label.setAlignment(Qt.AlignCenter)
        lnls_img_label = QtWidgets.QLabel(self)
        lnls_img_label.setPixmap(self.lnls_icon)
        lnls_img_label.setAlignment(Qt.AlignCenter)
        initial_widget =  QtWidgets.QWidget()
        initial_widget.setLayout(grid_layout)
        idx = self.tab_widget.addTab(initial_widget, "Main")
        grid_layout.addWidget(title_label, 0, 1)
        grid_layout.addWidget(lnls_img_label, 1, 2)
        grid_layout.addWidget(cnpem_img_label, 1, 0)
        grid_layout.addWidget(waiting_label, 2, 1)

    def make_connections(self) -> None:
        """Connect signals to slots"""
        self.run_start_signal.connect(self.update_gui)
        self.run_stop_signal.connect(self.stop_plot_threads)

    def stop_plot_threads(self) -> None:
        """Stop all plot threads after the scan ended"""
        for key in self.tab_dict.keys():
            self.tab_dict[key]["plot_thread"].stop()

    def plot_tab(self, detector: str, motor: str) -> None:
        """Manage all plot tab creating a new one for each detector in the scan. The first passed motor is passed to be x axis"""
        self.tab_dict[detector] = {"widget": QtWidgets.QWidget()}
        self.tab_dict[detector]["tab_index"] = self.tab_widget.addTab(self.tab_dict[detector]["widget"], detector)
        self.tab_dict[detector]["layout"] = QtWidgets.QHBoxLayout()
        self.tab_dict[detector]["widget"].setLayout(self.tab_dict[detector]["layout"])
        self.tab_dict[detector]["plot"] = ThreadSafePlot1D()
        self.tab_dict[detector]["plot"].getXAxis().setLabel(motor)
        self.tab_dict[detector]["plot"].getYAxis().setLabel(detector)
        self.tab_dict[detector]["plot"].setGraphTitle(title=detector)
        self.tab_dict[detector]["plot"].setDefaultPlotPoints(True)
        self.tab_dict[detector]["plot_thread"] = UpdateThread(self.kafka_topic, self.tab_dict[detector]["plot"], detector, motor)
        self.tab_dict[detector]["plot_thread"].start()
        self.tab_dict[detector]["layout"].addWidget(self.tab_dict[detector]["plot"])
        # self.tab_widget.setCurrentIndex(self.tab_dict[detector]["tab_index"])

    def update_gui(self) -> None:
        """Update the window with the new plots when a new scan starts, deleting the previous tabs"""
        self.delete_tab()
        for detector in self.detectors:
            self.plot_tab(detector, self.motors[0])

    def delete_tab(self) ->  None:
        """Delte all tabs from the tabWidget"""
        for i in range(self.tab_widget.count()):
            self.tab_widget.removeTab(0)
        self.tab_dict = {}
