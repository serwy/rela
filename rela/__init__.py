## Copyright (c) 2024 Roger D. Serwy. All rights reserved.
## See LICENSE.txt for more information.

'''
Using relative imports from the __main__ script

Copyright (c) 2024 Roger D. Serwy. All rights reserved.
See LICENSE.txt for more information.

'''

from ._rela import (tive, path, if_main_run, AbsolutePathWarning)
from . import _test as test

__all__ = ['tive', 'path', 'if_main_run', 'test']
