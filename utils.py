import os
import contextlib

@contextlib.contextmanager
def remember_cwd(new_dir=None):
    curdir = os.getcwd()
    try:
        if new_dir:
            os.chdir(new_dir)
        yield
    finally:
        os.chdir(curdir)

