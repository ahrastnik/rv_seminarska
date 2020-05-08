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

    COMMUNICATION_TIMEOUT = 1.0  # [s]
    COMMUNICATION_RETRIES = 3  # Number of transmission retries

    def __init__(self):
        self._running = False
        self._queue_receive = Queue()
        self._queue_send = Queue()
        self._thread_receiver = Thread(name="receiver", target=self._receiver)
        self._thread_sender = Thread(name="sender", target=self._sender)

    def connect(self):
        """ Connect to the end system """
        if self._running:
            return

        self._running = True
        # Start threads
        self._thread_receiver.start()
        self._thread_sender.start()

    def disconnect(self):
        """ Disconnect from the end system """
        if not self._running:
            return

        self._running = False

        # Wait until threads finish
        self._thread_receiver.join(timeout=None)
        self._thread_sender.join(timeout=None)

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
        """
        Sends data to the end systems

        :param data:    Data to send to the end-system
        """
        pass

    @abstractmethod
    def _receive(self):
        """ Receives data from the end systems """
        pass

    def send(self, data):
        """
        Queue data for sending to the end system

        :param data:    Data to send to the end-system
        """
        self._queue_send.put(data)

    def receive(self, **kwargs):
        """
        Get queued data, that was received from the end-system

        :param kwargs:
        :return:        Queued data packet or None, if one wasn't found
        """
        try:
            data = self._queue_receive.get(**kwargs)
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
        START = 0xE0
        STOP = 0xE1
        BALL_POSITION = 0xF0
        TRAJECTORY_START = 0xF1
        TRAJECTORY_END = 0xF2
        TRAJECTORY_SAMPLE = 0xF3

    def __init__(self, ip=None, port_send=None, port_receive=None):
        self._ip = ip
        self._port_send = port_send
        self._port_receive = port_receive

        self._sock_send = None
        self._sock_receive = None

        super().__init__()

        # Connect immediately if all connection details were input
        if ip is not None and port_send is not None and port_receive is not None:
            self.connect()

    def connect(self, ip=None, port_send=None, port_receive=None):
        # Update connection settings
        if ip is not None:
            self._ip = ip
        if port_send is not None:
            self._port_send = port_send
        if port_receive is not None:
            self._port_receive = port_receive

        if self._sock_send is not None or self._sock_receive is not None:
            return

        # Create sender socket and connect to the server
        self._sock_send = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock_send.connect((self._ip, self._port_send))
        # Create receiver socket and bind address
        self._sock_receive = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock_receive.bind((self._ip, self._port_receive))

        # Start the sender and receiver threads
        super().connect()

    def disconnect(self):
        super().disconnect()

        # Close sockets
        if self._sock_send is not None:
            self._sock_send.close()
            self._sock_send = None

        if self._sock_receive is not None:
            self._sock_receive.close()
            self._sock_receive = None

    def _send(self, data):
        """
        Send a data to the controller

        :param data:    1D Numpy array
        """
        if self._sock_send is None:
            return

        # Encode data
        packet = struct.pack(">%sd" % data.size, *data.flatten("F"))
        # Send the data to the controller
        self._sock_send.sendto(packet, (self._ip, self._port_send))

    def _receive(self):
        """
        Receive a data from the controller

        :return:    1D Numpy array
        """
        if self._sock_receive is None:
            return None

        # Receive the data from the controller
        try:
            packet = self._sock_receive.recv(PhantomCommunicator.RECEIVE_BUFFER_SIZE)
            return struct.unpack(">%sd" % PhantomCommunicator.PACKET_SIZE, packet)
        except struct.error:
            print("Invalid data format received!")
        except ConnectionResetError:
            self.disconnect()

        return None

    def send_packet(self, packet_type, data=None, confirm=False):
        """
        Sends a single 4 byte packet to the Phantom controller

        :param packet_type: Type of the packet (PacketTypes)
        :param data:        1D Numpy array of size 3
                            Data to send in the packet, if the data is None zeros will be sent,
                            after the packet type
        :param confirm:     Does the packet expect a confirmation response?

        :return             Was the sending/confirmation successful
        """
        packet = np.zeros(PhantomCommunicator.PACKET_SIZE, dtype=np.double)
        # Assign packet type
        packet[0] = packet_type.value
        # Assign data, if any was provided
        if data is not None:
            packet[1:] = data
        # Send the packet to the controller
        self.send(packet)
        # Wait for confirmation
        if confirm:
            confirmation = self.receive(
                block=True, timeout=PhantomCommunicator.COMMUNICATION_TIMEOUT
            )
            if confirmation is None or confirmation[0] != packet_type.value:
                return False

        return True

    def send_start(self):
        """
        Notify the controller about the connection

        :return     Was the sending/confirmation successful
        """
        return self.send_packet(PhantomCommunicator.PacketTypes.START, confirm=True)

    def send_stop(self):
        """ Notify the controller about the disconnect """
        self.send_packet(PhantomCommunicator.PacketTypes.STOP)

    def send_ball_position(self, position):
        """
        Send the ball position coordinates to the controller

        :param position:    Ball coordinates as a 1D Numpy vector of size 3
        """
        self.send_packet(PhantomCommunicator.PacketTypes.BALL_POSITION, data=position)

    def send_trajectory(self, trajectory):
        """
        Send the new trajectory to the controller

        :param trajectory:  List of coordinates as tuples of length 3

        :return             Was the sending/confirmation successful
        """
        if len(trajectory) < 3:
            return False

        for retry in range(PhantomCommunicator.COMMUNICATION_RETRIES):
            # Signal trajectory transmission start
            if not self._send_trajectory_start(len(trajectory)):
                continue

            # Send all samples
            for sample in trajectory:
                self._send_trajectory_sample(sample)

            # Signal trajectory transmission stop
            if self._send_trajectory_end():
                return True

        return False

    def _send_trajectory_start(self, length):
        """
        Notify the trajectory transmission start

        :param length:  Number of samples in the trajectory

        :return     Was the sending/confirmation successful
        """
        packet = np.zeros(PhantomCommunicator.PACKET_SIZE - 1)
        packet[0] = length
        return self.send_packet(
            PhantomCommunicator.PacketTypes.TRAJECTORY_START, data=packet, confirm=True
        )

    def _send_trajectory_end(self):
        """
        Notify the trajectory transmission stop

        :return     Was the sending/confirmation successful
        """
        return self.send_packet(
            PhantomCommunicator.PacketTypes.TRAJECTORY_END, confirm=True
        )

    def _send_trajectory_sample(self, sample):
        """
        Send the trajectory sample

        :param sample:  Sample as tuple of length 3
        """
        self.send_packet(PhantomCommunicator.PacketTypes.TRAJECTORY_SAMPLE, data=sample)


if __name__ == "__main__":
    # Phantom communicator test
    from time import sleep

    comm = PhantomCommunicator(ip="127.0.0.1", port_send=6969, port_receive=9696)
    i = 0
    while True:
        x = np.arange(69, 73) + i
        comm.send(x)
        while True:
            message = comm.receive()
            if message is None:
                break
            print(message)

        sleep(1.0)
        i += 1
    comm.disconnect()
