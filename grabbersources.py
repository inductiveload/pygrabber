#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Part of pyGrabber.

This module contains the core functions used to actually retrieve images from
online libraries and repositories.

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

import consts

import re
import sys
import urllib2, urlparse
import socket
from lxml.html import fromstring, tostring

import clean_html

class GrabberSource():
    """
    Base class for all pyGrabber sources
    """
    construct_image_page_url = None #null function, these are defined as required.
    construct_image_url = None
    construct_text_url = None
    construct_book_url = None
    page_text_is_direct = False #the website delivers the ocr directly as a file: no html parsing is required

    def set_page_number(self, number):
        self.page_number = number

    def get_page_url(self):
        if self.construct_image_page_url: #we need to load an HTML page first to determine the image location
            self.page_url = self.construct_image_page_url (self.opts['textid'], self.page_number)
        else:
            self.page_url = None

        return self.page_url


    def get_data_from_url(self, url, read=False):
        """Try to get the data, retry upon timeout, and exceptions

        If you want the data, specify read, otherwise you get the opened_url object

        If the server doesn't return code 200, you get false
        """

        while True:
            try:
                opened_url = urllib2.urlopen(url)

                code = opened_url.code
                if code != 200:
                    print ('(ERR) HTTP code %d returned, skipping.'%code)
                    return False
                else:

                    if read:
                        return opened_url.read()
                    else:
                        return opened_url

            except socket.timeout: #FIXME
                print ('\t(ERR) timed out, retrying' )
            except urllib2.URLError:
                print ('\t(ERR) URLopen error, retrying' )
                err = sys.exc_info()#[1]
                print ('\t\t%s' % str(err))
            #except:
            #    print ("\t(ERR) Unknown exception: %s" % sys.exc_info()[1])
            return False


    def get_image_url(self):

        if self.page_url:
            # we need to search in the page HTML
            html_page = self.get_data_from_url(self.page_url, read=True)
            mySearchTree = fromstring(html_page)

            self.image_url = self.extract_image_url(mySearchTree)

        else:
            # we can directly construct the URL
            if self.construct_image_url:
                self.image_url = self.construct_image_url(self.opts['textid'], self.page_number)
            else:
                self.image_url = None

        return self.image_url


    def get_image_file(self):

        while True:
            try:
                image = self.get_data_from_url(self.image_url, read=True)

                if not image: # 200 code not received
                    break
            except AttributeError:
                print '(ERR) URL not resolved, maybe you need a proxy.'
                break

            if len(image) > 1000: #less than 1kB, probaly corrupt
                return image

    def get_page_text(self):

        if self.construct_text_url:
            self.text_url = self.construct_text_url(self.opts['textid'], self.page_number)
        else:
            return None #there is no text resource associated with the source

        if self.page_text_is_direct:
            retrieved_ocr = self.get_data_from_url(self.text_url, read=True)

            try:
                retrieved_ocr = retrieved_ocr.strip()
            except AttributeError:
                pass
        else:
            html_page = self.get_data_from_url(self.text_url, read=True)

            mySearchTree = fromstring(html_page)

            retrieved_ocr = self.extract_page_text(mySearchTree)

        return retrieved_ocr


    def setup_urlopener(self):

        if self.opts['use_proxy']:
            proxy_handler = urllib2.ProxyHandler({'http': self.opts['proxy']})
            opener = urllib2.build_opener(proxy_handler)
        else:
            opener = urllib2.build_opener()

        opener.addheaders = [('User-agent', 'Opera/9.80 (Windows NT 5.1; U; en) Presto/2.5.24 Version/10.52')]
        urllib2.install_opener(opener)

    def get_book_url(self):
        """Open the web page of the book"""

        if self.book_url_template:
            return self.book_url_template % self.opts
        else:
            return None

    def __init__(self, opts, page_number=-1):

        self.page_number = page_number
        self.opts = opts
        self.setup_urlopener()


class SourceHathi(GrabberSource):
    key = 'HATHI'
    description = "Hathi Trust"
    page_text_is_direct = True

    def construct_book_url(self, textid):
        return 'http://babel.hathitrust.org/cgi/pt?id=%s' % textid
        
    def construct_image_url(self, textid, number):
        return 'http://services.hathitrust.org/htd/pageimage/%s/%d' % (textid, number)
        
    def construct_text_url(self, textid, number):
        return 'http://services.hathitrust.org/htd/pageocr/%s/%d' % (textid, number)  #http://babel.hathitrust.org/cgi/pt?id=umn.31951d02988297j;page=root;seq=1;view=text;size=100;orient=0
    
    
    #page_url_template = 'http://babel.hathitrust.org/cgi/pt?id=%(textid)s;seq=%(number)d;size=200;'

    #def extract_image_url(self, searchTree):
        ## <img alt="image of individual page" id="mdpImage" src="/cache/imgsrv/mdp/pairtree_root/39/01/50/59/06/26/80/39015059062680/00000092.jp2.1360.0.0.jpg" width="1360" height="2157" />

        ## while the image is not hard to find, it is impossible to tell whether you are looking for a jp2 or tif base file.

        #for a in searchTree.cssselect('img'):

            #if 'id' in a.attrib and a.attrib['id'] == 'mdpImage':
                #image_url = 'http://babel.hathitrust.org' + a.attrib['src']

                #return image_url

    #def extract_page_text(self, searchTree):
        #retrieved_ocr = None
        #for a in searchTree.cssselect('div#mdpText > p'):

            #retrieved_ocr = tostring(a)
            #retrieved_ocr = clean_html.clean_html(retrieved_ocr, newline_at_br=False)

        #return retrieved_ocr


class SourceSceti(GrabberSource):
    key = 'SCETI'
    description = "SCETI, University of Pennsylvania"

    def construct_book_url(self, textid):
        return 'http://sceti.library.upenn.edu/sceti/printedbooksNew/index.cfm?TextID=%s&PagePosition=1' % textid
        
    def construct_image_page_url(self, textid, number):
        return 'http://sceti.library.upenn.edu/sceti/printedbooksNew/image.cfm?PagePosition=%d&TextID=%s' % (number, textid)

    def extract_image_url(self, searchTree):

        #<img alt="1" src="http://sceti.library.upenn.edu/sceti//etext/collections/furness/holinshed_ireland/008.jpg">
        image_url = None
        for a in searchTree.cssselect('input'):
            if a.name == 'myimage':
                image_url = a.attrib['src']


        if not image_url:
            for a in searchTree.cssselect('img'):
                image_url = a.attrib['src']

        if image_url:
            image_url = re.sub(r'level=\d', 'level=0', image_url)

            return image_url

class SourceBfeld(GrabberSource):
    key = 'BFELD'
    description = "University of Bielefeld: Digital Library"

    def construct_book_url(self, textid):
        return 'http://www.ub.uni-bielefeld.de/diglib/more/%s/' % textid
        
    def construct_image_url(self, textid, number):
        return 'http://www.ub.uni-bielefeld.de/diglib/more/%s/jpeg/%08d.jpg' % (textid, number)

class SourceGallica(GrabberSource):

    key = 'GALLICA'
    description = "Gallica: Bibliothèque Nationale de France"
    # textids look like btv1b8402704r
    
    def construct_book_url(self, textid):
        return 'http://gallica.bnf.fr/ark:/12148/%s' % textid
        
    def construct_image_url(self, textid, number):
        return 'http://gallica.bnf.fr/proxy?method=R&ark=%s.f%d&l=%d' % (textid, number, 50) #zoomlevel 50 should be plenty!
        
    def construct_text_url(self, textid, number):
        return 'http://gallica.bnf.fr/ark:/12148/%s/f%d.texte' % (textid, number)


    def extract_page_text(self, searchTree):
        retrieved_ocr = None
        for a in searchTree.cssselect('div#modeTexte > div'):
            retrieved_ocr = tostring(a)
            retrieved_ocr = clean_html.clean_html(retrieved_ocr, newline_at_br=True)

        return retrieved_ocr
        
#class SourceLoC(GrabberSource):
    #key = 'LOC'
    #description = "Library of Congress"

    
    #book_url_template = 'http://www.ub.uni-bielefeld.de/diglib/more/%(textid)s/'

    #image_url_template = 'http://lcweb2.loc.gov/service/rbc/rbc0001/2009/2009mcyoung02604/%(number)04dv.jpg'
    
    #def make_url_template( textid ):
        ##rbc0001_2009mcyoung02604
        
        
