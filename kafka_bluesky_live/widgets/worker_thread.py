import threading
import time

from kafka import KafkaConsumer
import msgpack
from silx.gui.plot import Plot1D

THREAD_WAIT = 0.1


class UpdateThread(threading.Thread):
    """Thread updating the curve of a :class:`ThreadSafePlot1D`

    :param plot1d: The ThreadSafePlot1D to update."""

    def __init__(
        self,
        kafka_topic: str,
        plot1d: Plot1D,
        detector: str,
        motor: str,
        total_points: int,
    ):
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
            self.plot1d.addCurveThreadSafe(x, y)
            if len(x) == self.total_points:
                break
            time.sleep(THREAD_WAIT)

    def stop(self):
        """Stop the update thread"""
        self.running = False
        self.join(2)
