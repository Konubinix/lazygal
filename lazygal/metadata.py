# Lazygal, a lazy satic web gallery generator.
# Copyright (C) 2007 Alexandre Rossi <alexandre.rossi@gmail.com>
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

import os, sys, datetime
import pyexiv2, Image


MATEW_TAGS = {
    'album_name': 'Album name',
    'album_description': 'Album description',
    'album_picture': 'Album image identifier',
}
MATEW_METADATA = 'album_description'


class ExifTags(pyexiv2.Image):

    def __init__(self, image_path):
        pyexiv2.Image.__init__(self,
                               image_path.encode(sys.getfilesystemencoding()))
        self.readMetadata()

        self.image_path = image_path

    def get_exif_date(self, name):
        '''
        Parses date from EXIF information.
        '''
        exif_date = str(self[name])
        date, time = exif_date.split(' ')
        year, month, day = date.split('-')
        hour, minute, second = time.split(':')
        return datetime.datetime(int(year), int(month), int(day),
                           int(hour), int(minute), int(second))

    def get_date(self):
        '''
        Get real time when photo has been taken. We prefer EXIF fields
        as those were filled by camera, Image DateTime can be update by
        software when editing photos later.
        '''
        try:
            return self.get_exif_date('Exif.Photo.DateTimeDigitized')
        except (IndexError, ValueError):
            try:
                return self.get_exif_date('Exif.Photo.DateTimeOriginal')
            except (IndexError, ValueError):
                try:
                    return self.get_exif_date('Exif.Image.DateTime')
                except (IndexError, ValueError):
                    # No date available in EXIF
                    return None

    def get_required_rotation(self):
        try:
            orientation_code = int(self['Exif.Image.Orientation'])
            if orientation_code == 8:
                return 90
            elif orientation_code == 6:
                return 270
            else:
                return 0
        except IndexError:
            return 0

    def get_camera_name(self):
        '''
        Gets vendor and model name from EXIF and tries to construct
        camera name out of this. This is a bit fuzzy, because diferent
        vendors put different information to both tags.
        '''
        try:
            model = str(self['Exif.Image.Model'])
            try:
                vendor = str(self['Exif.Image.Make'])
                vendor_l = vendor.lower()
                model_l = model.lower()
                # Split vendor to words and check whether they are
                # already in model, for example:
                # Canon/Canon A40
                # PENTAX Corporation/PENTAX K10D
                # Eastman Kodak Company/KODAK DIGITAL SCIENCE DC260 (V01.00)
                for word in vendor_l.split(' '):
                    if model_l.find(word) != -1:
                        return model
                return '%s %s' % (vendor, model)
            except KeyError:
                return model
        except IndexError:
            return ''

    def get_exif_string(self, name):
        '''
        Reads string from EXIF information, returns empty string if key
        is not found.
        '''
        try:
            return str(self[name])
        except (IndexError, ValueError):
            return ''

    def get_exif_float(self, name):
        '''
        Reads float number from EXIF information (where it is stored as
        fraction). Returns empty string if key is not found.
        '''
        try:
            val = self[name]
            return str(round(float(val[0]) / float(val[1]), 1))
        except IndexError:
            return ''

    def get_jpeg_comment(self):
        '''
        Reads JPEG comment field, returns empty string if key is not
        found.
        '''
        im = Image.open(self.image_path)
        try:
            return im.app['COM']
        except KeyError:
            return ''

    def get_comment(self):
        try:
            ret = self.get_exif_string('Exif.Photo.UserComment')
            if ret == '':
                raise ValueError
            else:
                return ret
        except (ValueError, KeyError):
            return self.get_jpeg_comment()

    def get_flash(self):
        return self.get_exif_string('Exif.Photo.Flash')

    def get_exposure(self):
        try:
            exposure = self['Exif.Photo.ExposureTime']
            # FIXME : Not sure about this at all
            return "%d/%d" % (exposure[0], exposure[1])
        except (ValueError, KeyError):
            return ''

    def get_iso(self):
        # FIXME : Find how this is called in pyexiv2
        return self.get_exif_string('EXIF ISOSpeedRatings')

    def get_fnumber(self):
        val = self.get_exif_float('Exif.Photo.FNumber')
        if val == '':
            return ''
        return 'f/%s' % val

    def get_focal_length(self):
        flen = self.get_exif_float('Exif.Photo.FocalLength')
        if flen == '':
            return ''

        try:
            # FIXME : Find how this is called in pyexiv2
            iwidth = float(str(self['EXIF ExifImageWidth']))
            fresunit = str(self['Exif.Photo.FocalPlaneResolutionUnit'])
            factors = {'1': 25.4, '2': 25.4, '3': 10, '4': 1, '5': 0.001}
            try:
                fresfactor = factors[fresunit]
            except IndexError:
                fresfactor = 0

            fxrestxt = str(self['Exif.Photo.FocalPlaneXResolution'])
            if "/" in fxrestxt:
                fxres = float(eval(fxrestxt))
            else:
                fxres = float(fxrestxt)
            try:
                ccdwidth = float(iwidth * fresfactor / fxres)
            except ZeroDivisionError:
                return ''

            val = str(self['Exif.Photo.FocalLength']).split('/')
            if len(val) == 1: val.append('1')
            foclength = float(val[0]) / float(val[1])
            flen += ' (35 mm equivalent: %d mm)' % int(foclength / ccdwidth * 36 + 0.5)
        except IndexError:
            return flen

        return flen


class NoMetadata(Exception):
    '''
    Exception indicating that no meta data has been found.
    '''
    pass


class DirectoryMetadata:

    def __init__(self, dir):
        self.dir = dir
        self.directory_path = self.dir.source

        description = os.path.join(self.directory_path, MATEW_METADATA)
        if os.path.isfile(description):
            self.description_file = description
        else:
            self.description_file = None

    def get_mtime(self):
        if self.description_file:
            return os.path.getmtime(self.description_file)
        else:
            return 0

    def get_matew_metadata(self, metadata, subdir = None):
        '''
        Return dictionary with meta data parsed from Matew like format.
        '''
        if subdir is None:
            path = self.description_file
        else:
            path = os.path.join(self.directory_path, subdir, MATEW_METADATA)

        if path is None or not os.path.exists(path):
            raise NoMetadata('Could not open metadata file (%s)' % path)

        f = file(path, 'r')
        for line in f:
            for tag in MATEW_TAGS.keys():
                tag_text = MATEW_TAGS[tag]
                tag_len = len(tag_text)
                if line[:tag_len] == tag_text:
                    data = line[tag_len:]
                    data = data.strip()
                    if data[0] == '"':
                        # Strip quotes
                        data = data[1:-1]
                    if tag == 'album_picture':
                        if subdir is not None:
                            data = os.path.join(subdir, data)
                    metadata[tag] = data.decode(sys.stdin.encoding)
                    break

        return metadata

    def get(self, subdir = None):
        '''
        Returns directory meta data. First tries to parse known formats
        and then fall backs to built in defaults.
        '''

        result = {}

        try:
            result = self.get_matew_metadata(result, subdir)
        except NoMetadata:
            pass

        # Add album picture
        if not result.has_key('album_picture'):
            picture = self.dir.guess_directory_picture(subdir)
            if picture is not None:
                result['album_picture'] = picture

        if result.has_key('album_picture'):
            # Convert to thumbnail path
            result['album_picture'] =  result['album_picture'].replace('.', '_thumb.')

        return result


# vim: ts=4 sw=4 expandtab