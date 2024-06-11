#!/usr/bin/env python3

# smart-image-renamer
#
# Author: Ronak Gandhi (ronak.gandhi@ronakg.com)
# Project Home Page: https://github.com/ronakg/smart-image-renamer
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""Smart Image Renamer main module"""

import argparse
import datetime
import itertools
import os
import re
import sys
from enum import IntEnum

import inquirer
import pillow_heif
from PIL import Image
from PIL.ExifTags import TAGS
from pymediainfo import MediaInfo

from _version import __version__


class NotAnImageFile(Exception):
    """This file is not an Image"""
    pass


class NotAVideoFile(Exception):
    """This file is not a video"""
    pass


class InvalidExifData(Exception):
    """Could not find any EXIF or corrupted EXIF"""
    pass


class NoExifTimeStamp(Exception):
    """Could not find 'DateTimeOriginal' or 'DateTimeDigitized' EXIF timestamp"""
    pass


class InvalidExifTimeStamp(Exception):
    """Could not process EXIF Timestamp, which should be "YYYY:MM:DD HH:MM:SS" """
    pass


class BulkChoice(IntEnum):
    """Enum for bulk choices"""
    UNKNOWN = 0
    YES = 1
    NO = 2
    ALWAYS = 3
    NEVER = 4
    ABORT = 5


def get_bulk_choice(msg: str = 'Your choice?') -> BulkChoice:
    """Get bulk choice from user"""
    questions = [
        inquirer.List('bulk',
                      message=msg,
                      choices=['Yes', 'No', 'Always', 'Never', 'Abort'],
                      ),
    ]
    answers = inquirer.prompt(questions)
    if answers['bulk'] == 'Yes':
        return BulkChoice.YES
    elif answers['bulk'] == 'No':
        return BulkChoice.NO
    elif answers['bulk'] == 'Always':
        return BulkChoice.ALWAYS
    elif answers['bulk'] == 'Never':
        return BulkChoice.NEVER
    elif answers['bulk'] == 'Abort':
        return BulkChoice.ABORT
    else:
        return BulkChoice.UNKNOWN


def get_cmd_args():
    """Get, process and return command line arguments to the script
    """
    help_description = '''
Smart Image Renamer

Rename your photos in bulk using information stored in EXIF.
'''

    help_epilog = '''
Format string for the file name is defined by a mix of custom text and following tags enclosed in {}:
  YYYY        Year
  MM          Month
  DD          Day
  hh          Hours
  mm          Minutes
  ss          Seconds
  Seq         Sequence number
  Artist      Artist
  Make        Camera Make
  Model       Camera Model
  Height      Height of image in pixels
  Folder      Parent folder of the image file

Examples:
  Format String:          {YYYY}-{MM}-{DD}-{Folder}-{Seq}
  File Name:              2014-05-09-Wedding_Shoot-001.JPEG
                          2014-05-09-Wedding_Shoot-002.JPEG

  Format String:          {YYYY}{DD}{MM}_{Model}_Beach_Shoot_{Seq}
  File Name:              20140429_PENTAX K-x_Beach_Shoot_001.JPEG
                          20140429_PENTAX K-x_Beach_Shoot_002.JPEG
    '''

    parser = argparse.ArgumentParser(description=help_description,
                                     formatter_class=argparse.RawTextHelpFormatter,
                                     epilog=help_epilog)
    parser.add_argument('-f',
                        dest='format',
                        type=str,
                        default='{YYYY}-{MM}-{DD}_{hh}-{mm}-{ss}_{Height}',
                        help='Format of the new file name (default: {YYYY}-{MM}-{DD}_{hh}-{mm}-{ss}_{Height})')
    parser.add_argument('-s',
                        dest='sequence',
                        type=int,
                        default=1,
                        help='Starting sequence number (default: 1)')
    parser.add_argument('-r', dest='recursive', default=False,
                        action='store_true',
                        help='Recursive mode (default: False)')
    parser.add_argument('-i', dest='hidden', default=False,
                        action='store_true', help='Include hidden files (default: False)')
    parser.add_argument('-t', dest='test', default=False, action='store_true',
                        help='Test mode. Don\'t apply changes. (default: False)')
    parser.add_argument('-V', '--version', action='version',
                        version='%(prog)s {}'.format(__version__))
    group = parser.add_mutually_exclusive_group()
    group.add_argument("-v", "--verbose", action="store_true")
    group.add_argument("-q", "--quiet", action="store_true")
    parser.add_argument('input', nargs='+',
                        help='Absolute path to file or directory')

    return parser.parse_args()


def get_exif_data(img_file: str) -> dict:
    """Read EXIF data from the image.

    img_file: Absolute path to the image file

    Returns: A dictionary containing EXIF data of the file

    Raises: NotAnImageFile if file is not an image
            NoExifTimeStamp if EXIF does not contain timestamp
    """
    try:
        img = Image.open(img_file)
    except (OSError, IOError):
        raise NotAnImageFile

    try:
        # Use TAGS module to make EXIF data human readable
        exif_data = {
            TAGS[k]: v
            for k, v in img._getexif().items()
            if k in TAGS
        }
    except AttributeError:
        try:
            exif_data = {
                TAGS[k]: v
                for k, v in img.getexif().items()
                if k in TAGS
            }
        except AttributeError:
            print("WARNING: Could not read ExifData from " + img_file)
            raise NoExifTimeStamp
    # DEBUG: print(exif_data)

    # Add image format to EXIF
    exif_data['ext'] = img.format
    exif_data['Height'] = str(img.height) + 'px'

    # Find out the original timestamp or digitized timestamp from the EXIF
    img_timestamp = (exif_data.get('DateTimeDigitized') or
                     exif_data.get('DateTimeOriginal') or
                     exif_data.get('DateTime'))

    if not img_timestamp:
        raise NoExifTimeStamp

    # Extract year, month, day, hours, minutes, seconds from timestamp
    img_timestamp =\
        re.search(r'(?P<YYYY>\d\d\d?\d?):(?P<MM>\d\d?):(?P<DD>\d\d?) '
                  '(?P<hh>\d\d?):(?P<mm>\d\d?):(?P<ss>\d\d?)',
                  img_timestamp.strip())

    if not img_timestamp:
        raise NoExifTimeStamp

    try:
        exif_data.update(img_timestamp.groupdict())
    except Exception:
        print("Fatal Error: update of exif_data didn't work!")

    exif_data['YYYY'] = int(exif_data['YYYY'])
    exif_data['MM'] = int(exif_data['MM'])
    exif_data['DD'] = int(exif_data['DD'])
    exif_data['hh'] = int(exif_data['hh'])
    exif_data['mm'] = int(exif_data['mm'])
    exif_data['ss'] = int(exif_data['ss'])    

    return exif_data


def get_img_data(img_file: str) -> dict:
    """ Read image data without EXIF

    img_file: Absolute path to the image file

    Returns: A dictionary containing 'height' and the modification timestamp.

    Raises: NotAnImageFile if file is not an image
    """
    try:
        img = Image.open(img_file)
    except (OSError, IOError):
        raise NotAnImageFile

    img_data = dict()

    img_data['ext'] = img.format
    img_data['Height'] = str(img.height) + 'px'

    dt = datetime.datetime.fromtimestamp(os.path.getmtime(img_file))
    img_data['YYYY'] = dt.year
    img_data['MM'] = dt.month
    img_data['DD'] = dt.day
    img_data['hh'] = dt.hour
    img_data['mm'] = dt.minute
    img_data['ss'] = dt.second
    img_data['Artist'] = ''
    img_data['Make'] = ''
    img_data['Model'] = ''
    return img_data


def get_video_data(video_file: str) -> dict:
    """ Uses mediainfo library to read resolution of video

    Raises: NotAVideoFile if file is not a video
    """

    if not MediaInfo.can_parse():
        raise SystemError("libmediainfo library is missing. Please install!")

    try:
        vid = MediaInfo.parse(video_file)
    except:
        raise NotAVideoFile

    isvideo = False
    for track in vid.tracks:
        if track.track_type == 'Video':
            height = track.height
            isvideo = True
    if not isvideo:
        raise NotAVideoFile

    vid_data = dict()

    vid_data['ext'] = vid.tracks[0].file_extension
    vid_data['Height'] = str(height) + 'px'

    dt = datetime.datetime.fromtimestamp(os.path.getmtime(video_file))
    vid_data['YYYY'] = dt.year
    vid_data['MM'] = dt.month
    vid_data['DD'] = dt.day
    vid_data['hh'] = dt.hour
    vid_data['mm'] = dt.minute
    vid_data['ss'] = dt.second
    vid_data['Artist'] = ''
    vid_data['Make'] = ''
    vid_data['Model'] = ''

    return vid_data


def get_file_data(any_file: str) -> dict:
    """ Last fallback: use plain timestamp of file
    """

    vid_data = dict()

    vid_data['ext'] = any_file.split('.')[-1]
    vid_data['Height'] = '0px'

    dt = datetime.datetime.fromtimestamp(os.path.getmtime(any_file))
    vid_data['YYYY'] = dt.year
    vid_data['MM'] = dt.month
    vid_data['DD'] = dt.day
    vid_data['hh'] = dt.hour
    vid_data['mm'] = dt.minute
    vid_data['ss'] = dt.second
    vid_data['Artist'] = ''
    vid_data['Make'] = ''
    vid_data['Model'] = ''

    return vid_data


def find_new_name(old_filename: str) -> str:
    """ Adds sequence number and checks if file also exist. Tries until it finds a good number.

    Returns: new filename of file that does not exist
    """

    sep_idx = old_filename.rfind('.')
    base = old_filename[: sep_idx]
    ext = old_filename[sep_idx:]

    seq = 1
    new_name = base + '_' + str(seq) + ext
    while os.path.isfile(new_name):
        seq = seq + 1
        new_name = base + '_' + str(seq) + ext
    return new_name


def cli():
    pillow_heif.register_heif_opener()
    skipped_files = []
    args = get_cmd_args()

    input_paths = [os.path.abspath(input) for input in args.input]
    input_format = args.format
    verbose = args.verbose
    quiet = args.quiet
    sequence_start = args.sequence
    test_mode = args.test
    recursive = args.recursive
    include_hidden = args.hidden
    ignore_exifless = BulkChoice.UNKNOWN
    process_unreadable_videos = BulkChoice.UNKNOWN

    summary_files_processed = 0

    # Make sure the month, days, hours, minutes and seconds have 2 digits
    input_format = input_format.replace('{MM}', '{MM:02d}')
    input_format = input_format.replace('{DD}', '{DD:02d}')
    input_format = input_format.replace('{hh}', '{hh:02d}')
    input_format = input_format.replace('{mm}', '{mm:02d}')
    input_format = input_format.replace('{ss}', '{ss:02d}')
    print("Actual format string:", input_format)

    for input_path in input_paths:
        for root, dirs, files in os.walk(input_path):
            # Skip hidden directories unless specified by user
            if not include_hidden and os.path.basename(root).startswith('.'):
                continue

            # Initialize sequence counter
            # Use no of files to determine padding for sequence numbers
            seq = itertools.count(start=sequence_start)
            seq_width = len(str(len(files)))

            print(f'Processing folder: {root}')
            for f in sorted(files):
                # Skip hidden files unless specified by user
                if not include_hidden and f.startswith('.'):
                    continue

                old_file_name = os.path.join(root, f)
                try:
                    # Get EXIF data from the image
                    tag_data = get_exif_data(old_file_name)
                except NotAnImageFile:
                    try:
                        tag_data = get_video_data(old_file_name)
                    except NotAVideoFile:
                        if old_file_name.split('.')[-1] in ['mp4','mov', '3gp']:
                            print(f'WARNING: {old_file_name} is a video file, but I cannot open it!')
                            if process_unreadable_videos != BulkChoice.NEVER and process_unreadable_videos != BulkChoice.ALWAYS:
                                process_unreadable_videos = get_bulk_choice(f'Process file time stamp {old_file_name}?')
                            if process_unreadable_videos == BulkChoice.ABORT:
                                sys.exit(1)
                            elif process_unreadable_videos == BulkChoice.NEVER or process_unreadable_videos == BulkChoice.NO:
                                continue
                            elif process_unreadable_videos == BulkChoice.ALWAYS or process_unreadable_videos == BulkChoice.YES:
                                    tag_data = get_file_data(old_file_name)
                        elif verbose and not quiet:
                            print(f'INFO: {old_file_name} is neither an image nor a video file!')
                            continue
                except NoExifTimeStamp:
                    if not quiet:
                        print(f'INFO: {old_file_name} does not contain usable timestamp in EXIF!')
                    
                    # Decide how to proceed with image file, that has no usable EXIF timestamp
                    if ignore_exifless != BulkChoice.NEVER and ignore_exifless != BulkChoice.ALWAYS:
                        ignore_exifless = get_bulk_choice(f'Ignore file {old_file_name} without EXIF timestamp?')
                    
                    if ignore_exifless == BulkChoice.ABORT:
                        sys.exit(1)
                    elif ignore_exifless == BulkChoice.ALWAYS or ignore_exifless == BulkChoice.YES:
                        continue
                    elif ignore_exifless == BulkChoice.NEVER or ignore_exifless == BulkChoice.NO:
                        try:
                            tag_data = get_img_data(old_file_name)
                        except NotAnImageFile:
                            if verbose and not quiet:
                                print(f'INFO: {old_file_name} is neither an image nor a video file!')
                            continue

                # Generate data to be replaced in user provided format
                new_image_data = tag_data
                new_image_data['Folder'] = os.path.basename(root),
                new_image_data['Seq'] = '{0:0{1}d}'.format(next(seq), seq_width)

                # Generate new file name according to user provided format
                new_file_name = (input_format + '.{ext}').format(**new_image_data)
                new_file_name_complete = os.path.join(root, new_file_name)

                # file already has correct file name, skip it
                if old_file_name == new_file_name_complete:
                    if verbose and not quiet:
                        print(f'INFO: Skipping {old_file_name}, because it does already have correct file name!')
                    continue

                summary_files_processed += 1

                # target file name is already there, maybe high-speed shutter
                # was used (5 pics per second)
                # add a sequence number, so manual comparison is simplified
                if os.path.isfile(new_file_name_complete):
                    new_file_name_complete = find_new_name(new_file_name_complete)
                    if os.path.isfile(new_file_name_complete):
                        print('ERROR: Something went terribly wrong...')

                # Don't rename files if we are running in test mode
                if not test_mode:
                    try:
                        os.rename(old_file_name, new_file_name_complete)
                    except OSError:
                        skipped_files.append((old_file_name,
                                              'Failed to rename file'))
                        continue

                if verbose:
                    print('{0} --> {1}'.format(old_file_name,
                                               new_file_name_complete))
                elif not quiet:
                    print('{0} --> {1}'.format(f, new_file_name))

            # Folder processed
            print('')

            # Break if recursive flag is not present
            if not recursive:
                break

    print(f'Processed {summary_files_processed} files.')


if __name__ == '__main__':
    cli()
