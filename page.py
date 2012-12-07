#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Part of pyGrabber.

This module contiains a class used to represent a single page of a grabbing 
job. It deals with the actual ins and out of the file processing, calling
functions from lower-level modules to actually perform the processing


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

import codecs
import os
import sys
import shlex #for the cleaning command lexing
import re#for the command environment variable replacement
import shutil

import pages2djvu
import filetype_detector
import grabbersources
import utils
import pygrabber

#pywikipediabot imports
if pygrabber.USE_PYWIKIPEDIA:
    sys.path.append(pygrabber.PYWIKIPEDIA_PATH) 

    try:
        import wikipedia, upload
    except ImportError:
        print "(ERR) You need to set your pyWikipedia path, %s doesn't contain the 'wikipedia' modules needed." % pygrabber.PYWIKIPEDIA_PATH
        pygrabber.USE_PYWIKIPEDIA = False

class Page():
    """
    This class deals with a single page's information
    """

    error_encountered = False #flag to tell the external loop to skip the image
    ocr = None

    imageSize = None
    status = 'Queued.'
    have_file = False
    filepath = None


    def get_page_url(self):
        """Get the URL of the page holding the images from the source"""
        self.page_url = self.source.get_page_url()
        self.status = 'Found HTML page URL: %s' % self.page_url

    def get_image_url(self):
        """Ask the source for the image URL"""

        self.image_url = self.source.get_image_url()
        self.status = 'Found image URL: %s' % self.image_url


    def get_ocr_text(self, use_saved_ocr):
        """
        Retreive the OCR text from the source, or get it ourselves with
        Tesseract
        
        Input:
        use_saved_ocr   : if an existing OCR text file is found, use that, 
                            otherwise, regenerate the OCR
        """
        
        ocr_file = os.path.join(self.opts['book_directory'], '%04d.txt' % self.pageNumber)
        
        if os.path.exists(ocr_file) and use_saved_ocr:
            self.ocr = codecs.open(ocr_file, 'r', 'utf-8').read()            
            self.status = 'OCR text already exists (~%d chars).' % (os.path.getsize(ocr_file))
            return


        #if we will do all ocr ourselves, don't bother fetching OCR from the net
        if self.opts['force_tesseract']:
            self.ocr = False
        else:
            self.ocr = self.source.get_page_text()

        if self.ocr:
            method = 'Retrieved from source'
        else: #there's no easy way to get it, so do it locally
            if self.opts['fallback_tesseract']:
                method = "OCR'd with Tesseract"
                self.ocr = self.ocr_with_tesseract() # returns unicode
            else:
                self.status = "Not OCR'd."
                return


        try: #convert to unicode incase it isn't already
            self.ocr = unicode(self.ocr, 'utf-8')
        except TypeError:
            pass


        codecs.open(ocr_file, 'w', 'utf-8').write(self.ocr)
        self.status = 'OCR text completed (%s: ~%d chars).' % (method, len(self.ocr))

    def dump_ocr(self, dumpFile):
        """Append the page's OCR into the dump file
        
        Input:
        dumpFile    : file to dump the OCR to
        """

        fileHandler = codecs.open(dumpFile, 'a', 'utf-8')
        
        fileHandler.write('\n\n===Page %d===\n\n' % self.pageNumber)
        
        fileHandler.write(self.ocr)
        fileHandler.close()

    def ocr_with_tesseract(self):
        """OCR the page image with Tesseract"""
        
        ocr_file  = os.path.join(self.opts['book_directory'], 'TESSERACT-OCR-TXT-TEMP-FILE-%d' % self.pageNumber)

        if self.ext in ['.tif', '.jpg', '.png']: #if tesseract can't handle this image
            tiff_file = self.filepath
        else:
            tiff_file = os.path.join(self.opts['book_directory'], 'TESSERACT-OCR-TIFF-TEMP-FILE-%d.tiff' % self.pageNumber)
            cmd = [ 'convert', self.filepath, tiff_file]
            utils.run_cmd(cmd)

        if self.opts['clean_text']:
            
            sys.stdout.write("(INF) Cleaning text...")
            sys.stdout.flush()
            
            old_tiff_file = tiff_file
            
            root, ext = os.path.splitext(tiff_file)

            tiff_file = root + '.cleaned' + ext
            
            
            cmd_list = self.opts['clean_text_cmd'].split(';')
            
            new_cmd_list = []
            for cmd in cmd_list:
            
                # split the commands up in a "shell-like" way, preserving quoted parts as a single string
                cmd = shlex.split(str(cmd)) #this WILL break for unicode, but that is a limitation of shlex for python < 3.0 
                
                new_cmd = []
                for part in cmd:
                
                    part = os.path.expanduser(part) #sub any users
                    part = os.path.expandvars(part) #substitute any env variables
                    part = part.replace( '%fin', '%s'% old_tiff_file )
                    part = part.replace( '%fout', '%s'% tiff_file )
                    
                    new_cmd.append(part)
                    
                utils.run_cmd(new_cmd)
                
            if os.path.exists(old_tiff_file) and old_tiff_file != self.filepath:
                os.remove(old_tiff_file)
                
            print "done!"


        cmd = ['tesseract', tiff_file, ocr_file, '-l', self.opts['lang'] ]
        utils.run_cmd(cmd)
        
        ocr_file += '.txt'
        
        if os.path.exists(ocr_file):
            ocr = codecs.open(ocr_file, 'r', 'utf-8').read() #the ocr is a unicode string
        else:
            ocr = u''

        
        if os.path.exists(ocr_file): #kill the ocr temp file
            os.remove(ocr_file)
            
        if os.path.exists(tiff_file) and tiff_file != self.filepath:
            print tiff_file, 'exists!'
            os.remove(tiff_file)

        return ocr

    def convert_to_djvu(self, djvu_page_file):
        """Convert the page to a DJVU file and append it to the main file"""

        pages2djvu.convert_file(self.filepath, djvu_page_file, bitonal=self.opts['djvu_bitonal'], quality=self.opts['djvu_quality'])
        
        if os.path.isfile(djvu_page_file):
            self.djvu_page_filesize = os.path.getsize(djvu_page_file)
            self.status = 'Page converted to DJVU. (%s)' % utils.get_size_text(self.djvu_page_filesize,'kB')
            return True
        else:
            print ('\t(ERR) Page not converted to DjVu. Perhaps djvulibre is broken?')
            self.status = 'Page NOT converted to DJVU. An error occured in the conversion'
            return False

    def append_to_main_djvu(self, djvu_page_file, djvu_main_file):
        """Attach the page djvu to the main file."""

        pages2djvu.append_page(djvu_page_file, djvu_main_file)
        self.djvu_full_filesize = os.path.getsize(djvu_main_file)
        self.status = 'Page appended to DJVU. (Page size %s, total size: %s)' % (
                        utils.get_size_text(self.djvu_page_filesize),
                        utils.get_size_text(self.djvu_full_filesize))

    def upload_image(self):
        """Upload the page to Commons using the specified template name.

        pyWikipediabot needs to be set up for this beforehand."""

        upload_name = '%s - %04d%s' %(self.opts['filename_prefix'], self.pageNumber, self.ext)

        description = "{{%s|%04d}}" % (self.opts['template'], self.pageNumber)

        print '\t(INF) Page is going to be uploaded as: File:%s' % upload_name

        uploader = upload.UploadRobot(
                            useFilename = upload_name,
                            description = description,
                            targetSite = wikipedia.getSite("commons", "commons"),
                            url = self.filepath,
                            keepFilename = True,
                            verifyDescription = True,
                            ignoreWarning = self.opts['force_upload'])
        uploader.run()

        self.status = 'File uploaded to Commons as: File:%s' % upload_name


    def get_image_file(self):
        """Go and get the indicated image file. If this fails, set the status
        and error bit accordingly"""

        self.image_file = self.source.get_image_file()

        if self.image_file:
            self.error_encountered = False
            self.imageSize = len(self.image_file)
        else:
            self.error_encountered = True
            
    
    def clear_image_file(self):
        """
        Delete the image file to save memory
        """
        self.image_file = None 


    def construct_filename(self):
        """Construct the absolute filename of the image, witohut the extension
        which we will determine using magic, as some websites aren't clear"""

        if not os.path.exists(self.opts['book_directory']): #create the target directory if it doesn't exist.
            os.mkdir(self.opts['book_directory'])

        self.filepath = os.path.join(self.opts['book_directory'], '%04d'%( self.pageNumber))


    def save_image(self):
        """Write the image to a local file. Clear it from this object after that
        as images take a up lot of memory, and we can always reload from disk
        if we need"""
        
        if self.error_encountered:
            self.status = 'Image not found.'
            return
        
        self.construct_filename()

        localImageFile = open(self.filepath, 'w')
        localImageFile.write(self.image_file)
        localImageFile.close()
        self.have_file = True # we now have the file locally
        self.clear_image_file()

        #check the mimetype and rename accordingly
        filetype = filetype_detector.FileTypeDetector(self.filepath).detect()

        if filetype == 'jpeg':
            self.ext = '.jpg'
        elif filetype == 'png':
            self.ext = '.png'
        elif filetype == 'tif':
            self.ext = '.tif'
        elif filetype == 'gif':
            self.ext = '.gif'
        elif filetype == 'jp2':
            self.ext = '.jp2'
        else:
            self.ext = '.UNKNOWN'


        if self.ext == 'UNKNOWN':
            print '\t(ERR) Unknown file format'
        else:
            print '\t(INF) Identified file format: %s' % filetype

        shutil.move(self.filepath, self.filepath + self.ext)
        self.filepath += self.ext
        
        self.status = 'Saved image file to local file system.'


    def add_ocr_to_djvu(self, djvu_filename):
        """Adds the OCR in this pageItem to the (temporary) djvu file."""
        if not self.ocr:
            return

        pages2djvu.add_ocr_text(self.ocr, djvu_filename, 1)
        self.status = 'OCR text added to DJVU page. About %s chars.' % len(self.ocr)
        
    def get_filename(self):
        """
        Return just the filename of the filepath
        
        Return None is we don't have a file
        """
        
        if self.have_file:
            head, tail = os.path.split(self.filepath)
            return tail
        else:
            return None
        
    def set_filename(self, filepath):
        """
        Set the filename, and flag as "have image". Find the size too
        """
        
        self.have_file = True
        self.filepath = filepath
        
        self.status = "File already exists locally."
        
        self.imageSize = os.path.getsize(self.filepath)
        
        root, self.ext = os.path.splitext(self.filepath)
        

    def __init__(self, pageNumber, list_index, opts, source):
        self.opts = opts
        self.pageNumber = pageNumber
        self.list_index = list_index
        self.source = source
