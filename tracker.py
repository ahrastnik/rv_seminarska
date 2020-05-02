"""
Tracker module

Module provides object position tracking capability from an image/video.
"""
from abc import abstractmethod

import numpy as np
import cv2


class ObjectTracker:
    """ Abstract object tracker base class """

    def __init__(self, pixel_ratio, x_offset, y_offset):
        self._pixel_ratio = pixel_ratio
        self._x_offset = x_offset
        self._y_offset = y_offset

    @abstractmethod
    def find(self, image):
        """
        Locate the object on the image and return its position

        :param image:   Grayscale image as 2D Numpy array

        :return:        Object coordinates as 2D Numpy array
        """
        pass

    def _pixels_to_mm(self, coordinates):
        """
        Converts coordinates in pixels, to coordinates in millimeters

        :param coordinates:     Coordinates in pixels as Numpy array

        :return:                Coordinates in millimeters as Numpy array
        """
        pixel_coordinates = coordinates * self._pixel_ratio
        pixel_coordinates[:, :, 0] -= self._x_offset
        pixel_coordinates[:, :, 1] -= self._y_offset

        return pixel_coordinates


class BallTracker(ObjectTracker):
    def __init__(self, pixel_ratio, x_offset, y_offset):
        super().__init__(pixel_ratio, x_offset, y_offset)

    def find(self, image):
        image = cv2.medianBlur(image, 3)

        # Find circles
        pixel_coordinates = cv2.HoughCircles(
            image,
            cv2.HOUGH_GRADIENT,
            1,
            50,
            param1=50,
            param2=30,
            minRadius=10,
            maxRadius=30,
        )

        # Validate coordinates
        if pixel_coordinates is None:
            return None

        # Store all coordinates in a single array
        mm_coordinates = self._pixels_to_mm(pixel_coordinates)
        coordinates = np.empty(
            (*(pixel_coordinates.shape[:2]), pixel_coordinates.shape[2] * 2)
        )
        coordinates[:, :, :3] = pixel_coordinates
        coordinates[:, :, 3:] = mm_coordinates

        return coordinates
