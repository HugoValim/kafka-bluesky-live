import threading
from dataclasses import dataclass

from PyQt5 import QtWidgets

from .thread_safe_plot import ThreadSafePlot1D
from .worker_thread import UpdateThread, UpdateThreadInputs


@dataclass
class LiveViewInputs:
    kafka_topic: str = None
    detectors: list = None
    motors: list = None
    total_points: int = None
    main_counter: str = None
    main_motor: str = None
    parent: QtWidgets = None


class LiveViewTab(QtWidgets.QTabWidget):
    def __init__(self, live_view_args: LiveViewInputs) -> None:
        super().__init__(live_view_args.parent)
        self.kafka_topic = live_view_args.kafka_topic
        self.detectors = live_view_args.detectors
        self.motors = live_view_args.motors
        self.total_points = live_view_args.total_points
        self.main_counter = live_view_args.main_counter
        self.main_motor = live_view_args.main_motor
        self.tab_dict = {}
        self.build_plots()

    def build_update_thread_inputs(
        self, detector: str, motor: str
    ) -> UpdateThreadInputs:
        """Build inputs needed to instantiate LiveViewTab"""
        obj = UpdateThreadInputs(
            self.kafka_topic,
            self.tab_dict[detector]["plot"],
            detector,
            motor,
            self.total_points,
        )
        return obj

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
            self.build_update_thread_inputs(detector, motor)
        )
        self.tab_dict[detector]["plot_thread"].start()
        self.tab_dict[detector]["layout"].addWidget(self.tab_dict[detector]["plot"])
        # self.tab_widget.setCurrentIndex(self.tab_dict[detector]["tab_index"])

    def stop_all_plot_threads(self) -> None:
        """Stop all plot threads after the scan ended"""
        for key in self.tab_dict.keys():
            t = threading.Thread(target=lambda: self.stop_plot_threads(key))
            t.start()

    def stop_plot_threads(self, key: str) -> None:
        """Kill a thread based on the counter name (key)"""
        self.tab_dict[key]["plot_thread"].stop()

    def set_x_axis(self) -> str:
        """Set x axis with a motor or points"""
        if self.motors is not None:
            if self.main_motor is not None:
                return self.main_motor
            return self.motors[0]
        else:
            return None

    def set_main_counter_tab_first(self) -> None:
        """Get the main counter and put it at the first tab"""
        if self.main_counter is not None:
            self.detectors.remove(self.main_counter)
            self.detectors.insert(0, self.main_counter)

    def build_plots(self) -> None:
        """Update the window with the new plots when a new scan starts, deleting the previous tabs"""
        self.set_main_counter_tab_first()
        for detector in self.detectors:
            self.plot_tab(detector, self.set_x_axis())
