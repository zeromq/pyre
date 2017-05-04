__all__ = ['pyre', 'zbeacon', 'zhelper']

from os import path
version_file_path = path.join(path.split(__file__)[0], 'VERSION')

with open(version_file_path) as version_file:
    __version__ = version_file.read().strip()

from .pyre import Pyre
from .pyre_event import PyreEvent
