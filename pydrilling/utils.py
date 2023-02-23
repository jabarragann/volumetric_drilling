from collections import defaultdict
import json
import os
from enum import Enum
from pathlib import Path

from natsort import natsorted

def init_ambf(node_name="default"):
    from ambf_client import Client

    # Generate all objects in scene, even ones that may not be needed
    _client = Client(node_name)
    _client.connect()
    objects_dict = {}

    # TODO: maybe this can be an argument?
    ignore_list = ["World", "light"]  # remove world and light as we don't need them

    # Create python instances of AMBF objects
    obj_names = _client.get_obj_names()
    for obj_name in obj_names:
        obj_name = os.path.basename(os.path.normpath(obj_name))  # Get the last part of file path
        for ignore in ignore_list:
            if ignore in obj_name:
                break
        else:
            objects_dict[obj_name] = _client.get_obj_handle(obj_name)

    return _client, objects_dict


class ColorPrinting(Enum):
    HEADER = "\033[95m"
    OKBLUE = "\033[94m"
    OKCYAN = "\033[96m"
    OKGREEN = "\033[92m"
    WARNING = "\033[93m"
    FAIL = "\033[91m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"

    @classmethod
    def toStr(cls,f):
        return "{:.3f}".format(f)

    @classmethod
    def WARN_STR(cls,val):
        if type(val) != str:
            val = cls.toStr(val)
        valStr = cls.WARNING.value + val + cls.ENDC.value
        return valStr

    @classmethod
    def WARN2_STR(cls, val):
        if type(val) != str:
            val = cls.toStr(val)
        valStr = cls.OKCYAN.value + val + cls.ENDC.value
        return valStr

    @classmethod
    def ok_str(cls, val):
        if type(val) != str:
            val = cls.toStr(val)
        valStr = cls.OKGREEN.value + val + cls.ENDC.value
        return valStr

    @classmethod
    def info_str(cls,val):
        if type(val) != str:
            val = cls.toStr(val)
        valStr = cls.OKBLUE.value + val + cls.ENDC.value
        return valStr

    @classmethod
    def fail_str(cls,val):
        if type(val) != str:
            val = cls.toStr(val)
        valStr = cls.FAIL.value + val + cls.ENDC.value
        return valStr

class SimulatorDataParser:
    @classmethod
    def is_valid_recording_dir(cls, path:Path)->bool:
        """A valid recording dir contains at least one .hdf5 file and a meta.json file."""
        data_files = list(path.glob("*.hdf5") )
        if len(data_files)==0:
            return False 
        if not (path/"meta.json").exists(): 
            return False
        else:
            return True

    @classmethod
    def are_subdirs_valid(cls, path:Path)->bool:
        """ Check that all subfolders are valid recording directories.  """

        rec_dirs = list(path.glob("*"))
        if len(rec_dirs) == 0:
            print(ColorPrinting.fail_str(f"No subdirectories in {path}"))
            return False

        for f in rec_dirs: 
            if not cls.is_valid_recording_dir(f):
                print(ColorPrinting.fail_str(f"Subdirectory {f} is not a valid recording"))
                print("A valid recording dir contains at least one .hdf5 file and a meta.json file.")
                return False 

        return True
    
    @classmethod
    def get_participants_recordings(cls, path: Path)->dict:
        """Generate a dictionary of recording path to process.  Each entry in
        the dictionary is sorted using natsort

        Parameters
        ----------
        path : Path
            Path containing recordings of multiple users 
        """

        participant_dict = defaultdict(list)

        subdir_list = [p for p in path.glob("*") if p.is_dir()]
        for subdir in subdir_list:
            participant_id = subdir.name

            if cls.are_subdirs_valid(subdir): 
                for file in subdir.glob("*"):
                    participant_dict[participant_id].append(file)
            else:
                exit(0)

        participant_dict = cls.sort_recordings(participant_dict)            
        return dict(participant_dict)

    @classmethod
    def sort_recordings(cls, participant_dict:dict)->dict:
        """sort all valid recordings"""
        for k, v in participant_dict.items():
            participant_dict[k] = natsorted(v)
        
        return participant_dict

    @classmethod
    def load_meta_data(cls, trial_idx:int, rec_path:Path)->dict:

        with open(rec_path/"meta.json","r") as f:
            metadata = json.load(f)

        anatomy  = metadata['anatomy'] 
        guidance_type = metadata['guidance_modality'] 
        participant_id = metadata['participant_id']

        trial_meta_data = {
            "participant_id": participant_id,
            "guidance_modality": guidance_type,
            "anatomy": anatomy,
            "trial_idx": trial_idx,
        }
        return trial_meta_data

if __name__ =="__main__":
    print(ColorPrinting.ok_str("hello\n"))