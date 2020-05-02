import numpy as np
import cv2
from mss import mss

from communicator import PhantomCommunicator
from tracker import BallTracker


WIN_NAME = "RV seminarska"
SERVER_IP = "127.0.0.1"
SERVER_PORT = 6969


class App:
    CAPTURE_COORDINATES = {"top": 400, "left": 400, "width": 400, "height": 400}
    PIXEL_RATIO = 0.694
    X_OFFSET = 296
    Y_OFFSET = 278

    def __init__(self, name, server_ip, server_port):
        self._name = name
        self._server_ip = server_ip
        self._server_port = server_port

        self._trajectory = []
        self._drawing = False

        cv2.namedWindow(self._name)
        cv2.setMouseCallback(self._name, self._mouse_callback)

        self.comm = PhantomCommunicator(ip=server_ip, port=server_port, auto_start=True)
        self.tracker = BallTracker(App.PIXEL_RATIO, App.X_OFFSET, App.Y_OFFSET)

    def _mouse_callback(self, event, x, y, flags, param):
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
            while True:
                img = capture.grab(monitor=App.CAPTURE_COORDINATES)
                img_np = np.asarray(img)
                image = cv2.cvtColor(img_np, cv2.COLOR_BGR2GRAY)

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
                        cv2.circle(img_np, (x, y), r, (0, 255, 0), thickness=1)

                # Draw trajectory
                for i, coord in enumerate(self._trajectory[1:]):
                    p1 = self._trajectory[i][:2]
                    p2 = coord[:2]
                    cv2.line(img_np, p1, p2, (0, 0, 255), thickness=1)

                # Draw image
                cv2.imshow(self._name, img_np)

                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break

            cv2.destroyAllWindows()


if __name__ == "__main__":
    app = App(WIN_NAME, SERVER_IP, SERVER_PORT)
    app.run()
