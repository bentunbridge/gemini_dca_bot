import os
from typing import List


def make_new_dir(path: str,
                 unmask: bool = False):
    if not os.path.exists(path):
        if unmask:
            os.umask(0)
        os.makedirs(path)


def list2num(mylist: List[str]) -> List[str]:
    result = []
    for item in mylist:
        try:
            if item.lower().startswith("0x"):
                result.append(int(item, 16))
            else:
                result.append(int(item))
        except ValueError:
            pass
    return result
