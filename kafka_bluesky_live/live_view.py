#!/usr/bin/env python3

from os import path
import threading

from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtWidgets import QWidget
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QFrame

from kafka import KafkaConsumer
import msgpack

from .widgets.live_view_tab import LiveViewTab


class LiveView(QWidget):
    run_start_signal = QtCore.pyqtSignal()
    run_stop_signal = QtCore.pyqtSignal()
    # update_bar_signal = QtCore.pyqtSignal()

    def __init__(self, kafka_topic: str):
        super(LiveView, self).__init__()
        self.kafka_topic = kafka_topic
        self.consumer = KafkaConsumer(
            self.kafka_topic, value_deserializer=msgpack.unpackb
        )
        self.stacked_tabs = {}
        self.initUI()
        self.make_connections()
        t = threading.Thread(target=self.get_new_scan)
        t.daemon = True  # Dies when main thread (only non-daemon thread) exits.
        t.start()

    def parse_start_documents(self, start_document: dict) -> None:
        """Parse start Document and build the needed attributes"""
        self.scan_id = start_document["scan_id"]
        self.detectors = start_document["detectors"]
        self.start_hints = start_document["hints"]
        if "motors" in start_document.keys():
            self.motors = start_document["motors"]
        else:
            self.motors = None
        if "file_name" in start_document.keys():
            self.scan_identifier = start_document["file_name"]
        else:
            self.scan_identifier = "scan " + str(self.scan_id)
        self.points_now = 0
        self.total_points = start_document["num_points"]

    def parse_descriptor_documents(self, descriptor_document: dict) -> None:
        """Parse descriptor Document and build the needed attributes"""
        self.run_start_hints = descriptor_document["hints"]

    def parse_stop_documents(self, stop_document: dict) -> None:
        """Parse stop Document and build the needed attributes"""
        pass

    def get_new_scan(self) -> None:
        """Keep checking kafka message to know when a scan started/end. Emit signal for both cases"""
        # self.points_now = 0
        for message in self.consumer:
            # print(message.value[0])
            if message.value[0] == "start":
                self.parse_start_documents(message.value[1])
                continue
            if message.value[0] == "descriptor":
                self.parse_descriptor_documents(message.value[1])
                self.run_start_signal.emit()
                continue
            elif message.value[0] == "stop":
                self.parse_stop_documents(message.value[1])
                self.run_stop_signal.emit()
                continue
            # self.points_now += 1
            # self.update_bar_signal.emit()

    def initUI(self) -> None:
        """Init base UI components"""
        self.title = "Queue Server Live View"
        height = 800
        width = int(height * 16 / 9)
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
        self.cnpem_icon = self.cnpem_icon.scaled(
            img_size, img_size, QtCore.Qt.KeepAspectRatio
        )
        self.lnls_icon = QtGui.QPixmap(path.join(pixmap_path, "lnls-sirius.png"))
        self.lnls_icon = self.lnls_icon.scaled(
            img_size, img_size, QtCore.Qt.KeepAspectRatio
        )

    def build_initial_screen_widget(self) -> None:
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
        widget = QtWidgets.QWidget()
        vlayout = QtWidgets.QVBoxLayout()
        widget.setLayout(vlayout)
        self.get_only_plottable_counter()
        self.tab_widget = LiveViewTab(
            self.kafka_topic, self.detectors, self.motors, self.total_points
        )
        idx_now = self.list_widget.count() + 1
        item_scan = QtWidgets.QListWidgetItem(self.scan_identifier)
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
