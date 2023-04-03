import threading

from PyQt5 import QtCore, QtWidgets
from PyQt5.QtWidgets import QWidget

from kafka import KafkaConsumer
import msgpack

from .widgets.live_view_tab import LiveViewTab, LiveViewInputs
from .ui.main_window_ui import MainUI


class LiveView(QWidget, MainUI):
    """Main Live View class"""

    run_start_signal = QtCore.pyqtSignal()
    run_stop_signal = QtCore.pyqtSignal()
    # update_bar_signal = QtCore.pyqtSignal()

    def __init__(self, kafka_topic: str) -> None:
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
        if "main_motor" in start_document.keys():
            self.main_motor = start_document["main_motor"]
        else:
            self.main_motor = None
        if (
            "main_counter" in start_document.keys()
            and start_document["main_counter"] is not None
        ):
            self.main_counter = start_document["main_counter"]
        else:
            self.main_counter = None

        self.points_now = 0
        self.total_points = start_document["num_points"]

    def parse_descriptor_documents(self, descriptor_document: dict) -> None:
        """Parse descriptor Document and build the needed attributes"""
        self.run_start_hints = descriptor_document["hints"]

    def parse_stop_documents(self, stop_document: dict) -> None:
        """Parse stop Document and build the needed attributes"""
        pass

    def get_new_scan(self) -> None:
        """Keep checking kafka messages to know when a scan started/end. Emit signal for both cases"""
        # self.points_now = 0
        for message in self.consumer:
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

    def make_connections(self) -> None:
        """Connect signals to slots"""

        # Kafka Signals
        self.run_start_signal.connect(self.on_new_scan_add_tab)
        self.run_stop_signal.connect(self.stop_plot_threads)

        # QListWidget Signals
        self.list_widget.currentItemChanged.connect(self.change_stack_widget_index)

    def change_stack_widget_index(self) -> None:
        """Change stach widget to match the current selected row in the list widget"""
        self.stack_widget.setCurrentIndex(self.list_widget.currentRow())

    # def update_bar(self):
    #     def bar_percentage(current_points: int, total_points: int):
    #         return int((current_points/total_points)*100)
    #     self.progress_bar.setValue(bar_percentage(self.points_now, self.total_points))

    def get_only_plottable_counter(self) -> None:
        "Get only the counters that can be plotted. This information is gotten based in the hints field"
        for detector in self.detectors:
            if not self.run_start_hints[detector]["fields"]:
                # If field is [], them there is nothing to be read during a scan
                self.detectors.remove(detector)

    def build_live_view_inputs(self) -> LiveViewInputs:
        """Build inputs needed to insntantiate LiveViewTab"""
        obj = LiveViewInputs(
            self.kafka_topic,
            self.detectors,
            self.motors,
            self.total_points,
            self.main_counter,
            self.main_motor,
        )
        return obj

    def on_new_scan_add_tab(self) -> None:
        """Add new tab with the current scans plots after a new scan begin"""
        widget = QtWidgets.QWidget()
        vlayout = QtWidgets.QVBoxLayout()
        widget.setLayout(vlayout)
        self.get_only_plottable_counter()
        self.tab_widget = LiveViewTab(self.build_live_view_inputs())
        idx_now = self.list_widget.count() + 1
        item_scan = QtWidgets.QListWidgetItem(self.scan_identifier)
        self.list_widget.insertItem(idx_now, item_scan)
        vlayout.addWidget(self.tab_widget)
        # vlayout.addWidget(self.progress_bar)
        self.stack_widget.addWidget(widget)
        self.list_widget.setCurrentItem(item_scan)

    def stop_plot_threads(self):
        """Stop all plotting threads when a run stops"""
        try:
            self.tab_widget.stop_all_plot_threads()
        except AttributeError:
            pass
