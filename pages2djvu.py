#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Part of pyGrabber.

This file contains some functions used for djvu processing.
"""

import os
import codecs

import utils


def convert_file(page_image, page_djvu, bitonal=False, quality=48, force_convert=False):
    """
    Convert an image to DJVU with the given parameters:
    
    page_image      : image filename to convert
    page_djvu       : djvu file of the converted image (target)
    bitonal         : bitonal djvu output?
    quality         : decibel quality 16-50
    force_convert   : always run through imagemagick
    """

    directory = os.path.dirname(page_image)

    #create temporary DJVU file
    if bitonal:
        tempPpm  = os.path.join(directory, 'IMG-DJVU-CONVERTER-TEMP-FILE.pbm')
    else:
        tempPpm  = os.path.join(directory, 'IMG-DJVU-CONVERTER-TEMP-FILE.ppm')

    root, ext = os.path.splitext( page_image )

    if not bitonal and ext.lower() in ['.jpg', '.jpeg']:

        if force_convert:
            cmd = ['convert', page_image, tempPpm]
            utils.run_cmd(cmd)
            file = tempPpm
        else:
            file = page_image

        #convert jpg to a temp djvu file
        cmd = ['c44', '-decibel', str(quality), file, page_djvu]
        
        utils.run_cmd(cmd)

    elif bitonal and ext.lower() in ['.tiff','.tif']:
        #convert jpg to a temp djvu file
        cmd = ['cjb2', page_image, page_djvu]
        
        utils.run_cmd(cmd)

    else: #image needs converting

        cmd = ['convert', page_image, tempPpm]
        #print cmd
        utils.run_cmd(cmd)

        if bitonal:
            cmd = ['cjb2', tempPpm, page_djvu]
        else:
            cmd = ['c44', '-decibel', str(quality), tempPpm, page_djvu]
            
        utils.run_cmd(cmd)


    #Remove any leftover temporary files
    if os.path.exists(tempPpm):
        os.remove(tempPpm)


def append_page(page, main_file):
    """
    Appends a DjVu page to a main file
    
    page        : single page djvu file
    main_file   : file to append to
    """

    if os.path.exists(main_file):
        #Add the djvu file to the collated file
        cmd = ['djvm','-i', main_file, page]
    else:
        # Create the collated file
        cmd = ['djvm', '-c', main_file, page]

    utils.run_cmd(cmd)


def add_ocr_text(ocr, djvu_filename, page):
    """
    Adds an OCR text later to the page. Does not bother with position.
    
    ocr             : text layer
    djvu_filename   : the djvu file to add the text to
    page            : the page of the file to add the layer to
    """  

    directory = os.path.dirname(djvu_filename)

    djvu_text = u"(page 0 0 1 1\n"

    ocr_lines = ocr.split('\n')

    for line in ocr_lines:
        #escape \ and " characters
        djvu_text += u'(line 0 0 1 1 "%s")\n' % line.replace('\\', '\\\\').replace('"', '\\"').strip()

    djvu_text += ")\n"

    djvu_text_file = os.path.join(directory, 'DJVU-FORMATTED-OCR-TEXT-TEMP-FILE-%d.txt'%page)
    djvu_text_file_handler = codecs.open(djvu_text_file, 'w', 'utf-8')
    djvu_text_file_handler.write(djvu_text)
    djvu_text_file_handler.close()

    # remove the existing text
    cmd = ['djvused', djvu_filename, '-e', 'select %d; remove-txt' % page, "-s"]
    utils.run_cmd(cmd)

    # set the new text
    cmd = ['djvused', djvu_filename, '-e', 'select %d; set-txt %s'% (page, djvu_text_file), "-s"]
    utils.run_cmd(cmd)

    if os.path.exists(djvu_text_file):
        os.remove(djvu_text_file)
