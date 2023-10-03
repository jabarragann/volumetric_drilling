from argparse import ArgumentParser
from volumetric_sim_tools.DataUtils.Recording import Recording
from volumetric_sim_tools.DataUtils.VideoUtils import generate_video_from_recording
from pathlib import Path
import click


@click.command()
@click.option(
    "--path",
    type=click.Path(exists=True, dir_okay=True, file_okay=False, path_type=Path),
    required=True,
    help="Directory containing the hdf5 files of a single experiment.",
)
def generate_video(path: Path):
    """Extract the images from the hdf5 files and generate a video from experiment."""
    path = path.resolve()
    try:
        print(f"processing {path}")
        root = Path(path)
        recording = Recording(root, participant_id="None", anatomy="None", guidance_modality="None")
        generate_video_from_recording(recording)
    except Exception as e:
        print(f"error with {path}")
        print(e)


def main():
    generate_video()


if __name__ == "__main__":
    main()
