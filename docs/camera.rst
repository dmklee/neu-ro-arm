:github_url: https://github.com/dmklee/nuro-arm

Using Camera
============

To use the camera, you need to install `openCV <https://opencv.org/>`_. We
require the contrib version, which provides support for ArUco tags.  To include
opencv-contrib-python in the installation, you can use the following command:

.. code-block:: bash

    pip install nuro-arm[all]

Capturing Images
----------------

.. code-block:: python
    
    from nuro_arm import Camera

    cam = Camera()

    img = cam.get_image()

Calibration
-----------

If you want to associate features in the image with positions in the real world,
then the camera must be calibrated.


Using ArUco Tags
----------------

ArUco Tags are visual markers that look like QR codes.  Due to their unique
appearance, they can be easily located in an image using a computer vision
algorithm.  By placing them on an object, we can determine the object's
3D position, which can be used for a robotics task.

To generate a PDF of ArUco Tags, use the `generate_aruco_tags` script.  Here is
an example that creates four aruco tags (ids 0 to 3) with a size of 40 millimeters.

.. code-block:: bash

    generate_aruco_tags --size=40 --number=4

To locate ArUco Tags in an image:

.. code-block:: python

    from nuro_arm.camera.camera_utils import find_arucotags

    tag_size = 0.040 # size in meters
    tags = find_arucotags(img, tag_size)
