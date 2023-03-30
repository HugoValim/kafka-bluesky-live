#!/usr/bin/env python3

from os import path
import threading
import time
import atexit

from silx.gui import qt
from silx.gui.plot import Plot1D
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtWidgets import QWidget
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QFrame

from kafka import KafkaConsumer
import msgpack
import numpy

THREAD_WAIT = 0.1

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

    def __init__(self, kafka_topic: str, plot1d: Plot1D, detector: str, motor: str, total_points: int):
        super(UpdateThread, self).__init__()
        self.plot1d = plot1d
        self.total_points = total_points
        self.running = False
        self.counters_data = []
        self.motors_data = []
        self.detector = detector
        self.motor = motor
        self.consumer = KafkaConsumer(kafka_topic, value_deserializer=msgpack.unpackb)
        

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
                if self.motor is not None:
                    self.motors_data.append(message.value[1]["data"][self.motor])
                else:
                    self.motors_data = [i for i in range(len(self.counters_data))]
                return self.motors_data, self.counters_data

    def run(self):
        """Method implementing thread loop that updates the plot"""
        while self.running:
            x, y = self.get_data()
            self.plot1d.addCurveThreadSafe(
                x, y)
            if len(x) == self.total_points:
                break
            time.sleep(THREAD_WAIT)

    def stop(self):
        """Stop the update thread"""
        self.running = False
        self.join(2)

class LiveViewTab(QtWidgets.QTabWidget):

    def __init__(self, kafka_topic: str, detectors: list, motors: list, total_points: int, parent=None):
        super().__init__(parent)
        self.kafka_topic = kafka_topic
        self.detectors = detectors
        self.motors = motors
        self.total_points = total_points
        self.tab_dict = {}
        self.build_plots()

    def plot_tab(self, detector: str, motor: str) -> None:
        """Manage all plot tab creating a new one for each detector in the scan. The first passed motor is passed to be x axis"""
        self.tab_dict[detector] = {"widget": QtWidgets.QWidget()}
        self.tab_dict[detector]["tab_index"] = self.addTab(self.tab_dict[detector]["widget"], detector)
        self.tab_dict[detector]["layout"] = QtWidgets.QVBoxLayout()
        self.tab_dict[detector]["widget"].setLayout(self.tab_dict[detector]["layout"])
        self.tab_dict[detector]["plot"] = ThreadSafePlot1D()
        self.tab_dict[detector]["plot"].getXAxis().setLabel(motor)
        self.tab_dict[detector]["plot"].getYAxis().setLabel(detector)
        self.tab_dict[detector]["plot"].setGraphTitle(title=detector)
        self.tab_dict[detector]["plot"].setDefaultPlotPoints(True)
        self.tab_dict[detector]["plot_thread"] = UpdateThread(self.kafka_topic, self.tab_dict[detector]["plot"], detector, motor, self.total_points)
        self.tab_dict[detector]["plot_thread"].start()
        self.tab_dict[detector]["layout"].addWidget(self.tab_dict[detector]["plot"])
        # self.tab_widget.setCurrentIndex(self.tab_dict[detector]["tab_index"])

    def stop_all_plot_threads(self) -> None:
        """Stop all plot threads after the scan ended"""
        for key in self.tab_dict.keys():
            t = threading.Thread(target=lambda: self.stop_plot_threads(key))
            t.start()

    def stop_plot_threads(self, key):
        self.tab_dict[key]["plot_thread"].stop()

    def build_plots(self) -> None:
        """Update the window with the new plots when a new scan starts, deleting the previous tabs"""
        for detector in self.detectors:
            if self.motors is not None:
                self.plot_tab(detector, self.motors[0])
            else:
                self.plot_tab(detector, self.motors)

class LiveView(QWidget):

    run_start_signal = QtCore.pyqtSignal()
    run_stop_signal = QtCore.pyqtSignal()
    # update_bar_signal = QtCore.pyqtSignal()
    
    def __init__(self, kafka_topic: str):
        super(LiveView, self).__init__()
        self.kafka_topic = kafka_topic
        self.consumer = KafkaConsumer(self.kafka_topic, value_deserializer=msgpack.unpackb)
        self.stacked_tabs = {}
        self.initUI()
        self.make_connections()
        t = threading.Thread(target=self.get_new_scan)
        t.daemon = True  # Dies when main thread (only non-daemon thread) exits.
        t.start()

    def get_new_scan(self) -> None:
        """Keep checking kafka message to know when a scan started/end. Emit signal for both cases"""
        # self.points_now = 0
        for message in self.consumer:
            # print(message.value[0])
            if message.value[0] == "start":
                self.scan_id = message.value[1]["scan_id"]
                self.detectors = message.value[1]["detectors"]
                self.start_hints = message.value[1]["hints"]
                if "motors" in message.value[1].keys():
                    self.motors = message.value[1]["motors"]
                else:
                    self.motors = None
                self.points_now = 0
                self.total_points = message.value[1]['num_points']
                continue
            if message.value[0] == "descriptor":
                self.run_start_hints = message.value[1]["hints"]
                self.run_start_signal.emit()
                continue
            elif message.value[0] == "stop":
                self.run_stop_signal.emit()
                continue
            # self.points_now += 1
            # self.update_bar_signal.emit()

    def initUI(self) ->  None:
        """Init base UI components"""
        self.title = "Queue Server Live View"
        height = 800
        width = int(height*16/9)
        self.resize(width, height)
        self.setWindowTitle(self.title)
        self.build_main_screen_layout()

    def make_connections(self) -> None:
        """Connect signals to slots"""

        # Kafka Signals
        self.run_start_signal.connect(self.on_new_scan_add_tab)
        self.run_stop_signal.connect(self.stop_plot_threads)   

        # QListWidget Signals
        self.list_widget.currentItemChanged.connect(self.change_stack_widget_index)


    def build_icons_pixmap(self):
        """Build used icons"""
        img_size = 150
        pixmap_path = path.join(path.dirname(path.realpath(__file__)), "icons")
        self.cnpem_icon = QtGui.QPixmap(path.join(pixmap_path, "cnpem.png"))
        self.cnpem_icon = self.cnpem_icon.scaled(img_size, img_size, QtCore.Qt.KeepAspectRatio)
        self.lnls_icon = QtGui.QPixmap(path.join(pixmap_path, "lnls-sirius.png"))
        self.lnls_icon = self.lnls_icon.scaled(img_size, img_size, QtCore.Qt.KeepAspectRatio)


    def build_initial_screen_widget(self) ->  None:
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

        grid_layout.addWidget(title_label, 0, 1)
        grid_layout.addWidget(lnls_img_label, 1, 2)
        grid_layout.addWidget(cnpem_img_label, 1, 0)
        grid_layout.addWidget(waiting_label, 2, 1)

        main_screen_widget = QFrame()
        main_screen_widget.setLayout(grid_layout)

        return main_screen_widget

    def build_main_screen_layout(self):
        self.stack_widget = QtWidgets.QStackedWidget(self)

        self.frame_main = QFrame()
        self.frame_main.setFrameShape(QFrame.StyledPanel)

        self.list_widget = QtWidgets.QListWidget(self)
        self.list_widget.setFixedWidth(250)
        self.list_widget.addItem("main")

        self.horizontalLayout = QtWidgets.QHBoxLayout(self)
        self.horizontalLayout.addWidget(self.list_widget)
        self.horizontalLayout.addWidget(self.frame_main)
        self.verticalLayout = QtWidgets.QVBoxLayout()
        self.frame_main.setLayout(self.verticalLayout)
        
        self.verticalLayout.addWidget(self.stack_widget)
        self.stack_widget.addWidget(self.build_initial_screen_widget())

    def change_stack_widget_index(self):
        self.stack_widget.setCurrentIndex(self.list_widget.currentRow())

    # def update_bar(self):
    #     def bar_percentage(current_points: int, total_points: int):
    #         return int((current_points/total_points)*100)
    #     self.progress_bar.setValue(bar_percentage(self.points_now, self.total_points))

    def get_only_plottable_counter(self):
        "Get only the counters that can be plotted. This information is gotten based in the hints field"
        for detector in self.detectors:
            if not self.run_start_hints[detector]["fields"]:
                # If field is [], them there is nothing to be read during a scan
                self.detectors.remove(detector)

    def on_new_scan_add_tab(self):
        """Add new tab with plot after a new scan begin"""
        widget =  QtWidgets.QWidget()
        vlayout = QtWidgets.QVBoxLayout()
        widget.setLayout(vlayout)
        self.get_only_plottable_counter()
        self.tab_widget = LiveViewTab(self.kafka_topic, self.detectors, self.motors, self.total_points)
        idx_now = self.list_widget.count() + 1
        item_scan = QtWidgets.QListWidgetItem("scan " + str(self.scan_id))
        self.list_widget.insertItem(idx_now, item_scan)
        vlayout.addWidget(self.tab_widget)
        # vlayout.addWidget(self.progress_bar)
        self.stack_widget.addWidget(widget)
        self.list_widget.setCurrentItem(item_scan)

    def stop_plot_threads(self):
        try:
            self.tab_widget.stop_all_plot_threads()
        except AttributeError:
            pass        
        

