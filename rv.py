from enum import Enum

import numpy as np
import cv2
from mss import mss

from communicator import PhantomCommunicator
from tracker import BallTracker


WIN_NAME = "RV seminarska"
SERVER_IP = "127.0.0.1"
PORT_SEND = 6969
PORT_RECEIVE = 9696


class App:
    PIXEL_RATIO = 0.694
    X_OFFSET = 296
    Y_OFFSET = 278

    # Capture size limit
    CAPTURE_SIZE_LIMIT_X = 200
    CAPTURE_SIZE_LIMIT_Y = 100

    # Key list
    KEY_QUIT = "q"
    KEY_CAPTURE_AREA = "r"

    # Colors
    COLOR_DRAW = (255, 102, 102)
    COLOR_PASS = (150, 240, 150)
    COLOR_FAIL = (70, 70, 255)
    COLOR_MARK = (0, 255, 0)
    COLOR_TEXT = (255, 255, 255)

    class States(Enum):
        STATE_QUIT = -2
        STATE_HANDSHAKE = -1
        STATE_CAPTURE_AREA = 0
        STATE_TRACKING = 1

    class TrajectoryStates(Enum):
        STATE_DRAWING = 0
        STATE_TRANSMISSION_PASS = 1
        STATE_TRANSMISSION_FAIL = 2

    def __init__(self, name, server_ip, port_send, port_receive):
        self._name = name
        self._server_ip = server_ip
        self._port_send = port_send
        self._port_receive = port_receive

        self._state = App.States.STATE_HANDSHAKE

        # State - capture area
        self._selecting_capture = False
        self._capture_area = np.zeros([2, 2], dtype=np.int16)
        self._capture_coord = {"top": 400, "left": 400, "width": 400, "height": 400}
        self._screen_capture = None

        # State - tracking
        self._trajectory = []
        self._trajectory_state = App.TrajectoryStates.STATE_DRAWING
        self._drawing = False

        self.comm = PhantomCommunicator(
            ip=server_ip, port_send=port_send, port_receive=port_receive
        )
        self.tracker = BallTracker(App.PIXEL_RATIO, App.X_OFFSET, App.Y_OFFSET)

    @staticmethod
    def _draw_instruction(image, text, position=(50, 50), size=0.75, color=COLOR_TEXT):
        """
        Draws an instruction on the screen

        :param image:   Image on which to draw the text
        :param text:    Text to draw
        """
        cv2.putText(
            image, text, position, cv2.FONT_HERSHEY_SIMPLEX, size, color,
        )

    def _mouse_callback_select(self, event, x, y, flags, param):
        """ Handles capture area selection """
        if event == cv2.EVENT_MOUSEMOVE and self._selecting_capture:
            self._capture_area[1, :] = (x, y)
            return

        if event == cv2.EVENT_LBUTTONDOWN:
            self._capture_area[0, :] = (x, y)
            self._capture_area[1, :] = (x, y)
            self._selecting_capture = True
            return

        elif event == cv2.EVENT_LBUTTONUP:
            # Calculate capture coordinates
            self._capture_coord["top"] = (
                int(self._capture_area[0, 1])
                if self._capture_area[0, 1] < self._capture_area[1, 1]
                else int(self._capture_area[1, 1])
            )
            self._capture_coord["left"] = (
                int(self._capture_area[0, 0])
                if self._capture_area[0, 0] < self._capture_area[1, 0]
                else int(self._capture_area[1, 0])
            )
            self._capture_coord["width"] = int(
                abs(self._capture_area[1, 0] - self._capture_area[0, 0])
            )
            self._capture_coord["height"] = int(
                abs(self._capture_area[1, 1] - self._capture_area[0, 1])
            )
            # Stop capturing area
            self._selecting_capture = False
            # Validate width and height
            if (
                self._capture_coord["width"] < App.CAPTURE_SIZE_LIMIT_X
                or self._capture_coord["height"] < App.CAPTURE_SIZE_LIMIT_Y
            ):
                return
            # Clear screen shot
            self._screen_capture = None
            # Set mode to tracking
            self._state = App.States.STATE_TRACKING
            return

    def _mouse_callback(self, event, x, y, flags, param):
        """ Handles trajectory drawing """
        if self._state == App.States.STATE_CAPTURE_AREA:
            self._mouse_callback_select(event, x, y, flags, param)
            return

        if event == cv2.EVENT_MOUSEMOVE and self._drawing:
            self._trajectory.append((x, y, 0))
            return

        elif event == cv2.EVENT_LBUTTONDOWN:
            self._trajectory.clear()
            self._trajectory_state = App.TrajectoryStates.STATE_DRAWING
            self._drawing = True
            return

        elif event == cv2.EVENT_LBUTTONUP:
            # Connect the last point with the first one
            if len(self._trajectory) > 0:
                self._trajectory.append(self._trajectory[0])

            # Send the trajectory
            if self.comm.send_trajectory(self._trajectory):
                self._trajectory_state = App.TrajectoryStates.STATE_TRANSMISSION_PASS
            else:
                self._trajectory_state = App.TrajectoryStates.STATE_TRANSMISSION_FAIL

            self._drawing = False
            return

        elif event == cv2.EVENT_RBUTTONUP and not self._drawing:
            self._trajectory.clear()
            self._trajectory_state = App.TrajectoryStates.STATE_DRAWING
            return

    def run(self):
        """ Run the app state machine """
        with mss() as capture:
            while True:
                if self._state == App.States.STATE_HANDSHAKE:
                    self._state_handshake()
                    continue

                elif self._state == App.States.STATE_CAPTURE_AREA:
                    self._state_capture_area(capture)
                    continue

                elif self._state == App.States.STATE_TRACKING:
                    self._state_tracking(capture)
                    continue

                elif self._state == App.States.STATE_QUIT:
                    self._state_quit()
                    break

    def _state_handshake(self):
        """
        Establish a handshake with the controller

        The state waits for a handshake. If the handshake packet isn't received
        or it's content isn't valid, the application will quit.
        """
        screen = np.zeros([500, 500])
        # Draw instruction
        App._draw_instruction(screen, "Connecting to the controller...")
        # Draw image
        cv2.namedWindow(self._name)
        cv2.imshow(self._name, screen)
        cv2.waitKey(1)

        # Attempt to notify the controller about the established connection
        if self.comm.send_start():
            self._state = App.States.STATE_CAPTURE_AREA

            cv2.destroyWindow(self._name)
            cv2.waitKey(500)
        else:
            self._state = App.States.STATE_QUIT

            screen = np.zeros([500, 500])
            App._draw_instruction(screen, "Failed to connect...")
            cv2.imshow(self._name, screen)
            cv2.waitKey(1)

    def _state_capture_area(self, capture):
        """
        Select the capture are for tracking

        :param capture:     Reference to the screen capture instance
        """
        if self._screen_capture is None:
            # Grab the screen shot, when first time entering the state
            self._screen_capture = np.asarray(capture.grab(capture.monitors[1]))
            # OpenCV window initialization
            cv2.namedWindow(self._name)
            cv2.setMouseCallback(self._name, self._mouse_callback)

        # Copy the screen shot, to prevent over-drawing
        screen = self._screen_capture.copy()
        # Draw the area selection rectangle
        if self._selecting_capture:
            p1, p2 = tuple(self._capture_area[0, :]), tuple(self._capture_area[1, :])
            cv2.rectangle(screen, p1, p2, App.COLOR_DRAW, thickness=1)

        # Draw instruction
        App._draw_instruction(screen, "Select the capture area")
        # Draw image
        cv2.imshow(self._name, screen)

        if cv2.waitKey(1) & 0xFF == ord(App.KEY_QUIT):
            self._state = App.States.STATE_QUIT

    def _state_tracking(self, capture):
        """
        Track the ball and send the coordinates

        :param capture:     Reference to the screen capture instance
        """
        # Capture the selected area
        screen = np.asarray(capture.grab(self._capture_coord))
        image = cv2.cvtColor(screen, cv2.COLOR_BGR2GRAY)

        # Locate the ball
        coordinates = self.tracker.find(image)
        if coordinates is not None:
            # Send ball coordinates to the robot controller
            for c in coordinates[0, :, 3:]:
                self.comm.send_ball_position(c)

            # Mark detected ball
            for i in coordinates[0, :, :3]:
                # Convert pixel coordinates as floats to integers
                i = np.uint16(np.around(i))
                x, y, r = i
                cv2.circle(screen, (x, y), r, App.COLOR_MARK, thickness=1)

        # Draw trajectory
        for i, coord in enumerate(self._trajectory[1:]):
            p1 = self._trajectory[i][:2]
            p2 = coord[:2]
            # Select color
            if self._trajectory_state == App.TrajectoryStates.STATE_TRANSMISSION_PASS:
                color = App.COLOR_PASS
            elif self._trajectory_state == App.TrajectoryStates.STATE_TRANSMISSION_FAIL:
                color = App.COLOR_FAIL
            else:
                color = App.COLOR_DRAW
            # Draw trajectory
            cv2.line(screen, p1, p2, color, thickness=1)

        # Draw instruction
        App._draw_instruction(
            screen, "Press the left button to start drawing the trajectory"
        )
        App._draw_instruction(
            screen, "Press the right button to clear the trajectory", position=(50, 75)
        )
        App._draw_instruction(
            screen, "Press R key to reselect the capture area", position=(50, 100)
        )
        App._draw_instruction(
            screen, "Press Q key to quit the program", position=(50, 125)
        )

        # Draw image
        cv2.imshow(self._name, screen)

        # OpenCV mainloop
        key = cv2.waitKey(1) & 0xFF

        # Reselect capture area
        if key == ord(App.KEY_CAPTURE_AREA):
            self._state = App.States.STATE_CAPTURE_AREA
            return

        # Quit
        elif key == ord(App.KEY_QUIT):
            self._state = App.States.STATE_QUIT

    def _state_quit(self):
        """ Cleanup and close the program """
        # Notify controller about the dropped connection
        self.comm.send_stop()
        self.comm.disconnect()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    app = App(WIN_NAME, SERVER_IP, PORT_SEND, PORT_RECEIVE)
    app.run()
