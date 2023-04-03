from os import path

from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QFrame

from kafka_bluesky_live.configs.main_window_config import MainWindowConfigs


class MainUI:
    """Class to be inherited in the main window, it holds the main screen UI layout"""

    def initUI(self) -> None:
        """Init base UI components"""
        height = MainWindowConfigs.height
        width = MainWindowConfigs.width
        self.resize(width, height)
        self.setWindowTitle(MainWindowConfigs.title)
        self.build_main_screen_layout()

    def build_icons_pixmap(self) -> None:
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
        self.background_path = path.join(pixmap_path, "background.jpg")

    def build_initial_screen_widget(self) -> None:
        """Build the main screen to be displayed before a scan start"""
        self.build_icons_pixmap()

        grid_layout = QtWidgets.QGridLayout()

        title_label = QtWidgets.QLabel(self)
        title_label.setText(MainWindowConfigs.title)
        title_label.setStyleSheet(
            "font-weight: bold; font-size: 30pt; background:transparent;"
        )
        title_label.setAlignment(Qt.AlignCenter)

        waiting_label = QtWidgets.QLabel(self)
        waiting_label.setText("Wainting for a scan to begin ...")
        waiting_label.setStyleSheet(
            "font-weight: bold; font-size: 18pt; background:transparent;"
        )
        waiting_label.setAlignment(Qt.AlignCenter)

        cnpem_img_label = QtWidgets.QLabel(self)
        cnpem_img_label.setPixmap(self.cnpem_icon)
        cnpem_img_label.setAlignment(Qt.AlignCenter)
        cnpem_img_label.setStyleSheet("background:transparent;")

        lnls_img_label = QtWidgets.QLabel(self)
        lnls_img_label.setPixmap(self.lnls_icon)
        lnls_img_label.setAlignment(Qt.AlignCenter)
        lnls_img_label.setStyleSheet("background:transparent;")

        grid_layout.addWidget(title_label, 0, 1)
        grid_layout.addWidget(lnls_img_label, 1, 2)
        grid_layout.addWidget(cnpem_img_label, 1, 0)
        grid_layout.addWidget(waiting_label, 2, 1)

        main_screen_widget = QFrame()
        main_screen_widget.setStyleSheet(
            "background-image: url({}); background-attachment: fixed".format(
                self.background_path
            )
        )
        main_screen_widget.setLayout(grid_layout)

        return main_screen_widget

    def build_main_screen_layout(self) -> None:
        """Build the main window showed in the UI initialization"""
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
