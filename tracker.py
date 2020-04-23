"""
Tracker module

Module provides object position tracking capability from an image/video.
"""
from abc import abstractmethod


class ObjectTracker:
    """ Abstract object tracker base class """

    def __init__(self):
        pass

    @abstractmethod
    def find(self):
        """ Locate the object and return its position """
        pass


class BallTracker(ObjectTracker):
    def __init__(self):
        super().__init__()

    def find(self):
        pass
