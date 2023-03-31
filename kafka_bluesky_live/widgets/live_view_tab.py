import threading

from PyQt5 import QtWidgets

from .thread_safe_plot import ThreadSafePlot1D
from .worker_thread import UpdateThread


class LiveViewTab(QtWidgets.QTabWidget):
    def __init__(
        self,
        kafka_topic: str,
        detectors: list,
        motors: list,
        total_points: int,
        parent=None,
    ):
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
        self.tab_dict[detector]["tab_index"] = self.addTab(
            self.tab_dict[detector]["widget"], detector
        )
        self.tab_dict[detector]["layout"] = QtWidgets.QVBoxLayout()
        self.tab_dict[detector]["widget"].setLayout(self.tab_dict[detector]["layout"])
        self.tab_dict[detector]["plot"] = ThreadSafePlot1D()
        self.tab_dict[detector]["plot"].getXAxis().setLabel(motor)
        self.tab_dict[detector]["plot"].getYAxis().setLabel(detector)
        self.tab_dict[detector]["plot"].setGraphTitle(title=detector)
        self.tab_dict[detector]["plot"].setDefaultPlotPoints(True)
        self.tab_dict[detector]["plot_thread"] = UpdateThread(
            self.kafka_topic,
            self.tab_dict[detector]["plot"],
            detector,
            motor,
            self.total_points,
        )
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
