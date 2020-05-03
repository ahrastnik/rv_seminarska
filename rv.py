import numpy as np
import cv2
from mss import mss

from communicator import PhantomCommunicator
from tracker import BallTracker


WIN_NAME = "RV seminarska"
SERVER_IP = "127.0.0.1"
SERVER_PORT = 6969


class App:
    PIXEL_RATIO = 0.694
    X_OFFSET = 296
    Y_OFFSET = 278

    def __init__(self, name, server_ip, server_port):
        self._name = name
        self._server_ip = server_ip
        self._server_port = server_port

        self._initializing = True
        self._selecting_capture = False
        self._capture_area = np.zeros([2, 2], dtype=np.int16)
        self._capture_coord = {"top": 400, "left": 400, "width": 400, "height": 400}
        self._trajectory = []
        self._drawing = False

        cv2.namedWindow(self._name)
        cv2.setMouseCallback(self._name, self._mouse_callback)

        self.comm = PhantomCommunicator(ip=server_ip, port=server_port, auto_start=True)
        self.tracker = BallTracker(App.PIXEL_RATIO, App.X_OFFSET, App.Y_OFFSET)

    def _mouse_callback_init(self, event, x, y, flags, param):
        if event == cv2.EVENT_MOUSEMOVE and self._selecting_capture:
            self._capture_area[1, :] = (x, y)
            # print(self._capture_area)
            return

        if event == cv2.EVENT_LBUTTONDOWN:
            self._capture_area[0, :] = (x, y)
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
            self._initializing = False
            return

    def _mouse_callback(self, event, x, y, flags, param):
        if self._initializing:
            self._mouse_callback_init(event, x, y, flags, param)
            return

        if event == cv2.EVENT_MOUSEMOVE and self._drawing:
            self._trajectory.append((x, y, 0))
            return

        elif event == cv2.EVENT_LBUTTONDOWN:
            self._trajectory.clear()
            self._drawing = True
            return

        elif event == cv2.EVENT_LBUTTONUP:
            # Connect the last point with the first one
            if len(self._trajectory) > 0:
                self._trajectory.append(self._trajectory[0])

            # Send the trajectory
            self.comm.send_trajectory(self._trajectory)

            self._drawing = False
            return

    def run(self):
        with mss() as capture:
            # screenshot = np.asarray(capture.grab(capture.monitors[1]))

            while True:
                # Select capture area
                if self._initializing:
                    if not self._select_capture_area(capture):
                        break
                    continue

                # Capture the selected area
                screen = np.asarray(capture.grab(self._capture_coord))
                image = cv2.cvtColor(screen, cv2.COLOR_BGR2GRAY)

                # Locate the ball
                coordinates = self.tracker.find(image)
                if coordinates is not None:
                    # Send ball coordinates to Simulink
                    for c in coordinates[0, :, 3:]:
                        self.comm.send_ball_position(c)

                    # Mark detected ball
                    for i in coordinates[0, :, :3]:
                        # Convert pixel coordinates as floats to integers
                        i = np.uint16(np.around(i))
                        x, y, r = i
                        cv2.circle(screen, (x, y), r, (0, 255, 0), thickness=1)

                # Draw trajectory
                for i, coord in enumerate(self._trajectory[1:]):
                    p1 = self._trajectory[i][:2]
                    p2 = coord[:2]
                    cv2.line(screen, p1, p2, (0, 0, 255), thickness=1)

                # Draw image
                cv2.imshow(self._name, screen)

                # OpenCV mainloop
                key = cv2.waitKey(1) & 0xFF

                if key == ord("r"):
                    # Reselect capture area
                    self._initializing = True
                    continue

                elif key == ord("q"):
                    # Quit
                    break

            cv2.destroyAllWindows()

    def _select_capture_area(self, capture):
        screen = np.asarray(capture.grab(capture.monitors[1]))
        # screen = screenshot.copy()
        # Draw the area selection rectangle
        if self._selecting_capture:
            p1, p2 = tuple(self._capture_area[0, :]), tuple(self._capture_area[1, :])
            cv2.rectangle(screen, p1, p2, (0, 0, 255), thickness=1)

        # Draw image
        cv2.imshow(self._name, screen)

        if cv2.waitKey(1) & 0xFF == ord("q"):
            return False

        return True


if __name__ == "__main__":
    app = App(WIN_NAME, SERVER_IP, SERVER_PORT)
    app.run()
