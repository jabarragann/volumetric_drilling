# Commands to generate edt structures

All the commands in this section should be execute from the project root directory.

Create a txt file with the name of all the images.
```
python3 scripts/EdtGeneration/create_list_of_images.py --root ./resources/volumes/ear3_171
```

Create a single EDT structure

```
./../EDT/cmake-build/bin/EDTFromGrid --in ./resources/volumes/ear3_171/ear3_171.txt --id 110 184 209 --out ./edt_grids/ear3_171_red.edt
```

Create EDT arrays for all the anatomical structures

```
python3 scripts/EdtGeneration/create_all_edt.py
```