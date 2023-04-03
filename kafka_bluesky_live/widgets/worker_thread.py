import threading
from dataclasses import dataclass

from kafka import KafkaConsumer
import msgpack
from silx.gui.plot import Plot1D


@dataclass
class UpdateThreadInputs:
    kafka_topic: str
    plot1d: Plot1D
    detector: str
    motor: str
    total_points: int


class UpdateThread(threading.Thread):
    """Thread updating the curve of a :class:`ThreadSafePlot1D`

    :param plot1d: The ThreadSafePlot1D to update."""

    def __init__(self, update_thread_inputs: UpdateThreadInputs) -> None:
        super(UpdateThread, self).__init__()
        self.consumer = KafkaConsumer(
            update_thread_inputs.kafka_topic, value_deserializer=msgpack.unpackb
        )
        self.plot1d = update_thread_inputs.plot1d
        self.detector = update_thread_inputs.detector
        self.motor = update_thread_inputs.motor
        self.total_points = update_thread_inputs.total_points
        self.running = False
        self.counters_data = []
        self.motors_data = []

    def start(self) -> None:
        """Start the update thread"""
        self.running = True
        super(UpdateThread, self).start()

    def get_data(self) -> list:
        """Get data based on the kafka topic"""
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
            elif message.value[0] == "stop":
                self.running = False
                return None, None

    def run(self) -> None:
        """Method implementing thread loop that updates the plot"""
        while self.running:
            x, y = self.get_data()
            if x is not None:
                self.plot1d.addCurveThreadSafe(x, y)

    def stop(self) -> None:
        """Stop the update thread"""
        self.join(1)
