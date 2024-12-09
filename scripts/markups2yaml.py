import csv
import yaml
from collections import OrderedDict
import click
from pathlib import Path

def check_csvformat(input_csv):

    with open(input_csv, "r") as csv_file:
        reader = csv.reader(csv_file)
        first_row = iter(reader).__next__()
        assert len(first_row) == 4, f"Expected 4 columns [name, x, y, z] but got only {len(first_row)}." 

def create_yaml_from_csv(input_csv, output_yaml):
    bodies = ["BODY volume_anatomical_origin"]
    fiducial_locations = OrderedDict()
    body_entries = []

    check_csvformat(input_csv)
    with open(input_csv, "r") as csv_file:
        reader = csv.reader(csv_file)

        for row in reader:
            name, x, y, z = row[0], float(row[1]), float(row[2]), float(row[3])
            bodies.append(f"BODY {name}")
            body_entries.append(
                {
                    f"BODY {name}": {
                        "name": name,
                        "mass": 0.001,
                        "location": {
                            "position": {"x": x, "y": y, "z": z},
                            "orientation": {"r": 0.0, "p": 0.0, "y": 0.0},
                        },
                    }
                }
            )
    fiducial_locations = dict(fiducial_locations)

    # Prepare the YAML structure
    yaml_structure = OrderedDict()
    yaml_structure["bodies"] = bodies

    for body_entry in body_entries:
        yaml_structure.update(body_entry)

    yaml_structure = dict(yaml_structure)

    # Write the YAML file
    with open(output_yaml, "w") as yaml_file:
        yaml.dump(
            yaml_structure,
            yaml_file,
            sort_keys=False,
            default_flow_style=False,
            allow_unicode=True,
        )

@click.command()
@click.option('--input', type=click.Path(exists=True), help="Input csv file")
@click.option('--output', type=click.Path(), help="Output file. If out not defined path will be the same as input.")
def main(input: str, output: str):
    """ Helper script to generate yaml file from csv file with fiducial locations for the registration plugin.
    """
    # # Example usage
    # input = "/home/juan95/research/discovery_grant/user_studies/resources/ADF/20241015_PhantomADF/Scan3"
    # input = Path(input) / "markup.csv"
    # out_path = Path(input) / "markup.yaml"

    input = Path(input) 
    if output is None:
        output = input.parent / "volume_with_fiducials.yaml"

    create_yaml_from_csv(input, output)


if __name__ == "__main__":
    main()
