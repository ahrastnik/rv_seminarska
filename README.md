# Trajectory ball control on a platform using robot vision
*Project was created as part of a larger seminar at two of our courses, Robot vision and Robot control.
 Courses are part of the Robotics masters program, at Faculty of electrical engineering - Ljubjana 2019/20*

## Description
Project presents the user interface and simulated robot vision for a ball balancing demonstration.
The demonstration is built using three separate, 3 DOF haptic robots, who control a single round platform,
in order to balance a ball.
The main goal here is to determine the ball position and set a trajectory, on which the ball should move.
All data must than be passed to the robot controller via a network protocol.

Initially the project intended to utilize a real camera feed and calculate ball coordinates from a real life robot system.
Unfortunately due to the COVID-19 pandemic, we were forced to move everything in a simulation.
Because of this reason, the program instead screen captures the virtual simulation and operates on the simulation feed,
instead of one from a real camera.

## Installation instructions (Windows)
- Install Python: https://www.python.org/downloads/release/python-382/
- Install Git: https://git-scm.com/
- Clone the repository in a directory of your choice: *git clone git@github.com:ahrastnik/rv_seminarska.git*
- Install the python virtual environment manager: *pip install virtualenv virtualenvwrapper-win*
- Setup the project virtual environment:
    - Create the project virtual environment: *mkvirtualenv bojan*
    - Make sure you are located in the root project directory
    - Set the virtual environment project directory: *setprojectdir .*
    - Install all project-required modules: *pip install -r requirements.txt*

## Usage instructions
1. Firstly, the robot controller must be setup and running as a server
on port 6969 (from which the data is received)
and a client on port 9696 (to which the data is sent).
2. Run the application
3. If the connection with the controller was established,
a window containing a full screen screenshot will appear.
4. Select the capture area by LEFT clicking and dragging.
5. After the capture area was selected the application is running
and tracking the ball, if one is found.
6. To set a trajectory on which you wish the ball to move,
draw a trajectory by pressing and holding the LEFT mouse button,
until you desired shape is formed.
7. To clear the trajectory, press the RIGHT mouse button.
8. To reselect the capture area, press the 'R' key.
9. To quit the application at any time, press the 'Q' key
