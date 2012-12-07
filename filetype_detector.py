#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Very simple, very limited filetype detector based on magic numbers.

DISCLAIMER:
pyGrabber is to be used ONLY to download public domain book in a legal
fashion. The capability of pyGrabber to download from a specific resource
does not imply that you are allowed to, and you do so at your own risk.

LICENCE:
This program is free software; you can redistribute it and/or modify it
under the terms of the GNU General Public License as published by the Free
Software Foundation; either version 3 of the License, or (at your option)
any later version.

This program is distributed in the hope that it will be useful, but WITHOUT
ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for
more details.

You should have received a copy of the GNU General Public License along with
this program; if not, write to the Free Software Foundation, Inc., 51
Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
"""

import optparse


SIGS = {    'jpeg' :  [  {0:0xFF, 1:0xD8, -2:0xFF, -1:0xD9} ], #[0:1] = FF D8, [-2:-1] = FF D9

            'png'  : [  {0:0x89, 1:0x50, 2:0x4E, 3:0x47, 4:0x0D, 5:0x0A, 6:0x1A, 7:0x0A} ], #[0:7] = \211 P N G \r \n \032 \n (89 50 4E 47 0D 0A 1A 0A)

            'gif'  : [  {0:0x47, 1:0x49, 2:0x46, 3:0x38, 4:0x37, 5:0x61},  # [0:5] =  "GIF87a" (47 49 46 38 37 61)
                        {0:0x47, 1:0x49, 2:0x46, 3:0x38, 4:0x39, 5:0x61} ], # [0:5] =  "GIF89a" (47 49 46 38 39 61)

            'tif'  : [  {0:0x49, 1:0x49, 2:0x2A, 3:0x00},
                        {0:0x4D, 1:0x4D, 2:0x00, 4:0x2A} ],

            'jp2'  : [  {0:0x00, 1:0x00, 2:0x00, 3:0x0C, 4:0x6A, 5:0x50, 6:0x20, 7:0x20, 8:0x0D, 9:0x0A} ],
        }


class FileTypeDetector(object):

    def __init__(self, filename):

        self.data = open(filename, 'r').read()

    def detect(self):

        for sig in SIGS:

            if self.compare_data_and_sig(SIGS[sig]):
                return sig

        return None


    def compare_data_and_sig(self, sig_list):

        for sig in sig_list: #for each possible magic word:
            match = True
            for index in sig:
               if ord(self.data[index]) != sig[index]:
                    match = False

            if match:
                return True

        return False



if __name__ == "__main__":
    parser = optparse.OptionParser(usage='Usage: %prog -f <file>')
    parser.add_option('-f', dest='file', action='store',\
                             help='the file to detect')

    (opts, args) = parser.parse_args()

    # check mandatory options
    if opts.file == None:
        print("The input file must be given\n")
        parser.print_help()
        exit(-1)

    FileTypeDetector(opts.file)
