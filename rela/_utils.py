## Copyright (c) 2024 Roger D. Serwy. All rights reserved.
## See LICENSE.txt for more information.

import sys

def _get_globals(d=2):
    f  = sys._getframe()
    for _ in range(d):
        f = f.f_back
    g = f.f_globals
    return g
