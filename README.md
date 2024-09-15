# rela.tive imports in Python from `__main__`

Allow relative imports to work when running a script.

    import rela; rela.tive('.')

No more dealing with `ImportError: attempted relative import with no known parent package` tracebacks.

## How and Why?

It detects if `__name__ == "__main__"` and runs the code
as if it were run using `python -m`.

This can make iterative code development and testing faster
when developing in a single file inside a package.

You don't need to install the package to use the package
when inside its development directory.

## API Overview

`rela.tive(to)`
- Allows relative imports in script running from `__name__ == '__main__'`
- __Parameters:__ `to` - a string of the package name or the number of dots to the top-level package.
- __Returns:__ the package's top-level module

`rela.path(directory, top=True)`
- Ensures `directory` is found only once in `sys.path`, at the top or bottom of the list. Always runs.
- __Parameters:__ `directory` - a string with a relative or absolute path to add to `sys.path`.
- __Returns:__ the absolute path added to `sys.path`
    - can be used as a context manager that removes the path when done.

`rela.if_main_run(module)`
- A hack to run other code instead of the current `__main__` script.
- __Motivation__: because you don't want to switch editor windows or your IDE can't configure its "run code" command.
- __Description:__ runs `module` if executing from `__name__ == '__main__'`
- __Parameters:__ `module` - a string with the relative module to run, e.g. `'.__main__'`
- __Raises:__ `IfMainInterrupt` exception when done, to stop execution of the rest of the script

## unittest API helpers

`@rela.test.case()`
- A decorator to filter tests from a `unittest.TestCase` class, used with `rela.test.keep`
- Does not filter unless `@rela.test.keep()` is applied to at least one test method.
- __Motivation:__ Makes focusing on a particular test a lot easier
- __Parameters:__ None

`@rela.test.keep()`
- A decorator applied to a particular test method, so that `test.case` keeps that test on the class.
- Can be applied to multiple test methods.
- __Parameters:__ None

`@rela.test.run(...)`
- A decorator to run a `unittest.TestCase` class if running from `__main__`.
- __Parameters:__ accepts TestRunner parameters
- __Raises:__ `RelaTestRunDone`


## Examples

If your code is laid out like this:

    project/
    ├── src
    │   └── thing
    │       ├── __init__.py
    │       ├── __main__.py
    │       ├── other.py
    │       └── xyz.py
    └── test
        └── test_thing.py


In `__main__.py`:

    import rela; rela.tive('.')

Now you can run `python __main__.py` rather than `python -m thing`.


In `test_thing.py`:

    import rela; rela.path('../src')
    import thing.xyz   # now this imports


In `other.py`:

    import rela; rela.tive('thing')  # '.' would work too
    from . import xyz


Running `python other.py` now works rather than giving an ImportError.


# Requirements

Minimum Python Version: 3.6, because of f-strings.
