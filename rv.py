import numpy as np
import cv2
from mss import mss

from communicator import PhantomCommunicator
from tracker import BallTracker


WIN_NAME = "RV seminarska"
CAPTURE_COORDINATES = {"top": 400, "left": 400, "width": 400, "height": 400}

SERVER_IP = "127.0.0.1"
SERVER_PORT = 6969

PIXEL_RATIO = 0.694
X_OFFSET = 296
Y_OFFSET = 278


def main():
    comm = PhantomCommunicator(ip=SERVER_IP, port=SERVER_PORT, auto_start=True)
    tracker = BallTracker(PIXEL_RATIO, X_OFFSET, Y_OFFSET)

    with mss() as capture:
        while True:
            img = capture.grab(monitor=CAPTURE_COORDINATES)
            img_np = np.asarray(img)
            image = cv2.cvtColor(img_np, cv2.COLOR_BGR2GRAY)

            coordinates = tracker.find(image)
            if coordinates is not None:
                # Send ball coordinates to Simulink
                for c in coordinates[0, :, 3:]:
                    comm.send(c)

                # Mark detected ball
                for i in coordinates[0, :, :3]:
                    # Convert pixel coordinates as floats to integers
                    i = np.uint16(np.around(i))
                    x, y, r = i
                    cv2.circle(img_np, (x, y), r, (0, 255, 0), 2)

            # Draw image
            cv2.imshow(WIN_NAME, img_np)

            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
