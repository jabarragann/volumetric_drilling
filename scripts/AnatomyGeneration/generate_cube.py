import cv2
import numpy as np
import argparse
from pathlib import Path

if __name__ == "__main__":

    # fmt: off
    parser = argparse.ArgumentParser(description="Description of your program")
    parser.add_argument("-s", "--resolution", help="Image resolution", default=40)
    parser.add_argument("-c", "--cuberes", help="Cube resolution", default=32)
    parser.add_argument("-f", "--dirname", help="directory name", default="cube40_32")
    parser.add_argument("-r", "--root", help="Location where you want to save the images",
                        default="resources/volumes/")
    # fmt: on
    args = parser.parse_args()

    # define path
    root: Path = Path(args.root) / args.dirname
    root = root.resolve()

    if not root.exists():
        root.mkdir(parents=True)

    ans = input(f"storing images in: {root} (y/n) ")
    if ans == "n":
        exit(0)
    else:
        img_res = args.resolution
        cube_res = args.cuberes
        init_p = int((img_res - cube_res) / 2)
        counter = 0
        with open((root / args.dirname).with_suffix(".txt"), "w") as f:

            for i in range(args.resolution):
                if i < init_p or i > cube_res + init_p:
                    img = np.zeros((args.resolution, args.resolution, 4), dtype=np.uint8)
                else:
                    img = np.zeros((args.resolution, args.resolution, 4), dtype=np.uint8)
                    # img[:, :, -1] = 25
                    img = cv2.rectangle(
                        img, (init_p, init_p), (init_p + cube_res, init_p + cube_res), (255, 255, 255, 255), -1
                    )
                img_name = f"plane00{counter}.png"
                f.write(img_name + "\n")
                cv2.imwrite(str(root / img_name), img)
                counter += 1

                # test = cv2.imread(str(root / img_name), cv2.IMREAD_UNCHANGED)
                # print(test[100, 100])
                # break
