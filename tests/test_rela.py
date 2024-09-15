## Copyright (c) 2024 Roger D. Serwy. All rights reserved.
## See LICENSE.txt for more information.

'''
Tests for the `rela` project.


'''
import unittest
import subprocess
import pathlib
import sys
import types
import os
import importlib
import tempfile


try:
    import rela
    raise ImportError
except ImportError:
    # might as well try to make it work ;-)
    me = pathlib.Path(__file__).absolute().parent
    if (me.parent / 'rela').exists():
        sys.path.insert(0, str(me.parent))
        import rela
        sys.path.remove(str(me.parent))
    else:
        raise  # pragma: no cover


class SysMod:
    # Context Manager to restore `sys.modules` to state before
    # in order to undo imports performed during testing. Also sys.path
    def __enter__(self):
        self.mods = sys.modules.copy()
        self.pre_path = sys.path[:]
        return self

    def __exit__(self, *args):
        try:
            self._restore_mods()
        except:  # pragma: no cover
            import traceback
            traceback.print_exc()

    def _restore_mods(self):
        to_delete = []
        for k, v in list(sys.modules.items()):
            if k not in self.mods:
                to_delete.append(k)
            else:
                if v is not self.mods[k]:
                    print('mutated mod?', k, v)  # pragma: no cover

        to_delete.sort(reverse=True)
        removed = {}
        for name in to_delete:
            removed[name] = sys.modules.pop(name)
        self.removed = removed

        self.post_path = sys.path[:]

        sys.path.clear()
        sys.path.extend(self.pre_path)


class FileItem:
    ''' A quick way to configure the filesystem with a mock package '''
    def __init__(self, basepath):
        self.basepath = pathlib.Path(basepath)
        self.basepath.mkdir(parents=True, exist_ok=True)

    def __getitem__(self, key):
        return (self.basepath / key).read_text()

    def __delitem__(self, key):
        (self.basepath / key).unlink()

    def __setitem__(self, key, value):
        file = (self.basepath / key)
        file.parent.mkdir(parents=True, exist_ok=True)
        return file.write_text(value)

    def path(self, key):
        return self.basepath / key

    def update(self, *E, **F):
        d = dict(*E, **F)
        for k, v in d.items():
            self[k] = v


@rela.test.case()
class TestRela(unittest.TestCase):

    def setUp(self):
        self.mod = types.ModuleType('__main__')
        self.g = vars(self.mod)
        self.td = tempfile.TemporaryDirectory(prefix='test-rela-')
        self.fs = FileItem(self.td.name)

    def tearDown(self):
        self.td.cleanup()

    def do(self, file, src, *, package=None):
        # run code in a module
        self.g['__file__'] = file
        if package:
            self.g['__package__'] = package

        with SysMod() as m:
            exec(src, self.g)
        return m

    def test_test_utils(self):
        self.fs.update({
            'x': '123'
        })
        self.assertEqual(self.fs['x'], '123')

        path = self.fs.path('x')
        self.assertTrue(path.exists())

        del self.fs['x']
        self.assertFalse(path.exists())

    def test_one_period(self):
        self.fs.update({
            'package/__init__.py': '',
            'package/xyz.py': 'value=123'
        })

        file = self.fs.path('package/aaa.py')

        self.do(str(file), '''if 1:
            import rela; rela.tive('.')
            from . import xyz
        ''')

        self.assertEqual(self.g['xyz'].value, 123)

    def test_two_period(self):
        self.fs.update({
            'package/__init__.py': '',
            'package/xyz.py': 'value=123',
            'package/thing/.exist': '',
        })

        file = self.fs.path('package/thing/aaa.py')

        self.do(str(file), '''if 1:
            import rela; rela.tive('..')
            from .. import xyz
        ''')

        self.assertEqual(self.g['xyz'].value, 123)
        self.assertEqual(self.g['xyz'].__name__, 'package.xyz')


    def test_tive_by_name(self):
        self.fs.update({
            'package/__init__.py': '',
            'package/xyz.py': 'value=123'
        })

        file = self.fs.path('package/aaa.py')

        self.do(str(file), '''if 1:
            import rela; rela.tive('package')
            from . import xyz
        ''')

        self.assertEqual(self.g['xyz'].value, 123)
        self.assertEqual(self.g['xyz'].__name__, 'package.xyz')

    def test_not_found(self):
        file = self.fs.path('aaa.py')
        with self.assertRaises(FileNotFoundError):
            self.do(
                str(file),
                '''import rela; rela.tive('package_not_found')''')


    def test_namespace_package(self):
        self.fs.update({
            'ns_package/a/b/c/d.py': 'value=111'
        })

        file = self.fs.path('ns_package/a/b/c/test.py')

        mods = self.do(str(file), '''if 1:
            import rela; rela.tive('ns_package')
            from . import d
        ''')
        r = set(['ns_package', 'ns_package.a', 'ns_package.a.b',
                 'ns_package.a.b.c', 'ns_package.a.b.c.d'])

        self.assertEqual(r, set(mods.removed))
        self.assertEqual(self.g['d'].value, 111)


    def test_tive_skip_not_main(self):
        self.fs.update({
            'pack/a.py': 'value=111'
        })

        file = self.fs.path('pack/b.py')
        self.g['__name__'] = 'pack.b'  # not __main__

        with self.assertRaises(ImportError):
            mods = self.do(str(file), '''if 1:
                import rela; rela.tive('.')
                from . import a
            ''', package='pack')


    def test_path(self):
        self.fs.update({
            'pack/a.py': 'value=111'
        })
        file = self.fs.path('pack/b.py')

        mods = self.do(str(file), '''if 1:
            import rela; rela.path('../')
            from pack import a
        ''')
        self.assertEqual(self.g['a'].value, 111)

        parent = str(self.fs.path(''))
        self.assertFalse(parent in mods.pre_path)
        self.assertTrue(parent in mods.post_path)

        # test other aspects of `path`
        file = self.fs.path('pack/c.py')
        mods = self.do(str(file), '''if 1:
            import sys
            import rela
            p = rela.path('../')
            assert sys.path.count(p) == 1, "has one path instance"
            assert sys.path[0] == p, "path is at the top"

            sys.path.append(p)
            sys.path.append(p)
            assert sys.path.count(p) == 3, "has three path instance"

            p = rela.path('../', top=False)
            assert sys.path.count(p) == 1, "has one path instance"
            assert sys.path[-1] == p, "path is at the bottom"

        ''')


    def test_path_context(self):
        self.fs.update({
            'pack/a.py': 'value=111'
        })
        file = self.fs.path('pack/b.py')

        mods = self.do(str(file), '''if 1:
            import rela
            import sys
            with rela.path('../') as p:
                from pack import a
                assert p in sys.path

            assert p not in sys.path
        ''')
        self.assertEqual(self.g['a'].value, 111)

        parent = str(self.fs.path(''))
        self.assertFalse(parent in mods.pre_path)
        self.assertFalse(parent in mods.post_path)


    def test_path_not_main(self):
        self.fs.update({
            'pack/__init__.py': '',
            'pack/a.py': 'value=111'
        })
        file = self.fs.path('pack/b.py')
        self.g['__name__'] = 'pack.b'  # not __main__
        self.g['__package__'] = 'pack'

        with SysMod() as m:

            spec = importlib.util.spec_from_file_location(
                'pack', str(self.fs.path('pack/__init__.py'))
            )
            mod = importlib.util.module_from_spec(spec)
            sys.modules['pack'] = mod
            orig_path = sys.path[:]

            mods = self.do(str(file), '''if 1:
                import rela; rela.path('../')
                from . import a
            ''')

            # no sys.path modifications since we are not on main
            self.assertEqual(orig_path, sys.path)
            self.assertEqual(self.g['a'].value, 111)

    def test_absolute_path(self):
        self.fs.update({
            'pack/a.py': 'value=111'
        })
        file = self.fs.path('pack/b.py')

        abspath = str(self.fs.path(''))

        with self.assertWarns(rela.AbsolutePathWarning):
            mods = self.do(str(file), f'''if 1:
            import rela; rela.path(r'{abspath}')
            from pack import a
            ''')
            self.assertEqual(self.g['a'].value, 111)

    def test_main(self):
        self.fs.update({
            'test_pack/a.py': 'value=111'
        })
        file = self.fs.path('test_pack/b.py')

        with self.assertRaises(rela._rela.IfMainInterrupt):
            with self.assertWarns(rela._rela.IfMainExecuting):
                mods = self.do(str(file), f'''if 1:
                    import rela; rela.tive('.')
                    rela.if_main_run('.a')
                ''')

    def test_rela_module_finder(self):
        file = self.fs.path(self.fs.path(''))
        orig_meta = sys.meta_path[:]

        mf = rela._rela.RelaModuleFinder('notfound', str(file))

        with self.assertWarns(rela._rela.RelaModuleNotFound):
            with mf:
                self.assertTrue(mf in sys.meta_path)

        # make sure RelaModuleFinder removed itself
        self.assertEqual(sys.meta_path, orig_meta)

    def test_main_not_main(self):
        self.fs.update({
            'test_pack/a.py': 'value=111'
        })
        file = self.fs.path('test_pack/b.py')

        mods = self.do(str(file), f'''if 1:
            __name__ = 'test_pack.b'
            import rela; rela.tive('.')
            result = rela.if_main_run('.a')
        ''')

        self.assertEqual(self.g['result'], None)

    def test_bad_init(self):
        # we make __init__.py a directory instead of a file
        self.fs.update({
            'bad_pack/__init__.py/broken': 'broken',
            'bad_pack/a.py': 'value=111'
        })
        file = self.fs.path('bad_pack/b.py')

        mods = self.do(str(file), f'''if 1:
            import rela; rela.path('../')
            import bad_pack
            if hasattr(bad_pack, '__file__'):  # python3.6
                assert bad_pack.__file__ is None
        ''')

    def test_python_shell(self):
        self.fs.update({
            'shell/__init__.py': '',
            'shell/a.py': 'value=111'
        })
        file = self.fs.path('shell/b.py')

        cwd = os.getcwd()
        try:
            os.chdir(file.parent)
            mods = self.do(str(file), f'''if 1:
                del __file__   # python shell does not have __file__
                import rela; rela.tive('.')
                from . import a
            ''')
            self.assertEqual(self.g['a'].__name__, 'shell.a')
        finally:
            os.chdir(cwd)


        try:
            pwd = str(file.parent.parent)
            os.chdir(file.parent)
            mods = self.do(str(file), f'''if 1:
                del __file__   # python shell does not have __file__
                import rela; rela.path(r"{pwd}")  # r'' because Windows \\ in paths
                from . import a
            ''')
            self.assertEqual(self.g['a'].__name__, 'shell.a')
        finally:
            os.chdir(cwd)


    def test_already_imported(self):
        self.fs.update({
            'imported/__init__.py': 'from . import b',
            'imported/b.py': ''
        })

        file = self.fs.path('imported/b.py')

        with self.assertWarns(RuntimeWarning):
            mods = self.do(str(file), f'''if 1:
            import rela; rela.tive('.')
            ''')

    def test_already_imported_init(self):
        self.fs.update({
            'imported/__init__.py': '',
        })
        file = self.fs.path('imported/__init__.py')
        with self.assertWarns(RuntimeWarning):
            mods = self.do(str(file), f'''if 1:
            import rela; rela.tive('.')
            ''')

    def test_case_keep(self):
        tested = []

        with self.assertWarns(rela._test.TestCaseFilter):
            @rela.test.case()
            class TestThing(unittest.TestCase):

                @rela.test.keep()
                def test_one(self):
                    pass  # pragma: no cover

                def test_two(self):
                    pass  # pragma: no cover

        self.assertIn('test_one', dir(TestThing))
        self.assertNotIn('test_two', dir(TestThing))

    def test_run_cases(self):

        file = self.fs.path('case/a.py')

        src = f'''if 1:

            class Null:
                def write(self, *args): pass
                def flush(self): pass

            import unittest
            import rela
            tested = []

            @rela.test.case()
            class Test(unittest.TestCase):
                @rela.test.keep()
                def test_thing(self):
                    tested.append('test_thing')
        '''

        with self.assertWarns(rela._test.TestCaseFilter):
            self.do(str(file), src)

        with self.assertRaises(rela._test.RelaTestRunDone):
            with self.assertWarns(rela._test.RelaTestRunning):
                self.do(str(file), src + '\n' + f'''if 1:
                rela.test.run(stream=Null())(Test)
            ''')

        # test when not running in __main__
        with self.assertWarns(rela._test.TestCaseFilter):
            self.do(str(file), src + '\n' + f'''if 1:
                __name__ = 'case.a'
                rela.test.run(stream=Null())(Test)
            ''')
        self.assertEqual(self.g['tested'], [])



if __name__ == '__main__':
    unittest.main(verbosity=2)
