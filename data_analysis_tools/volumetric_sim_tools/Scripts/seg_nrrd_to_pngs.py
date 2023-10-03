from argparse import ArgumentParser
from pathlib import Path
from volumetric_sim_tools.DataUtils.NrrdConverter import NrrdConverter


def main():
    parser = ArgumentParser()
    parser.add_argument("-n", action="store", dest="nrrd_file", help="Specify Nrrd File")
    parser.add_argument(
        "-p", action="store", dest="image_prefix", help="Specify Image Prefix", default="plane"
    )
    parser.add_argument("--dst_p", help="Directory to save all images (Required)", required=True)
    parser.add_argument(
        "--rx",
        action="store",
        dest="x_skip",
        help="X axis order [1-100]. Higher value indicates greater reduction",
        default=1,
    )
    parser.add_argument(
        "--ry",
        action="store",
        dest="y_skip",
        help="Y axis order [1-100]. Higher value indicates greater reduction",
        default=1,
    )
    parser.add_argument(
        "--rz",
        action="store",
        dest="z_skip",
        help="Z axis order [1-100]. Higher value indicates greater reduction",
        default=1,
    )
    parsed_args = parser.parse_args()
    print("Specified Arguments")
    print(parsed_args)

    dst_path = Path(parsed_args.dst_p)
    if not dst_path.exists():
        print(f"Destination path ({dst_path}) does not exists")
        dst_path.mkdir()

    nrrd_converter = NrrdConverter(
        int(parsed_args.x_skip), int(parsed_args.y_skip), int(parsed_args.z_skip)
    )
    nrrd_converter.read_nrrd(parsed_args.nrrd_file)
    nrrd_converter.initialize_image_matrix()
    nrrd_converter.initialize_segments_infos()
    nrrd_converter.print_segments_infos()

    nrrd_converter.copy_volume_to_image_matrix()
    # nrrd_converter.normalize_image_matrix_data()
    nrrd_converter.scale_image_matrix_data(255)
    nrrd_converter.save_image_matrix_as_images(dst_path, parsed_args.image_prefix)


if __name__ == "__main__":
    main()
