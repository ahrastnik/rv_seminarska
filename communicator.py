"""
Communicator module

Module provides the necessary functionality for communicating with the end system.
"""
import socket
import struct
from threading import Thread
from queue import Queue, Empty
from abc import abstractmethod
from enum import Enum

import numpy as np


class Communicator:
    """
    Abstract Communicator base class

    The Communicator defines a UI safe - general interface, for creating
    communication handlers, which connect to end systems, based on defined protocols.
    """

    COMMUNICATION_TIMEOUT = 2.0  # [s]

    def __init__(self, auto_start=True):
        self._running = False
        self._queue_receive = Queue()
        self._queue_send = Queue()

        if auto_start:
            self.start()

    def start(self):
        """ Starts the communicator """
        if self._running:
            return

        self._running = True
        # Start the receiver
        thread_receiver = Thread(name="receiver", target=self._receiver)
        thread_receiver.start()
        # Start the sender
        thread_sender = Thread(name="sender", target=self._sender)
        thread_sender.start()

    def stop(self):
        """ Stops the communicator """
        if not self._running:
            return

        self._running = False

    def _receiver(self):
        while self._running:
            data = self._receive()
            if data is None:
                continue

            self._queue_receive.put_nowait(data)

    def _sender(self):
        while self._running:
            try:
                data = self._queue_send.get(
                    block=True, timeout=Communicator.COMMUNICATION_TIMEOUT
                )
                self._queue_send.task_done()

                if data is not None:
                    self._send(data)
            except Empty:
                continue

    @abstractmethod
    def _send(self, data):
        """ Sends data to the end systems """
        pass

    @abstractmethod
    def _receive(self):
        """ Receives data from the end systems """
        pass

    @abstractmethod
    def connect(self):
        """ Connect to the end system """
        pass

    @abstractmethod
    def disconnect(self):
        """ Disconnect from the end system """
        pass

    def send(self, data):
        """ Send data to the end system """
        self._queue_send.put(data)

    def receive(self):
        """ Receive data from the end system """
        try:
            data = self._queue_receive.get_nowait()
            self._queue_receive.task_done()
            return data
        except Empty:
            return None


class PhantomCommunicator(Communicator):
    """
    Phantom positioning system communicator class

    The Phantom Communicator is designed to communicate with the Matlab-Simulink controller via UDP.
    """

    RECEIVE_BUFFER_SIZE = 4096  # [bytes]
    PACKET_SIZE = 4  # [bytes]

    class PacketTypes(Enum):
        BALL_POSITION = 0x00
        TRAJECTORY_START = 0x01
        TRAJECTORY_END = 0x02
        TRAJECTORY_SAMPLE = 0x03

    def __init__(self, ip=None, port=None, **kwargs):
        self._ip = ip
        self._port = port

        self._sock = None
        # Connect immediately if all connection details were input
        if ip is not None and port is not None:
            self.connect()

        super().__init__(**kwargs)

    def connect(self, ip=None, port=None):
        # Update connection settings
        if ip is not None:
            self._ip = ip
        if port is not None:
            self._port = port

        if self._sock is not None:
            return

        # Create the socket and connect to the server
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.connect((self._ip, self._port))

    def disconnect(self):
        if self._sock is None:
            return

        self._sock.close()
        self._sock = None

    def _send(self, data):
        """
        Send a data to the controller

        :param data:    1D Numpy array
        """
        if self._sock is None:
            return

        # Encode data
        packet = struct.pack(">%sd" % data.size, *data.flatten("F"))
        # Send the data to the controller
        self._sock.sendto(packet, (self._ip, self._port))

    def _receive(self):
        """
        Receive a data from the controller

        :return:    1D Numpy array
        """
        if self._sock is None:
            return None

        # Receive the data from the controller
        try:
            data = self._sock.recvfrom(PhantomCommunicator.RECEIVE_BUFFER_SIZE)
        except ConnectionResetError:
            self.disconnect()
            return None

        return data

    def send_packet(self, packet_type, data=None):
        """
        Sends a single 4 byte packet to the Phantom controller

        :param packet_type: Type of the packet (PacketTypes)
        :param data:        1D Numpy array of size 3
                            Data to send in the packet, if the data is None zeros will be sent,
                            after the packet type
        """
        packet = np.zeros(PhantomCommunicator.PACKET_SIZE, dtype=np.double)
        # Assign packet type
        packet[0] = packet_type.value
        # Assign data, if any was provided
        if data is not None:
            packet[1:] = data
        # Send the packet to the controller
        self.send(packet)

    def send_ball_position(self, position):
        self.send_packet(PhantomCommunicator.PacketTypes.BALL_POSITION, position)

    def send_trajectory(self, trajectory):
        self._send_trajectory_start()

        for sample in trajectory:
            self._send_trajectory_sample(sample)

        self._send_trajectory_end()

    def _send_trajectory_start(self):
        self.send_packet(PhantomCommunicator.PacketTypes.TRAJECTORY_START)

    def _send_trajectory_end(self):
        self.send_packet(PhantomCommunicator.PacketTypes.TRAJECTORY_END)

    def _send_trajectory_sample(self, sample):
        self.send_packet(PhantomCommunicator.PacketTypes.TRAJECTORY_SAMPLE, sample)


if __name__ == "__main__":
    # Phantom communicator test
    from time import sleep

    comm = PhantomCommunicator(ip="127.0.0.1", port=6969, auto_start=True)
    print("Client connected!")
    i = 0
    while True:
        X = np.arange(69, 72) + i
        comm.send(X)
        # message = comm.receive()
        # if message is not None:
        #     print(message)
        #     if message == "off":
        #         break
        sleep(1.0)
        i += 1
    comm.disconnect()
