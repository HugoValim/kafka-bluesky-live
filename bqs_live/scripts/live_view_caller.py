#!/usr/bin/env python3

from silx.gui import qt
import argparse

from bqs_live import LiveView

def parse_args() ->  None:

    parser = argparse.ArgumentParser(description='Live view for Bluesky Queue Server scans')
    parser.add_argument('kafka-topic', metavar='topic name', type=str,
                        help='Name of the kafka-topic streaming the scan')
    args = parser.parse_args()
    dict_args = vars(args)
    return dict_args


def main() -> None:
    # global app
    app = qt.QApplication([])
    cmd_args = parse_args()
    topic = cmd_args["kafka-topic"]
    window = LiveView(topic)
    window.show()
    app.exec_()

    window.updateThread.stop()  # Stop updating the plot


if __name__ == '__main__':
    main()