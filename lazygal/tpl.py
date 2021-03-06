# Lazygal, a lazy static web gallery generator.
# Copyright (C) 2007-2012 Alexandre Rossi <alexandre.rossi@gmail.com>
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
import glob
from genshi.core import START
from genshi.template import TemplateLoader, MarkupTemplate, NewTextTemplate
from genshi.template import TemplateNotFound
from genshi.template.eval import UndefinedError
from genshi.input import XMLParser
import __init__

import timeutils


DEFAULT_THEME = 'default'
USER_THEME_DIR = os.path.expanduser(os.path.join('~', '.lazygal', 'themes'))
THEME_SHARED_FILE_PREFIX = 'SHARED_'


class LazygalTemplate(object):

    def __init__(self, loader, genshi_tpl):
        self.loader = loader
        self.path = genshi_tpl.filepath
        self.genshi_tpl = genshi_tpl

    def __complement_values(self, values):
        values['gen_datetime'] = timeutils.Datetime()
        values['gen_date'] = values['gen_datetime'].strftime('%c')
        values['lazygal_version'] = __init__.__version__
        return values

    def __generate(self, values):
        # The cryptic values['_'] = _ is the way to pass the gettext
        # translation function to the templates : the _() callable is assigned
        # to the '_' keyword arg.
        values['_'] = _
        return self.genshi_tpl.generate(**values)

    def instanciate(self, values):
        self.__complement_values(values)
        # encoding=None gives us a unicode string instead of an utf-8 encoded
        # string. This is because we are not out of lazygal yet.
        return self.__generate(values).render(self.serialization_method,
                                              encoding=None)

    def dump(self, values, dest):
        self.__complement_values(values)

        if os.path.exists(dest):
            os.unlink(dest)
        page = open(dest, 'w')
        try:
            self.__generate(values).render(method=self.serialization_method,
                                           out=page, encoding='utf-8')
        except UnicodeDecodeError:
            problematic_vars = []
            for key, value in values.items():
                if type(value) is not unicode:
                    try:
                        str(value).decode('utf-8')
                    except UnicodeDecodeError:
                        problematic_vars.append(key)
            print 'Problematic template vars : %s' % ', '.join(problematic_vars)
            raise
        except UndefinedError, e:
            print 'W: %s' % e
            raise
        finally:
            page.close()


class XmlTemplate(LazygalTemplate):

    serialization_method = 'xhtml'
    genshi_tpl_class = MarkupTemplate

    def subtemplates(self, tpl=None):
        if tpl is None:
            tpl = self

        subtemplates = []
        f = open(tpl.path, 'r')
        try:
            for kind, data, pos in XMLParser(f, filename=tpl.path):
                if kind is START:
                    tag, attrib = data
                    if tag.namespace == 'http://www.w3.org/2001/XInclude'\
                            and tag.localname == 'include':
                        subtpl_ident = attrib.get('href')
                        try:
                            subtpl = self.loader.load(subtpl_ident)
                        except TemplateNotFound:
                            # This will fail later, here we just need to ignore
                            # template idents that are dynamically computed.
                            pass
                        else:
                            subtemplates.append(subtpl)
        finally:
            f.close()

        for subtemplate in subtemplates:
            for new_subtpl in self.subtemplates(subtemplate):
                if new_subtpl not in subtemplates:
                    subtemplates.append(new_subtpl)

        return subtemplates


class PlainTemplate(LazygalTemplate):

    serialization_method = 'text'
    genshi_tpl_class = NewTextTemplate


class TplFactory(object):

    known_exts = {
        '.thtml': XmlTemplate,
        '.tcss' : PlainTemplate,
        '.tjs'  : PlainTemplate,
    }

    def __init__(self, default_tpl_dir, tpl_dir):
        # We use lenient mode here because we want an easy way to check whether
        # a template variable is defined, or the empty string, thus defined()
        # will only work for the 'whether it is defined' part of the test.
        self.loader = TemplateLoader([tpl_dir, default_tpl_dir],
                                     variable_lookup='lenient')

    def is_known_template_type(self, file):
        filename, ext = os.path.splitext(os.path.basename(file))
        return ext in self.known_exts.keys()

    def load(self, tpl_ident):
        if self.is_known_template_type(tpl_ident):
            filename, ext = os.path.splitext(os.path.basename(tpl_ident))
            tpl_class = self.known_exts[ext]
            tpl = self.loader.load(tpl_ident, cls=tpl_class.genshi_tpl_class)
            return tpl_class(self, tpl)
        else:
            raise ValueError(_('Unknown template type for %s' % tpl_ident))


class Theme(object):

    def __init__(self, themes_dir, name):
        self.name = name

        # First try user directory
        self.tpl_dir = os.path.join(USER_THEME_DIR, self.name)
        if not os.path.exists(self.tpl_dir):
            # Fallback to system themes
            self.tpl_dir = os.path.join(themes_dir, self.name)
            if not os.path.exists(self.tpl_dir):
                raise ValueError(_('Theme %s not found') % self.name)

        self.tpl_loader = TplFactory(os.path.join(themes_dir, DEFAULT_THEME),
                                     self.tpl_dir)

        # Load styles templates
        for style in self.get_avail_styles():
            style_filename = style['filename']
            try:
                self.tpl_loader.load(style_filename)
            except ValueError:
                # Not a known emplate ext, ignore
                pass

        # find out theme kind
        try:
            self.tpl_loader.load('dynindex.thtml')
        except TemplateNotFound:
            self.kind = 'static'
        else:
            self.kind = 'dynamic'

    def get_avail_styles(self, default_style=None):
        style_files_mask = os.path.join(self.tpl_dir,
                                        THEME_SHARED_FILE_PREFIX + '*' + 'css')
        styles = []
        for style_tpl_file in glob.glob(style_files_mask):
            style = {}
            tpl_filename = os.path.basename(style_tpl_file).split('.')[0]
            style['filename'] = tpl_filename[len(THEME_SHARED_FILE_PREFIX):]
            style['name'] = style['filename'].replace('_', ' ')
            if default_style is not None:
                if style['filename'] == default_style:
                    style['rel'] = 'stylesheet'
                else:
                    style['rel'] = 'alternate stylesheet'
            styles.append(style)
        return styles


# vim: ts=4 sw=4 expandtab
