# Lazygal, a lazy static web gallery generator.
# Copyright (C) 2010-2012 Alexandre Rossi <alexandre.rossi@gmail.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.


import os
import shutil
import tempfile
import unittest

from lazygal.sourcetree import Directory
from lazygal.generators import Album


SAMPLES_DIR = os.path.dirname(__file__)
SAMPLE_IMG = os.path.join(SAMPLES_DIR, 'sample.jpg')


# Init i18n
import gettext
LOCALES_PATH = os.path.normpath(os.path.join(os.path.dirname(__file__),
                                             'build', 'mo'))
gettext.install('lazygal', LOCALES_PATH, unicode=1)


# Init quiet logging
import logging
logging.basicConfig(format='%(message)s', level=logging.ERROR)


def has_symlinks():
    try:
        os.symlink
    except AttributeError:
        return False
    else:
        return True


class qnd_skipIf(object):
    """
    Quick and dirty unittest.skipIf decorator implementation to be able to run
    the test suite using python < 2.7 .
    """

    def __init__(self, cond, reason):
        self.cond = cond
        self.reason = reason

    def __call__(self, f):
        def nf(*args, **kwargs):
            if self.cond:
                print 'skipped: %s' % self.reason
                return
            f(*args, **kwargs)
        return nf


try:
    # Python >= 2.7
    skip = unittest.skipIf
except AttributeError:
    # Python < 2.7
    skip = qnd_skipIf


class LazygalTest(unittest.TestCase):

    def setUp(self):
        self.__workdirs = []

    def get_working_path(self):
        new_wd = tempfile.mkdtemp()
        self.__workdirs.append(new_wd)
        return unicode(new_wd)

    def get_sample_path(self, sample):
        return os.path.join(SAMPLES_DIR, sample)

    def add_img(self, dest_dir, name):
        img_path = os.path.join(dest_dir, name)
        shutil.copy(SAMPLE_IMG, img_path)
        return img_path

    def tearDown(self):
        for wd in self.__workdirs:
            shutil.rmtree(wd)


class LazygalTestGen(LazygalTest):

    def setUp(self, album=True):
        super(LazygalTestGen, self).setUp()

        self.tmpdir = self.get_working_path()
        self.source_dir = os.path.join(self.tmpdir, 'src')
        os.mkdir(self.source_dir)

        if album:
            self.setup_album()

    def setup_album(self, config=None):
        self.album = Album(self.source_dir, config)

    def setup_subgal(self, name, pic_names):
        subgal_path = os.path.join(self.source_dir, name)
        if not os.path.isdir(subgal_path):
            os.mkdir(subgal_path)
        for pic_name in pic_names:
            self.add_img(subgal_path, pic_name)

        return Directory(subgal_path, [], pic_names, self.album)


# Workaround for __import__ behavior, see
# http://docs.python.org/lib/built-in-funcs.html
def my_import(name):
    mod = __import__(name)
    components = name.split('.')
    for comp in components[1:]:
        mod = getattr(mod, comp)
    return mod


def run():
    import glob
    suitelist = []
    for fn in glob.glob(os.path.join(os.path.dirname(__file__),
                                     "test_*.py")):
        module_path = '.'.join(['lazygaltest', os.path.basename(fn[:-3])])
        m = my_import(module_path)
        suitelist.append(unittest.defaultTestLoader.loadTestsFromModule(m))
    runner = unittest.TextTestRunner(verbosity=2)
    runner.run(unittest.TestSuite(suitelist))


# vim: ts=4 sw=4 expandtab
