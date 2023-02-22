import os
from enum import Enum

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

if __name__ =="__main__":
    print(ColorPrinting.ok_str("hello\n"))