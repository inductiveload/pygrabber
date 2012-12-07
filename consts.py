#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Part of pyGrabber.

This file contains constants used in pyGrabber
"""

import wx
import grabbersources

NICENESS = '19' #pyGrabber's heavy-duty functions try to yield to other processes on the computer
DOWNLOAD_ATTEMPTS = 10 # time to retry if the file appears corrupt

#COLOURS
COLOUR_ERR = wx.Colour(248, 128, 128)
COLOUR_OK = wx.Colour(160, 220, 101)
COLOUR_INACTIVE = wx.Colour(211, 215, 207)

#RESULT STATUS CODES
RESULT_PAGELIST_POPULATED = 0
RESULT_ALL_PROCESSED = 1
RESULT_REACHED_PAGENUMBER = 2
RESULT_WAITING = 3
RESULT_FOUND_PAGE_URL = 4
RESULT_FOUND_IMAGE_URL = 5
RESULT_SAVED_FILE = 6
RESULT_FETCH_FAILED = 7
RESULT_OCR_COMPLETE = 8
RESULT_DJVU_COMPLETE = 9
RESULT_DJVU_OCRD = 10
RESULT_DJVU_APPENDED = 11
RESULT_UPLOADED = 12
RESULT_PAGE_COMPLETE = 13
RESULT_PAGE_MISSING = 14


_sourceList = [ grabbersources.SourceHathi,
                grabbersources.SourceSceti,
                grabbersources.SourceBfeld,
                grabbersources.SourceGallica ]

#create a dictionary of sources, using an abbreviation as the key
SOURCES = {}
for source in _sourceList:
    SOURCES[source.key] = source
