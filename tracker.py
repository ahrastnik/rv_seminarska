"""
Tracker module

Module provides object position tracking capability from an image/video.
"""
from abc import abstractmethod

import numpy as np
import cv2


class ObjectTracker:
    """ Abstract object tracker base class """

    CALIBRATION_RETRIES = 10

    def __init__(self):
        self._pixel_ratio = 0.69
        self._x_offset = 0
        self._y_offset = 0
        self._calibrated = False

    @abstractmethod
    def find(self, image):
        """
        Locate the object on the image and return its position

        :param image:   Grayscale image as 2D Numpy array

        :return:        Object coordinates as 2D Numpy array
        """
        pass

    @abstractmethod
    def calibrate(self, image):
        """
        Calculate pixel to mm ratio

        :param image:   BGR image as 3D Numpy array

        :return:        Coordinates of calibration markers
        """
        pass

    def _pixels_to_mm(self, pixel_coordinates):
        """
        Converts coordinates in pixels, to coordinates in millimeters

        :param pixel_coordinates:     Coordinates in pixels as Numpy array

        :return:                Coordinates in millimeters as Numpy array
        """
        mm_coordinates = pixel_coordinates.copy()  # * self._pixel_ratio
        mm_coordinates[:, 0] -= self._x_offset
        mm_coordinates[:, 1] -= self._y_offset
        mm_coordinates[:, 2] = 0
        mm_coordinates[:, 0] *= self._pixel_ratio
        mm_coordinates[:, 1] *= -self._pixel_ratio

        return mm_coordinates

    def process_trajectory(self, trajectory):
        """
        Converts trajectory pixel coordinates to millimeters

        :param trajectory:  List of coordinates as tuples of size 3

        :return:            2D numpy array of size Nx3
        """
        trajectory_mm = np.asarray(trajectory, dtype=np.double)
        return self._pixels_to_mm(trajectory_mm)


class BallTracker(ObjectTracker):
    def __init__(self):
        super().__init__()
        self.previous_coord = np.array((0, 0, 0))
        self.treshold = np.array((0.001, 0.001, 0))

    def find(self, image):
        if not self._calibrated:
            return None

        # Find circles
        pixel_coordinates = cv2.HoughCircles(
            image,
            cv2.HOUGH_GRADIENT,
            1,
            25,
            param1=50,
            param2=25,
            minRadius=15,
            maxRadius=30,
        )

        # Validate coordinates
        if pixel_coordinates is None:
            return None
        pixel_coordinates = pixel_coordinates.reshape(pixel_coordinates.shape[1:])
        # Store all coordinates in a single array
        mm_coordinates = self._pixels_to_mm(pixel_coordinates)
        coordinates = np.empty(
            (pixel_coordinates.shape[0], pixel_coordinates.shape[1] * 2)
        )
        if np.all(abs(mm_coordinates - self.previous_coord) >= self.treshold):
            coordinates[:, 3:] = mm_coordinates
            self.previous_coord = mm_coordinates
        else:
            coordinates[:, 3:] = self.previous_coord
        coordinates[:, :3] = pixel_coordinates

        return coordinates

    def calibrate(self, image):

        imGray = cv2.cvtColor(image, cv2.COLOR_BGRA2GRAY)
        imgH = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        hue = imgH[:, :, 0]
        x_calib, y_calib, center = [1, 1, 1], [1, 1, 1], [1, 1, 1]
        found_x, found_y, found_center = False, False, False

        coord = cv2.HoughCircles(
            imGray,
            cv2.HOUGH_GRADIENT,
            1,
            25,
            param1=50,
            param2=25,
            minRadius=5,
            maxRadius=30,
        )
        if coord is None:
            return None
        coord = np.uint16(np.around(coord[0, :]))
        for (x, y, r) in coord:
            if hue[y, x] >= 80:  # blue ball
                x_calib = [x, y, r]
                found_x = True
            elif hue[y, x] <= 20:  # red bal
                center = [x, y, r]
                found_center = True
            else:  # green ball
                y_calib = [x, y, r]
                found_y = True

        if not (found_x and found_y and found_center):
            return None

        self._x_offset, self._y_offset = center[0], center[1]
        self._pixel_ratio = 0.1 / (
            (center[1] - y_calib[1] + x_calib[0] - center[0]) / 2
        )

        coordinates = np.array((x_calib, y_calib))
        self._calibrated = True
        return coordinates
