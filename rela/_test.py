## Copyright (c) 2024 Roger D. Serwy. All rights reserved.
## See LICENSE.txt for more information.

'''
Helpers for using `unittest`.

'''
import unittest
import inspect
import warnings

from ._utils import _get_globals


class RelaTestRunning(Warning):
    pass


class RelaTestRunDone(BaseException):
    pass


class TestCaseFilter(Warning):
    pass

_linesep = '=' * 70



def run(**kw):
    """ decorator for unittest.TestCase to run the test suite
        if running from `__name__ == '__main__'`.

        Raises `RelaTestRunDone` exception.
    """
    g = _get_globals()
    if g['__name__'] != '__main__':
        # allow unittest discover to operate, so we
        # return a pass-thru decorator
        return lambda cls: cls

    kw.setdefault('verbosity', 2)
    ''' decorator for unittest.TestCase to run'''
    def decorator(cls):
        assert unittest.TestCase in cls.__mro__
        # run the tests

        try:
            lineno = inspect.getsourcelines(cls)[1]
        except (OSError, TypeError):
            lineno = '(not found)'

        msg = f'on line {lineno}'

        msg_full = msg
        warnings.warn(
            RelaTestRunning(msg_full),
            'always',
            stacklevel=2
        )

        suite = unittest.TestLoader().loadTestsFromTestCase(cls)
        runner = unittest.runner.TextTestRunner(**kw)
        runner.run(suite)

        # We will raise an exception because this decorator
        # is a momentary convenience hack during development and
        # test error triage.
        raise RelaTestRunDone()

    return decorator



def keep():
    ''' decorator for a test method of a unittest.TestCase class.
        Requires the class be decorated with `rela.test.case`.
    '''
    def decorator(func):
        setattr(func, '_test_keep__', True)
        return func
    return decorator

def case():
    ''' decorator for unittest.TestCase to filter test methods,
        if any are decorated using `@rela.test.keep()`, otherwise all
        test methods are kept.
    '''

    # because test runners are hardly configuration friendly :-)

    def decorator(cls):
        assert unittest.TestCase in cls.__mro__

        try:
            lineno = inspect.getsourcelines(cls)
        except (OSError, TypeError):
            lineno = '(not found)'

        msg = f'on line {lineno}.'

        keep = []
        remove = []
        for name in dir(cls):
            if not name.startswith('test_'):
                continue
            obj = getattr(cls, name)
            if hasattr(obj, '_test_keep__'):
                line =  obj.__code__.co_firstlineno
                keep.append((line, f'line {line:4}:  {name}'))
            else:
                remove.append(name)

        if keep:
            # we have at least one kept item, we now filter

            keep.sort()
            keep_line = [m for line, m in keep]
            kept = '    \n'.join(keep_line)
            remove.sort()

            remove_count = len(remove)
            keep_count = len(keep)

            msg_full = [
                msg,
                _linesep,
                f'Removed {remove_count} tests from {cls}',
                f'Keeping {keep_count} tests:\n\n{kept}',
                _linesep,
            ]

            msg_full = '\n'.join(msg_full)

            warnings.warn(
                TestCaseFilter(msg_full),
                'always',
                stacklevel=2
            )

            for r in remove:
                delattr(cls, r)

        return cls

    return decorator
