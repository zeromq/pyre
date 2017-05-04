__all__ = ['pyre', 'zbeacon', 'zhelper']

with open('VERSION') as version_file:
    __version__ = version_file.read().strip()

from .pyre import Pyre
from .pyre_event import PyreEvent
