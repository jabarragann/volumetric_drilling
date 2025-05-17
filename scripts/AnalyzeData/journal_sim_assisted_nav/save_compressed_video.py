
#!/usr/bin/env python

import rospy
from sensor_msgs.msg import CompressedImage
import cv2
import numpy as np

def callback(msg):
    # Convert compressed image to OpenCV format
    np_arr = np.frombuffer(msg.data, np.uint8)
    image = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

    if image is not None:
        # cv2.imshow("Compressed Video", image)
        # cv2.waitKey(1)
        cv2.imwrite("./left_raw.png", image)


def main():
    topic = "/decklink_left/camera/image_raw/compressed"
    rospy.init_node('compressed_video_display', anonymous=True)
    rospy.Subscriber(topic, CompressedImage, callback, queue_size=1, buff_size=2**24)
    rospy.loginfo(f"Subscribed to {topic}")
    
    try:
        rospy.spin()
    except KeyboardInterrupt:
        pass
    finally:
        cv2.destroyAllWindows()

if __name__ == '__main__':
    main()
