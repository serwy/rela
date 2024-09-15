## Copyright (c) 2024 Roger D. Serwy. All rights reserved.
## See LICENSE.txt for more information.

'''
Make relative imports work by messing with the python import system.

Motivation: Running a script inside a parent package that does relative imports
from an IDE rather than using `python -m`.

This is a fun hack.

2024-08-19

'''
from ._utils import _get_globals

import warnings
import sys
import importlib.abc
import importlib.machinery
import importlib.util
import os
import pathlib


class AbsolutePathWarning(Warning):
    pass

class IfMainExecuting(Warning):
    pass

class IfMainInterrupt(BaseException):
    pass

class RelaModuleNotFound(Warning):
    pass


class RelaModuleFinder(importlib.abc.MetaPathFinder):

    def __init__(self, mod_name, mod_path):
        self.mod_name = mod_name
        self.mod_path = pathlib.Path(mod_path)
        self.skip = False
        self.found = False

    def __enter__(self):
        sys.meta_path.insert(0, self)

    def __exit__(self, *args):
        # we're done, we're not needed anymore
        sys.meta_path.remove(self)
        if not self.found:
            if self.mod_name not in sys.modules:
                msg = 'RelaModuleFinder did not provide %r from %r' % (
                    self.mod_name, self.mod_path)
                warnings.warn(RelaModuleNotFound(msg), 'once')

    def find_spec(self, fullname, path, target=None):

        if self.skip:
            return None

        spec = None
        if fullname == self.mod_name:

            init_py = self.mod_path / '__init__.py'
            if init_py.is_file():
                spec = importlib.util.spec_from_file_location(
                    self.mod_name,
                    str(init_py),
                )

            elif self.mod_path.is_dir():
                # we need to hack sys.path. I can't find the right
                # incantations to make importlib give the correct Namespace package
                # with type(module.__path__) == _NamespacePath

                # Since we are only importing the toplevel namespace package,
                # there is no risk of cascaded imports causing a namespace
                # collision because there is no __init__.py

                p = str(self.mod_path.parent)
                sys.path.insert(0, p)
                self.skip = True  # so we don't recurse
                spec = importlib.util.find_spec(self.mod_name)
                sys.path.remove(p)

            if spec:
                self.found = True
                return spec

        return None


def tive(to):
    """ to - package name or relative dots """
    g = _get_globals()
    return _tive(to, g)

def _tive(s, g):
    ''' s - periods or name of module,
        g - globals dict
    '''
    mod = None
    if g['__name__'] != '__main__':
        return

    fake = os.path.join(os.getcwd(), '__rela__')
    file = g.get('__file__', fake)

    path = pathlib.Path(file)

    periods = s.count('.')

    if periods == 0 and s:
        # try by name instead
        try:
            idx = path.parts.index(s)
        except ValueError:
            idx = None

        if idx is None:
            fullpath = str(path)
            msg = f'"{s}" not found in path "{fullpath}"'
            raise FileNotFoundError(msg)

        # compute the effective number of periods
        periods = len(path.parts[idx:]) - 1

    names = path.parts[-(1+periods):-1]
    name = '.'.join(names)

    parent_dir = path.parts[:-(1+periods)]
    pdir = os.path.sep.join(parent_dir)

    target = os.path.sep.join(path.parts[:-periods])

    with RelaModuleFinder(names[0], target) as mf:
        mod = importlib.import_module(name)

    # WARN if we already imported the current script before executing it.
    me = '.'.join(path.parts[-(1+periods):-1] + (path.stem, ))
    if me.endswith('.__init__'):
        me = me.replace('.__init__', '')

    if me in sys.modules:
        msg = (f"The script at '{file}' already exists as sys.modules['{me}']. " +
               "Running this script again in sys.modules['__main__'] may result in " +
               "unpredictable behavior."
               )
        warnings.warn(RuntimeWarning(msg), 'always', stacklevel=3)

    p = g.get('__package__', None)
    if p is None:
        g['__package__'] = mod.__name__

    spec = g.get('__spec__', None)
    if spec is None:
        my_name = name + '.' + path.stem
        g['__spec__'] =  importlib.util.spec_from_loader(my_name, g['__loader__'])

    return mod



def path(directory, top=True):
    '''structured sys.path hacking, returns the path added'''
    g = _get_globals(d=2)
    return _path(directory, g, top)

def _path(p, g, top):

    orig_p = p

    if '__file__' in g:
        p = os.path.expanduser(p)
        file = pathlib.Path(g['__file__'])

        path = pathlib.Path(file).parent / p

        if not orig_p.startswith('.'):
            relpath = os.path.relpath(path, file.parent)
            s = '%r -> %r' % (orig_p, relpath)
            warnings.warn(AbsolutePathWarning(s), 'always', stacklevel=3)

    else:
        # allow .path to work from the shell
        path = pathlib.Path(p)

    path = path.absolute()
    p2 = str(path)
    # ensure that p exists in the path

    p2 = os.path.abspath(p2)
    while p2 in sys.path:
        sys.path.remove(p2)

    if top:
        sys.path.insert(0, p2)
    else:
        sys.path.append(p2)

    class ContextString(str):
        def __enter__(self):
            return self
        def __exit__(self, *args):
            s = str(self)
            while s in sys.path:
                sys.path.remove(s)

    return ContextString(p2)


def if_main_run(run_this_module):
    ''' if __name__ == '__main__', run this module instead '''
    g = _get_globals()
    if g['__name__'] != '__main__':
        return

    mod = run_this_module
    mod = mod.strip()

    file = pathlib.Path(g['__file__'])
    package = g['__package__']
    mod_name = package + '.' + file.stem

    parts = mod_name.split('.')

    while mod.startswith('.'):
        parts = parts[:-1]
        mod = mod[1:]

    new_mod = '.'.join(parts) + '.' + mod

    msg = f'"{new_mod}" from "{mod_name}"'
    warnings.warn(
        IfMainExecuting(f'executing instead: {msg}'),
        'always',
        stacklevel=2
    )

    # execute the module instead and then stop executing the current
    # script by raising an exception
    import runpy
    result = runpy.run_module(new_mod, run_name='__main__')
    raise IfMainInterrupt(f'stopping execution: {msg}')
