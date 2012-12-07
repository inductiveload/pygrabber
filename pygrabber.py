#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
pyGrabber is a program to download books from the internet.

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

USE_PYWIKIPEDIA = True #change this to false if you don't have pyWikipedia - you won't be able to upload
PYWIKIPEDIA_PATH = '/home/john/src/pywikipedia' #change this to match your install

import codecs
import sys
import os
import time
import re
import shutil
import threading
import pickle
import webbrowser

# GUI IMPORTS
import wx
import wx.lib.scrolledpanel
import wx.lib.buttons

# grabber imports
import consts
import page
import utils

# GLOBAL CONSTANTS
NAME = 'pyGrabber'
VERSION = '0.1.7'



class GrabberMainFrame(wx.Frame):
    """
    This is the main GUI class. It deals with gathering and validating user
    settings, and responds to the state of an ongoing job, but doesn't actually
    do any file processing itself, to avoid locking up.
    
    This class communicates with the FileGrabber class to initiate grabbing as
    responds to status signals from there. It can also reach down to get info
    on Page objects through the FileGrabber class.
    """

    freeze_attributes = False #stop the attributes updating when we load them from file
    default_opts = os.path.join( os.path.dirname(__file__) , 'grabs', 'default.grab')

    def on_exit(self, e):
        
        try:
            self.imageDisplayFrame.Close(True)
        except AttributeError:
            pass

        self.Destroy()  # Close the frame.

    def on_about(self, e):

        description = "pyGrabber is an eBook downloader, which can grab and \
collate eBooks from several sources on the web, and is intended to be easily \
expanded to other sources."

        licence = """pyGrabber is free software; you can redistribute it and/or modify it
under the terms of the GNU General Public License as published by the Free Software Foundation;
either version 2 of the License, or (at your option) any later version.

pyGrabber is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY;
without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
See the GNU General Public License for more details. You should have received a copy of
the GNU General Public License along with File Hunter; if not, write to
the Free Software Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA"""

        info = wx.AboutDialogInfo()

        info.SetIcon(wx.Icon(os.path.join(os.path.dirname(__file__) , 'icons', 'grabber_48.png'), wx.BITMAP_TYPE_PNG))
        info.SetName(NAME)
        info.SetVersion(VERSION)
        info.SetDescription(description)
        info.SetLicence(licence)

        wx.AboutBox(info)

    def on_attributes_changed(self, e):
        """
        If an attribute which requires us to do something instantly is changed.
        """

        if not self.freeze_attributes: #don't do anything if the attributes are frozen
            self.get_attributes()
            
    def on_clock_tick(self, e):
        
        self.clockTime += 1
        self.update_time()
        

    def on_begin_grabbing(self, e):
        """
        Begin a file grabbing job. This is done by requesting the pagelist be
        set up by the FileGrabber instantiation. The signal emitted on that
        completion will trigger the rest of the processing
        """
        self.currentPage = self.opts['pg_start']
        self.clockTimer.Start(1000) #start the clock!
        self.clockTime = 0
        self.update_time() #reset the status text
        
        self.aborted = False
        self.btns['abort'].Enable(True) #prevent another job starting, and allow abortion
        self.btns['run'].Enable(False)
        
        self.djvu_size_list = [] #reset the djvu page size list
        
        self.get_attributes() #make sure the attributes are all fresh
        
        if self.valid:#only fire if the attributes are all ok
        
            self.fileGrabber = FileGrabber(self, self.opts, self.source) # setup the FileGrabber with the options.
            
            worker = threading.Thread(target=self.fileGrabber.setup_pagelist) # spawn a thread...
            worker.start()#and fire
                        

    def on_abort(self, e):
        """
        Request that the FileGrabber aborts as soon as possible. This could
        take a while, depending on what it is doing (downloading and OCR are slow)
        """
        self.fileGrabber.abort()
        self.statusBar.SetStatusText("Aborting, please wait for outstanding processes to terminate. Some processes may take a long time to finish.")


    def on_delete_all(self, e):
        """
        Delete all the files in the book directory
        """

        if os.path.isdir(self.opts['book_directory']):

            number_of_files = len(os.listdir(self.opts['book_directory']))

            dialog = wx.MessageDialog(None,
                'Are you sure you want to delete %d files?' % number_of_files,
                'Delete all files?', wx.YES_NO | wx.NO_DEFAULT | wx.ICON_EXCLAMATION)
            answer = dialog.ShowModal()

            if answer == wx.ID_YES:
                shutil.rmtree(self.opts['book_directory'])

                notification = 'Removed %d files.' % number_of_files
                self.statusBar.SetStatusText(notification)
                print '(INF) ' + notification
                
                
    def on_worker_event(self, e):
        """
        The callback to respond to signals coming in from worker threads
        """
                
        status = e.data[0]
        
        if status == consts.RESULT_PAGELIST_POPULATED:
            self.populate_filelist() #display the pages in the page list
            self.process_pages() #go to process the first page
        
        elif status == consts.RESULT_ALL_PROCESSED:
            self.processing_done() #clean up after the processing
            
        elif status == consts.RESULT_REACHED_PAGENUMBER:
            self.scroll_to_item(e.data[1])
            self.currentPage = e.data[1]
            
        elif status in [consts.RESULT_WAITING, consts.RESULT_FOUND_PAGE_URL,
                        consts.RESULT_FOUND_IMAGE_URL, consts.RESULT_DJVU_OCRD,
                        consts.RESULT_DJVU_APPENDED,
                        consts.RESULT_UPLOADED, consts.RESULT_OCR_COMPLETE,
                        consts.RESULT_FETCH_FAILED
                        ]:
            self.update_file_status(e.data[1])
            
        elif status == consts.RESULT_PAGE_MISSING:
            self.update_file_status(e.data[1])
            self.mark_missing_page(e.data[1])

        elif status == consts.RESULT_SAVED_FILE:
            self.update_file_status(e.data[1])
            self.update_file_size(e.data[1])
            self.update_file_name(e.data[1])
            
        elif status == consts.RESULT_DJVU_COMPLETE:
            self.update_file_status(e.data[1])
            self.update_djvu_size_projection(e.data[1])
            
        elif status == consts.RESULT_PAGE_COMPLETE:
            self.update_progress_bar(e.data[1])
            if self.opts['show_images']:
                self.display_image(e.data[1])

        

    def on_open_top_directory(self, e):
        """
        Open the filemanager to show the "top" directory
        """
        os.system('%s "%s"' % (utils.get_file_manager_cmd(), self.opts['top_directory']))


    def on_open_book_directory(self, e):
        """
        Open the filemanager to show the "book" directory
        """
        os.system('%s "%s"' % (utils.get_file_manager_cmd(), self.opts['book_directory']))


    def on_open_website(self, e):
        """
        Open the webpage for the book
        """

        url = self.source.get_book_url()

        if url:
            webbrowser.open(url)
            
            
    def on_get_directory(self, e):
        
        for key in ['book_directory', 'top_directory']:
            if e.GetEventObject() == self.ctrls[key]:
                ctrl_key = key
                
        self.freeze_attributes = True
        self.opts[ctrl_key] = self.choose_directory(initial_path=self.opts[key])
        self.apply_attributes()
        self.freeze_attributes = False
            
    def on_guess_pages_from_files(self, e):
        
        if not os.path.isdir(self.opts['book_directory']): #can't guess if there is no directory!
            return
            
        self.freeze_attributes = True
        index = 0
                
        # find the lower most filenumber 
        while True:
            if utils.is_file_in_directory(self.opts['book_directory'], index, type='IMAGE', format="%04d"):
                break
            
            index += 1
            
        self.opts['pg_start']=index
        
        #find the highest filenumber
        while True:
            if not utils.is_file_in_directory(self.opts['book_directory'], index, type='IMAGE', format="%04d"):
                break
            
            index += 1
    
        self.opts['pg_end'] = index-1
        
        self.apply_attributes()
        
        self.freeze_attributes = False

# PARAMETER VALIDATION AND HANDLING ==========================================

    def check_valid_ip(self):
        """Check if the given IP is valid, and colour accordingly

        Return True if the IP is valid, or it isn't needed."""

        ip = self.ctrls['proxy'].Value

        m = re.match(r'(\d+\.\d+\.\d+\.\d+)(:\d+)?$', ip)

        valid = not self.opts['use_proxy'] or m
        
        self.show_error_control( self.ctrls['proxy'],  not valid)

        return valid

    def check_page_range(self):
        """
        Make sure the lower page bound is smaller than the upper one
        """

        valid = self.ctrls['pg_start'].Value <= self.ctrls['pg_end'].Value

        self.show_error_control(self.ctrls['pg_end'], not valid)
        self.show_error_control(self.ctrls['pg_start'], not valid)

        return valid
        
    def enable_diasable_text_ctrl(self, control, enabled, always_editable=False):
        """If a control is diabled, it will havea grey backgrounds and 
        not be editable 
        
        enabled : true if you wish to enable the ctrl, false otherwise
        always_editable : true if you can edit the ctrl even when disabled"""
        
        control.Enable(enabled or always_editable)
        
        if always_editable:
            control.SetBackgroundColour(wx.WHITE if enabled else consts.COLOUR_INACTIVE)
        
    def show_error_control(self, control, error):
        """Show that a control has an error"""
        control.SetBackgroundColour( consts.COLOUR_ERR if error else wx.WHITE)

    def get_attributes(self):
        """Read the options out of the controls"""
        self.opts={}

        for control in self.ctrls:
            self.opts[control] = self.ctrls[control].GetValue()
            
        self.freeze_attributes=True #prevent updates from causing a recursive loop

        #immediate reponses to changed attributes

        #update the book directory control if we want it to be automatic
        
        if not self.opts['custom_bk_dir']:
            self.opts['book_directory'] = os.path.join(self.opts['top_directory'], '%s_%s'%(self.opts['source'],self.opts['textid']) )
            
            self.enable_diasable_text_ctrl(self.ctrls['top_directory'], True )
            self.enable_diasable_text_ctrl(self.ctrls['book_directory'], False )

            self.ctrls['book_directory'].SetValue(self.opts['book_directory'])
        else:
            self.enable_diasable_text_ctrl(self.ctrls['top_directory'], False )
            self.enable_diasable_text_ctrl(self.ctrls['book_directory'], True )
            self.opts['book_directory'] = self.ctrls['book_directory'].GetValue()
            
        self.enable_diasable_text_ctrl(self.ctrls['clean_text_cmd'], self.opts['clean_text'], always_editable=True)

        valid_proxy_ip = self.check_valid_ip()

        valid_page_range = self.check_page_range()

        if valid_page_range:
            self.progress_gauge.SetRange(self.opts['pg_end'] - self.opts['pg_start'] + 1)
        else:
            self.progress_gauge.SetRange(1)

        self.progress_gauge.SetValue(0)
        
        if valid_proxy_ip and valid_page_range:
            self.valid = True
            self.source = consts.SOURCES[self.opts['source']](self.opts) #instantiate the source
        else:
            self.valid = False
            
        self.freeze_attributes=False
        
    def apply_attributes(self):
        """
        Set up the controls in the setting panel based on the opts dictionary.
        This is done when the settings are loaded from file.
        """

        for control in self.opts:
            self.ctrls[control].SetValue( self.opts[control] )
            
        self.get_attributes()

# PARAMETER SAVE/LOAD CALLBACKS AND ROUTINES ===================================

    def choose_directory(self, prompt_text="Please choose a directory", initial_path='~'):
        """Allow user to select a directory"""
        
        if not initial_path: #watch out for empty initial path
            initial_path = '~'
        
        initial_path = os.path.expanduser(initial_path)
        dialog = wx.DirDialog(self, prompt_text, defaultPath=initial_path)
        if dialog.ShowModal() == wx.ID_OK:
            return dialog.GetPath()

    def on_save_as(self, e):
        """Save the parameters as a user-chosen filename"""

        dirname = ''
        dlg = wx.FileDialog(self, "Choose a file", dirname, "", "*.grab",
                        wx.SAVE | wx.OVERWRITE_PROMPT)
        if dlg.ShowModal() == wx.ID_OK:

            self.get_attributes()
            filename = os.path.join(dlg.GetDirectory(), dlg.GetFilename())
            self.save_opts_to_file(filename)


    def on_save_as_default(self, e):
        """Save the parameters as the defaults file"""
        self.get_attributes()
        self.save_opts_to_file(self.default_opts)


    def save_opts_to_file(self, filename):
        """Save parameters to a given file"""
        opts_file = open(filename , 'w')
        pickle.dump(self.opts, opts_file)
        opts_file.close()


    def on_open(self, e):
        
        dirname = ''
        dlg = wx.FileDialog(self, "Choose a file", dirname, "", "*.grab", wx.OPEN)
        if dlg.ShowModal() == wx.ID_OK:

            opts_filename = os.path.join(dlg.GetDirectory(), dlg.GetFilename())
            self.load_opts_from_file(opts_filename)


    def load_opts_from_file(self, opts_filename):
        """
        Load user parameters from a given filename.
        
        Inputs:
        opts_filename: the filename holding the user parameters
        """

        try:
            opts_file = open(opts_filename,'r')

        except IOError:
            print "(ERR) Failed to load file %s" % opts_filename
            return

        try:
            self.freeze_attributes = True
            self.opts = pickle.load(opts_file)
            opts_file.close()
            self.apply_attributes()
        except:
            print "(ERR) Failed to load attributes from file %s. The .grab file may be corrupt or for another version of pyGrabber" % opts_filename

        self.freeze_attributes = False

    def load_default_file(self):
        """
        Load the file from the default storage file
        """
        self.load_opts_from_file(self.default_opts)
        
# PAGE PROCESSING FUNCTIONS ====================================================

    def process_pages(self):
        """
        Initiate a page processing.
        """
        self.statusBar.SetStatusText("") # clear the status bar
        worker = threading.Thread(target=self.fileGrabber.initiate_grab)
        worker.start()
        
    def processing_done(self):
        """
        All pages have finished processing. Decide what to do next.
        
        pageNumber: the pageNumber of the page in question
        """
        
        self.clockTimer.Stop()
        self.statusBar.SetStatusText('Est. remaining: ' + utils.format_time(0), number=2)
        
        if self.fileGrabber.aborted:
            print "(INF) Aborted!"
            self.statusBar.SetStatusText("Grab aborted.")
        else:
            print "(INF) Processing complete!"
            self.statusBar.SetStatusText("Grab complete.")
        
        self.btns['abort'].Enable(False)
        self.btns['run'].Enable(True)
        
# SETUP FUNCTIONS ==============================================================

    def setup_menus(self):
        """
        Sets up the menu bar

        All the menus are added to the self.menus dict
        """

        #Create the menu dictionary,
        self.menus = {}

        # Setting up the file menu.
        self.menus['file']  = wx.Menu()

        menuSave = self.menus['file'].Append(wx.ID_SAVE,"&Save as default", "Save the grabbing parameters as the default parameters loaded when pyGrabber is started")
        self.Bind(wx.EVT_MENU, self.on_save_as_default, menuSave)

        menuSaveAs = self.menus['file'].Append(wx.ID_SAVEAS,"Save &As...", "Save the grabbing parameters")
        self.Bind(wx.EVT_MENU, self.on_save_as, menuSaveAs)

        menuOpen = self.menus['file'].Append(wx.ID_OPEN,"&Open", "Open previously saved grabbing parameters")
        self.Bind(wx.EVT_MENU, self.on_open, menuOpen)

        self.menus['file'].AppendSeparator()

        menuExit = self.menus['file'].Append(wx.ID_EXIT,"E&xit", "Terminate the program")
        self.Bind(wx.EVT_MENU, self.on_exit, menuExit)

        # Set up help menu
        self.menus['help'] = wx.Menu()

        menuAbout = self.menus['help'].Append(wx.ID_ABOUT, "&About", "Information about this program")
        self.Bind(wx.EVT_MENU, self.on_about, menuAbout)

        # Create the menubar, add all the menus
        self.menus['menubar'] = wx.MenuBar()
        self.menus['menubar'].Append(self.menus['file'], "&File")
        self.menus['menubar'].Append(self.menus['help'], "&Help")

        # Adding the MenuBar to the Frame content.
        self.SetMenuBar(self.menus['menubar'])

    def create_controls(self, panel):
        """
        Create the controls for the settings. They will be laid out later on
        
        Inputs:
        panel   : the parent panel for the controls
        """
        
        self.ctrls = {} #dict for all settings controls
        self.btns = {} # for buttons

        self.lbls = {}

        self.ctrls['textid'] = wx.TextCtrl(panel)
        self.Bind( wx.EVT_TEXT, self.on_attributes_changed,  self.ctrls['textid'])

        sourceList = [ key for key in consts.SOURCES ]
        self.ctrls['source'] = wx.ComboBox(panel, wx.ID_ANY, sourceList[1], wx.DefaultPosition,
                            (100,-1), sourceList, wx.CB_DROPDOWN)
        self.Bind( wx.EVT_COMBOBOX, self.on_attributes_changed,  self.ctrls['source'])


        self.ctrls['pg_start'] = wx.SpinCtrl(panel)
        self.ctrls['pg_start'].SetRange(0,10000)
        self.ctrls['pg_start'].SetValue(1)
        self.Bind( wx.EVT_SPINCTRL, self.on_attributes_changed,  self.ctrls['pg_start'])

        self.ctrls['pg_end'] = wx.SpinCtrl(panel)
        self.ctrls['pg_end'].SetRange(0,10000)
        self.ctrls['pg_end'].SetValue(92)
        self.Bind( wx.EVT_SPINCTRL, self.on_attributes_changed,  self.ctrls['pg_end'])

        self.ctrls['use_proxy'] = wx.CheckBox(panel, label="Use a proxy.  IP:")
        self.Bind( wx.EVT_CHECKBOX, self.on_attributes_changed,  self.ctrls['use_proxy'])

        self.ctrls['proxy'] = wx.TextCtrl(panel)
        self.Bind( wx.EVT_TEXT, self.on_attributes_changed,  self.ctrls['proxy'])

        self.ctrls['delay'] = wx.SpinCtrl(panel)
        self.ctrls['delay'].SetRange(0,500)
        self.ctrls['delay'].SetValue(0)

        self.ctrls['show_images'] = wx.CheckBox(panel, label='Show images after processing')

        self.ctrls['upload_images'] = wx.CheckBox(panel, label='Upload images to Commons (requires pyWikipedia)')
        if not USE_PYWIKIPEDIA:
            self.ctrls['upload_images'].Disable()

        self.ctrls['force_upload'] = wx.CheckBox(panel, label='Force upload')

        self.ctrls['convert_djvu'] = wx.CheckBox(panel, label='Convert to DjVu')
        self.ctrls['djvu_bitonal'] = wx.CheckBox(panel, label='Bitonal DjVu')

        self.ctrls['djvu_quality'] = wx.SpinCtrl(panel)
        self.ctrls['djvu_quality'].SetRange(16,50)
        self.ctrls['djvu_quality'].SetValue(48)
        
        self.ctrls['download'] = wx.CheckBox(panel, label= 'Try to download missing images')

        self.ctrls['perform_ocr'] = wx.CheckBox(panel, label= 'Perform OCR, add to DjVu')
        self.ctrls['fallback_tesseract'] = wx.CheckBox(panel, label='Use Tesseract if source page has no OCR')
        
        self.ctrls['force_tesseract'] = wx.CheckBox(panel, label= 'Perform ALL OCR locally with Tesseract')
        self.Bind( wx.EVT_CHECKBOX, self.on_attributes_changed,  self.ctrls['force_tesseract'])
        
        self.ctrls['use_saved_ocr'] = wx.CheckBox(panel, label= 'Use any available previously generated OCR')
        
        self.ctrls['dump_ocr'] = wx.CheckBox(panel, label= 'Dump readable OCR')
        self.ctrls['clean_text'] = wx.CheckBox(panel, label='Clean images before OCR')
        self.Bind( wx.EVT_CHECKBOX, self.on_attributes_changed,  self.ctrls['clean_text'])
        
        self.ctrls['clean_text_cmd'] = wx.TextCtrl(panel, style=wx.TE_MULTILINE)
        self.ctrls['clean_text_cmd'].SetFont(self.fonts['tt'])

        self.ctrls['top_directory'] = wx.SearchCtrl(panel)
        self.Bind( wx.EVT_TEXT, self.on_attributes_changed,  self.ctrls['top_directory'])
        self.Bind( wx.EVT_SEARCHCTRL_SEARCH_BTN, self.on_get_directory,  self.ctrls['top_directory'])

        self.ctrls['book_directory'] = wx.SearchCtrl(panel)
        self.Bind( wx.EVT_TEXT, self.on_attributes_changed,  self.ctrls['book_directory'])
        self.Bind( wx.EVT_SEARCHCTRL_SEARCH_BTN, self.on_get_directory,  self.ctrls['book_directory'])
        

        self.ctrls['custom_bk_dir'] = wx.CheckBox(panel, label='Custom book directory')
        self.Bind( wx.EVT_CHECKBOX, self.on_attributes_changed,  self.ctrls['custom_bk_dir'])

        self.ctrls['filename_prefix'] = wx.TextCtrl(panel)
        self.ctrls['template'] = wx.TextCtrl(panel, wx.ID_ANY,'Utopia, More, 1567')

        self.ctrls['lang'] = wx.TextCtrl(panel, wx.ID_ANY,'eng')


        self.btns['open_top_directory'] = wx.Button(panel, label="Open top dir", style=wx.BU_EXACTFIT )
        self.Bind(wx.EVT_BUTTON, self.on_open_top_directory, self.btns['open_top_directory'])
        
        self.btns['guess_page_range_from_files'] = wx.Button(panel, label="Guess from local files", style=wx.BU_EXACTFIT )
        self.Bind(wx.EVT_BUTTON, self.on_guess_pages_from_files, self.btns['guess_page_range_from_files'])

        self.btns['open_book_directory'] = wx.Button(panel, label="Open book dir", style=wx.BU_EXACTFIT )
        self.Bind(wx.EVT_BUTTON, self.on_open_book_directory, self.btns['open_book_directory'])

        self.btns['open_website'] = wx.Button(panel, label="Open website", style=wx.BU_EXACTFIT )
        self.Bind(wx.EVT_BUTTON, self.on_open_website, self.btns['open_website'])
        
    def create_buttons(self, parent):
        """
        These are the buttons that go in the "button area" below the 
        settings panel
        """
        
        #TODO fix the buttons when wx support bitmap+label buttons
        icon = wx.ArtProvider().GetBitmap(id=wx.ART_GO_FORWARD)
        self.btns['run'] =  wx.lib.buttons.GenBitmapTextButton(parent, label='Begin grab', bitmap = icon )
        self.Bind(wx.EVT_BUTTON, self.on_begin_grabbing, self.btns['run'])

        icon = wx.ArtProvider().GetBitmap(id=wx.ART_CROSS_MARK)
        self.btns['abort']  = wx.lib.buttons.GenBitmapTextButton(parent, label='Abort grab', bitmap = icon )
        self.btns['abort'].Enable(False)
        self.Bind(wx.EVT_BUTTON, self.on_abort, self.btns['abort'])

        icon = wx.ArtProvider().GetBitmap(id=wx.ART_DELETE)
        self.btns['delete_all']  = wx.lib.buttons.GenBitmapTextButton(parent, label='Delete all files', bitmap = icon )
        self.Bind(wx.EVT_BUTTON, self.on_delete_all, self.btns['delete_all'])

    def setup_settings_panel(self, parent):
        """
        Create and lay out the settings panel
        
        inputs:
        parent  : the parent panel of the settings panel
        """

        superPanel = wx.Panel(parent, wx.ID_ANY)

        panel = wx.lib.scrolledpanel.ScrolledPanel(superPanel, )

        self.create_controls(panel)
        self.create_buttons(superPanel)

        ctrlSizer = wx.GridBagSizer(vgap=3, hgap=3)

        row = 0

        heading = wx.StaticText(panel, wx.ID_ANY, 'Text properties')
        heading.SetFont(self.fonts['heading'])

        ctrlSizer.Add( heading,
                        pos=( row, 0 ),
                        span=( 1, 3 ),
                        border=10,
                        flag=wx.ALIGN_CENTER|wx.TOP )
        row += 1
        ctrlSizer.Add( wx.StaticText(panel, wx.ID_ANY, 'Text ID:'),
                        pos=( row, 0 ),
                        flag=wx.ALIGN_RIGHT|wx.ALIGN_CENTER_VERTICAL)

        ctrlSizer.Add( self.ctrls['textid'],
                        pos=( row, 1 ),
                        flag=wx.EXPAND )

        ctrlSizer.Add( self.btns['open_website'],
                        pos=( row, 2 ),
                        flag=wx.EXPAND )

        row += 1
        ctrlSizer.Add( wx.StaticText(panel, wx.ID_ANY, 'Text source:'),
                        pos=( row, 0 ),
                        flag=wx.ALIGN_RIGHT|wx.ALIGN_CENTER_VERTICAL)

        ctrlSizer.Add( self.ctrls['source'],
                        pos=( row, 1 ),
                        span=( 1, 2 ),
                        flag=wx.EXPAND )

        row += 1
        hBox = wx.BoxSizer(wx.HORIZONTAL)

        hBox.Add( self.ctrls['pg_start'],
                        proportion=1,)

        hBox.Add( wx.StaticText(panel, wx.ID_ANY, 'to'),
                        flag=wx.ALIGN_CENTER|wx.ALIGN_CENTER_VERTICAL|wx.RIGHT|wx.LEFT, border=10)

        hBox.Add( self.ctrls['pg_end'],
                        proportion=1, )

        ctrlSizer.Add( wx.StaticText(panel, wx.ID_ANY, 'Pages:'),
                        pos = (row, 0),
                        flag=wx.ALIGN_RIGHT|wx.ALIGN_CENTER_VERTICAL)

        ctrlSizer.Add(hBox, pos=(row,1), span=(1,2), flag=wx.EXPAND)
        
        row +=1
        
        ctrlSizer.Add(self.btns['guess_page_range_from_files'],
                        pos=(row,1)
                        )

        heading = wx.StaticText(panel, wx.ID_ANY, 'Network settings')
        heading.SetFont(self.fonts['heading'])

        row += 1
        ctrlSizer.Add( heading,
                        pos=( row, 0 ),
                        span=( 1, 3 ),
                        border=10,
                        flag=wx.ALIGN_CENTER|wx.TOP )
        row += 1
        ctrlSizer.Add( self.ctrls['use_proxy'],
                        pos=( row, 0 ) )


        ctrlSizer.Add( self.ctrls['proxy'],
                        pos=( row, 1 ),
                        span=(1, 2),
                        flag=wx.EXPAND )

        row += 1
        hBox = wx.BoxSizer(wx.HORIZONTAL)
        hBox.Add( self.ctrls['delay'] )

        ctrlSizer.Add( wx.StaticText(panel, wx.ID_ANY, 'Inter-fetch delay:'),
                        pos=( row, 0 ),
                        flag=wx.ALIGN_RIGHT|wx.ALIGN_CENTER_VERTICAL)

        ctrlSizer.Add(  hBox, pos=( row, 1 ), span=(1,2),
                        flag=wx.EXPAND )

        heading = wx.StaticText(panel, wx.ID_ANY, 'Local settings')
        heading.SetFont(self.fonts['heading'])

        row += 1
        ctrlSizer.Add( heading,
                        pos=( row, 0 ),
                        span=( 1, 3 ),
                        border=10,
                        flag=wx.ALIGN_CENTER|wx.TOP )
        row += 1
        ctrlSizer.Add( wx.StaticText(panel, wx.ID_ANY, 'Top directory:'),
                        pos=( row, 0 ),
                        flag=wx.ALIGN_RIGHT|wx.ALIGN_CENTER_VERTICAL)

        ctrlSizer.Add( self.ctrls['top_directory'],
                        pos = (row, 1 ),
                        flag=wx.EXPAND )

        ctrlSizer.Add( self.btns['open_top_directory'],
                        pos = (row, 2 ),
                        flag=wx.EXPAND )

        row+=1
        ctrlSizer.Add( self.ctrls['custom_bk_dir'],
                            pos=( row, 0 ),
                            span=(1,2) )

        ctrlSizer.Add( self.btns['open_book_directory'],
                        pos = (row, 2 ),
                        flag=wx.EXPAND )

        row += 1
        ctrlSizer.Add( wx.StaticText(panel, wx.ID_ANY, 'Book directory:'),
                        pos=( row, 0 ),
                        flag=wx.ALIGN_RIGHT|wx.ALIGN_CENTER_VERTICAL)

        ctrlSizer.Add( self.ctrls['book_directory'],
                        pos = (row, 1 ),
                        span = (1, 2),
                        flag=wx.EXPAND )

        row += 1
        ctrlSizer.Add( wx.StaticText(panel, wx.ID_ANY, 'Filename prefix:'),
                        pos=( row, 0 ),
                        flag=wx.ALIGN_RIGHT|wx.ALIGN_CENTER_VERTICAL)

        ctrlSizer.Add(self.ctrls['filename_prefix'],
                        pos=(row,1),
                        span=(1,2),
                        flag=wx.EXPAND)

        heading = wx.StaticText(panel, wx.ID_ANY, 'Upload settings')
        heading.SetFont(self.fonts['heading'])

        row += 1
        ctrlSizer.Add( heading,
                        pos=( row, 0 ),
                        span=( 1, 3 ),
                        border=10,
                        flag=wx.ALIGN_CENTER|wx.TOP )

        row+=1
        ctrlSizer.Add( self.ctrls['upload_images'],
                        pos=( row, 0 ),
                        span=(1,3) )

        row += 1
        text = wx.StaticText(panel, label="(To use this, you must have run pyGrabber from a teminal)")
        text.Wrap(300)
        text.SetFont(self.fonts['italic'])

        ctrlSizer.Add(text, pos=(row,0), span=(1,3), border=20, flag=wx.LEFT)

        row += 1
        ctrlSizer.Add( self.ctrls['force_upload'],
                        pos=( row, 0 ),
                        span=(1,3) )

        row += 1
        ctrlSizer.Add( wx.StaticText(panel, wx.ID_ANY, 'Template:'),
                        pos=( row, 0 ),
                        flag=wx.ALIGN_RIGHT|wx.ALIGN_CENTER_VERTICAL)

        ctrlSizer.Add(self.ctrls['template'],
                        pos=(row,1),
                        span=(1,2),
                        flag=wx.EXPAND)

        heading = wx.StaticText(panel, wx.ID_ANY, 'Display, conversion and OCR')
        heading.SetFont(self.fonts['heading'])

        row += 1
        ctrlSizer.Add( heading,
                        pos=( row, 0 ),
                        span=( 1, 3 ),
                        border=10,
                        flag=wx.ALIGN_CENTER|wx.TOP )
                        
        row+=1
        ctrlSizer.Add( self.ctrls['download'],
                        pos=( row, 0 ),
                        span=(1,3) )

        row += 1            
        ctrlSizer.Add( self.ctrls['show_images'],
                        pos=( row, 0 ),
                        span=(1,3) )

        row+=1

        hBox = wx.BoxSizer(wx.HORIZONTAL)

        hBox.Add( self.ctrls['convert_djvu'], proportion=1)
        hBox.Add( wx.StaticText(panel, label="DjVu quality (dB):"), flag=wx.ALIGN_RIGHT|wx.ALIGN_CENTER_VERTICAL )
        hBox.Add( self.ctrls['djvu_quality'], flag=wx.ALIGN_RIGHT)

        ctrlSizer.Add( hBox,
                            pos=( row, 0 ),
                            span=(1,3),
                            flag=wx.EXPAND )


        row += 1
        hBox = wx.BoxSizer(wx.HORIZONTAL)

        hBox.Add( self.ctrls['djvu_bitonal'], proportion=1)
        hBox.Add( wx.StaticText(panel, label="OCR language:"), flag=wx.ALIGN_RIGHT|wx.ALIGN_CENTER_VERTICAL )
        hBox.Add( self.ctrls['lang'], flag=wx.ALIGN_RIGHT)

        ctrlSizer.Add( hBox,
                            pos=( row, 0 ),
                            span=(1,3),
                            flag=wx.EXPAND )
                            
        row+=1
        ctrlSizer.Add( self.ctrls['perform_ocr'],
                        pos=( row, 0 ),
                        span=(1,3) )

        row += 1
        for control in ['fallback_tesseract', 'force_tesseract', 
                        'use_saved_ocr', 'dump_ocr', 'clean_text']:
            ctrlSizer.Add( self.ctrls[control],
                            pos=( row, 0 ),
                            span=(1,3) )
            row+=1

        ctrlSizer.Add( wx.StaticText(panel, wx.ID_ANY, 'Text cleaning cmd:'),
                        pos=( row, 0 ),
                        flag=wx.ALIGN_RIGHT|wx.ALIGN_CENTER_VERTICAL)

        ctrlSizer.Add(self.ctrls['clean_text_cmd'],
                        pos=(row,1),
                        span=(1,3),
                        flag=wx.EXPAND)
                        
        row += 1
        
        text = wx.StaticText(panel, label="""%fin is the input file from the source or disk
%fout is the output file that will be used to OCR
; separates individual commands
Use double quotes around arguments with spaces
Normal environment variables (eg $HOME, ~) should work
No unicode!""", style=wx.ITALIC)
        text.Wrap(300)
        text.SetFont(self.fonts['italic'])

        ctrlSizer.Add(text, pos=(row,1), span=(1,2), flag=wx.LEFT)

        ctrlSizer.AddGrowableCol(1,1)
        panel.SetSizer(ctrlSizer)        
        panel.SetupScrolling()
        
        #setup the button area sizer
        hbox = wx.BoxSizer(wx.HORIZONTAL)
        hbox.Add(self.btns['run'], proportion=1)
        hbox.Add(self.btns['abort'], proportion=1)
        hbox.Add(self.btns['delete_all'], proportion=1)

        #set up the panel holding the settings panel and the button area
        vBox = wx.BoxSizer(wx.VERTICAL)
        vBox.Add(panel, proportion=1, flag=wx.EXPAND)
        vBox.Add(hbox, flag=wx.ALIGN_BOTTOM|wx.ALIGN_CENTER)
        
        superPanel.SetSizer(vBox)   

        self.leftPanel = superPanel



    def setup_file_panel(self, parent):
        """
        Set up the file list panel
        """

        self.fileList = wx.ListCtrl(parent, wx.ID_ANY, style=wx.LC_REPORT)
        self.fileList.InsertColumn(0, 'Page', wx.LIST_FORMAT_RIGHT)
        self.fileList.InsertColumn(1, 'Filename', wx.LIST_FORMAT_RIGHT)
        self.fileList.InsertColumn(2, 'Size', wx.LIST_FORMAT_RIGHT)
        self.fileList.InsertColumn(3, 'Status', wx.EXPAND)

        self.fileList.SetColumnWidth(0, 50)
        self.fileList.SetColumnWidth(1, 100)
        self.fileList.SetColumnWidth(2, 75)
        self.fileList.SetColumnWidth(3, 500)


    def setup_progress_gauge(self, parent):
        """
        Sets up a page progress gauge
        """

        self.progress_gauge = wx.Gauge(parent)


    def setup_panes(self):
        """
        Set up all the "top-level" panels of the program
        """

        vSplitter = wx.SplitterWindow(parent=self)
        rightPanel = wx.Panel(parent=vSplitter)

        self.setup_settings_panel(parent=vSplitter)
        self.setup_file_panel(parent=rightPanel)
        self.setup_progress_gauge(parent=rightPanel)

        vBox = wx.BoxSizer(wx.VERTICAL)
        vBox.Add(self.fileList, proportion=1, flag=wx.EXPAND|wx.ALL)
        vBox.Add(self.progress_gauge, flag=wx.EXPAND|wx.ALL)
        rightPanel.SetSizer(vBox)

        vSplitter.SplitVertically(self.leftPanel, rightPanel)

        vBox = wx.BoxSizer(wx.VERTICAL)
        vBox.Add( vSplitter, proportion=1, flag=wx.EXPAND|wx.ALL)

        vSplitter.SetMinimumPaneSize(200)
        vSplitter.SetSashPosition(500)

        self.SetSizer(vBox)
        
        self.setup_statusbar()
        self.setup_clock()
        
    def setup_statusbar(self):

        self.statusBar = self.CreateStatusBar() # A Statusbar in the bottom of the window
        self.statusBar.SetFieldsCount(3)
        self.statusBar.SetStatusWidths([-1,180, 180])
        
    def setup_clock(self):
        
        self.clockTimer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.on_clock_tick, self.clockTimer)
        
    def setup_fonts(self):
        """
        Setup useful fonts, such as headings, etc
        """
        
        self.fonts = {}
        
        defaultFontSize = self.GetFont().GetPointSize()
        
        #set up the heading font
        
        self.fonts['heading'] = wx.Font(defaultFontSize+1, wx.DEFAULT, wx.NORMAL, wx.BOLD)
        
        #monospace font
        self.fonts['tt'] = wx.Font(defaultFontSize, wx.TELETYPE, wx.NORMAL, wx.NORMAL)
        
        #italic font
        self.fonts['italic'] = wx.Font(defaultFontSize-2, wx.DEFAULT, wx.ITALIC, wx.NORMAL)

    def setup_icons(self):
        """
        Find and set up the icons for the program. Update iconSizeList if you 
        add any other sized icons.
        """
        
        iconSizeList = [16, 22, 48]

        iconBundle = wx.IconBundle()

        for size in iconSizeList:
            iconBundle.AddIconFromFile(os.path.join(os.path.dirname(__file__) , 'icons', 'grabber_%d.png'%size), wx.BITMAP_TYPE_ANY)

        self.SetIcons(iconBundle)


    def populate_filelist(self):
        """
        Initially set up the entries in the filelist panel, and instantiate all
        the dictionary of Page objects
        """

        self.fileList.DeleteAllItems()
        
        index = 0

        for pageNumber in self.fileGrabber.pageList:
            
            pageItem = self.fileGrabber.pageDict[pageNumber] #get the page item out of the dict

            self.fileList.InsertStringItem(index, '')
            self.fileList.SetStringItem(index, 0, str(pageNumber))

            self.update_file_name(pageNumber)
            self.update_file_size(pageNumber)
            self.update_file_status(pageNumber)

            self.fileList.SetItemData(index, pageNumber)

            index += 1


    def update_file_status(self, number):
        pageItem = self.fileGrabber.pageDict[number]
        self.fileList.SetStringItem(pageItem.list_index, 3, pageItem.status)
      
        
    def mark_missing_page(self, number):
        pageItem = self.fileGrabber.pageDict[number]        
        self.fileList.SetItemBackgroundColour(pageItem.list_index,consts.COLOUR_ERR)


    def update_file_size(self, number):
        pageItem = self.fileGrabber.pageDict[number]
        self.fileList.SetStringItem(pageItem.list_index, 2, utils.get_size_text(pageItem.imageSize, 'kB'))
        
        
    def update_file_name(self, number):
        pageItem = self.fileGrabber.pageDict[number]
        
        filename = pageItem.get_filename()
            
        if not filename:
            filename = '?'
            
        self.fileList.SetStringItem(pageItem.list_index, 1, filename)


    def scroll_to_item(self, pageNumber):
        pageItem = self.fileGrabber.pageDict[pageNumber]
        self.fileList.EnsureVisible(pageItem.list_index)


    def update_time(self):
        
        self.statusBar.SetStatusText('Time elapsed: ' + utils.format_time(self.clockTime), number=1)
        
        completedPages = self.currentPage - self.opts['pg_start'] 
        
        if completedPages > 0:
            totalPages = self.opts['pg_end'] - self.opts['pg_start'] + 1
            
            timePerPage = self.clockTime/float(completedPages) #ratio of complete pages
            totalEstTime = timePerPage*totalPages
            totalEstRemTime = max(0, totalEstTime - self.clockTime)
            
            statusText = utils.format_time(totalEstRemTime)
        else:
            statusText = 'Unknown'
        
        self.statusBar.SetStatusText('Est. remaining: ' + statusText, number=2)


    def update_djvu_size_projection(self, pageNumber):
        """Recalculate and display the projection of the final djvu file size"""
        size = self.fileGrabber.pageDict[pageNumber].djvu_page_filesize
        self.djvu_size_list.append(size)

        avg_size_per_page = sum(self.djvu_size_list)/float(len(self.djvu_size_list))

        completed_pages = len(self.djvu_size_list)

        total_pages = self.opts['pg_end'] - self.opts['pg_start'] + 1 #

        projected_size = avg_size_per_page * total_pages

        info_string = 'Converting to DjVu. %s/%d pages at average size of %s. Projected total: %s' % (completed_pages, total_pages,
                            utils.get_size_text(avg_size_per_page), utils.get_size_text(projected_size) )

        self.statusBar.SetStatusText(info_string, number=0)

    def update_progress(self, number):

        self.update_progress_bar(number)
        self.update_title(number)

    def update_title(self, number):

        self.SetTitle( '%s - Processing: p. %d (%d/%d)' % ( 
                        NAME, 
                        number, 
                        number - self.opts['pg_start'], 
                        len(self.pageList)) )

    def update_progress_bar(self, number):

        value = number - self.opts['pg_start'] + 1
        self.progress_gauge.SetValue(value)

    def completed(self):
        """Finished grabbing. Clean up and report"""

        if self.opts['convert_djvu'] and os.path.exists(self.djvu_filename):
            djvu_size = os.path.getsize(self.djvu_filename)
            self.statusBar.SetStatusText('DjVu file completed (%d pages, %s)' % (
                len(self.djvu_size_list), utils.get_size_text(djvu_size, 'MB')  ) )

        self.cleanup_files()
        self.btns['abort'].Enable(False)
        self.btns['run'].Enable(True)

        if self.aborted:
            print '(INF) Book grab aborted.'
        elif self.valid:
            print '(INF) Completed book grab'
        else:
            print '(ERR) Aborted due to invalid parameters.'

        self.SetTitle( '%s - Completed: %d pages' % ( NAME, len(self.pageList)) )


    def display_image(self, pageNumber):
        """Display the newly-downloaded image in a separate window
        Take over the current one if it exists, else make it"""
        
        pageItem = self.fileGrabber.pageDict[pageNumber]
        
        try:
            self.imageDisplayFrame.update(pageItem)
        except AttributeError:
            self.imageDisplayFrame = ImageDisplayFrame(pageItem)


    def __init__(self):

        super(GrabberMainFrame, self).__init__(parent=None,
                                                title=NAME, size=(1000,800))
                                                
        EVT_RESULT(self,self.on_worker_event)
        
        self.Bind(wx.EVT_CLOSE, self.on_exit)
        
        self.setup_fonts()
        self.setup_icons()
        self.setup_menus()
        self.setup_panes()

        self.load_default_file()

        self.get_attributes()


class ImageDisplayFrame(wx.Frame):

    def __init__(self, pageItem):
        """Create a new window showing the image, and if available, the ocr"""
        super(ImageDisplayFrame, self).__init__(parent=None,
                                                title='Page %d' % pageItem.pageNumber,
                                                size=(600,800))

        self.sw = wx.ScrolledWindow(self)

        bmp = self.get_bmp(pageItem.filepath)

        self.staticBitmap = wx.StaticBitmap(self.sw, -1, bmp)

        vBox = wx.BoxSizer(wx.VERTICAL)
        vBox.Add( self.sw, proportion=1 ,  flag=wx.EXPAND|wx.ALL)

        self.textCtrl = wx.TextCtrl(self, wx.ID_ANY, '', style=wx.TE_MULTILINE)
        vBox.Add( self.textCtrl, proportion=1, flag=wx.EXPAND)

        if pageItem.ocr:
            self.textCtrl.SetValue(pageItem.ocr)

        self.SetSizerAndFit(vBox)

        self.sw.SetScrollbars(20, 20, 55, 40) #FIXME
        self.sw.Scroll(0,0)
        self.Centre()
        self.Show()


    def update(self, pageItem):
        """Update an existing window's image and text"""

        self.SetTitle('Page %d' % pageItem.pageNumber)

        bmp = self.get_bmp(pageItem.filepath)

        self.staticBitmap.SetBitmap(bmp)

        try:
            self.textCtrl.SetValue(pageItem.ocr)
        except AttributeError:
            pass
        except TypeError:
            self.textCtrl.SetValue('')

        self.sw.Scroll(0,0)

    def get_bmp(self, filename):

        bitmapType = self.get_type(filename)

        if bitmapType:
            img = wx.Image(filename, bitmapType)
        else:
            img = wx.Image(os.path.join(os.path.dirname(__file__) , 'icons', 'missing_500.png'), wx.BITMAP_TYPE_PNG)

        width = img.GetWidth()
        height = img.GetHeight()

        factor = 500.0 / width

        bmp = img.Rescale(width*factor, height*factor).ConvertToBitmap()

        return bmp

    def get_type(self, filename):

        root, ext = os.path.splitext(filename)

        if ext.lower() in ['.jpg', '.jpeg']:
            return wx.BITMAP_TYPE_JPEG
        elif ext.lower() in ['.png']:
            return wx.BITMAP_TYPE_PNG
        elif ext.lower() in ['.gif']:
            return wx.BITMAP_TYPE_GIF
        elif ext.lower() in ['.tif', '.tiff']:
            return wx.BITMAP_TYPE_TIF
        elif ext.lower() in ['.pnm', '.ppm', '.pbm']:
            return wx.BITMAP_TYPE_PNM
        else:
            print '\t(ERR) Unknown file type: %s. Will not display image.' % ext
            return None
            
# FILE PROCESSING CLASS ========================================================

class FileGrabber(object):
    """
    The main worker class, holding functions that would be called by the 
    GUI thread as new threads.
    
    All actual messing around with files is done in here. This class calls
    functions from Page objects to get stuff done.
    """
    
    def __init__(self, parent, opts, source):
        """Set up the job from the given parameters"""
        self._parent  = parent  #we will pass signals back to this
        self.opts = opts
        self.source = source
        
    def abort(self):
        self.aborted = True
        
    def initiate_grab(self):
        """Grab the raw image files off the web, and perform all necessary processing on them"""

        print '(INF) Beginning book grab.'
        self.aborted = False
        self.setup_files()


        for pageNumber in self.pageList:
            
            self.pageNumber = pageNumber #we need this number in a lot of functions
            self.pageItem = self.pageDict[pageNumber]
            
            self.source.set_page_number(self.pageNumber) #prepare the source with the page number

            if self.aborted: break

            print '\n(INF) Processing page %d' % self.pageNumber
            
            self.send_result((consts.RESULT_REACHED_PAGENUMBER, self.pageNumber))

            if not self.pageItem.have_file and self.opts['download']:
                self.delay_fetch()

                if self.aborted:
                    break

                success = self.fetch_page()

                if not success:
                    self.pageItem.status = "Fetch failed, skipping."
                    self.send_result((consts.RESULT_FETCH_FAILED, self.pageNumber))
                    continue #we didn't get the file, skip to next file.

            if self.aborted: break

            #process the downloaded file, if we have it
            if self.pageItem.have_file:
                self.process_page()
                self.send_result( (consts.RESULT_PAGE_COMPLETE, self.pageNumber) ) 
            else:
                self.pageItem.status = "Page missing and not downloaded"
                self.send_result( (consts.RESULT_PAGE_MISSING, self.pageNumber) ) 
                self.print_status()
                continue
        
        self.cleanup_files()
        self.send_result((consts.RESULT_ALL_PROCESSED,))
            
    def send_result(self, data):
        evt = ReturnEvent(data=data)
        wx.PostEvent(self._parent, evt)
        
    def print_status(self):
        """
        Print the page status to the console
        """
        print '\t(INF) %s' % self.pageItem.status
            
            
    def setup_pagelist(self):
        """
        Initialise the dictionary of Page items
        """
        
        self.pageList = range(self.opts['pg_start'], self.opts['pg_end']+1)

        self.pageDict = {}

        index = 0
        for pageNumber in self.pageList:
            
            pageItem = page.Page(pageNumber, index, self.opts, self.source )
            
            filename = utils.is_file_in_directory(self.opts['book_directory'], pageItem.pageNumber, type='IMAGE', format="%04d") #see if we downloaded already
            
            if filename:
                pageItem.set_filename(filename) #if so, tell the page object
  
            self.pageDict[pageNumber] = pageItem
            
            index +=1
            
        self.send_result( (consts.RESULT_PAGELIST_POPULATED, None) )


    def setup_files(self):
        """
        Set up any files we will need in the conversion processes
        """
        
        print '(INF) Setting up files\n'
        if self.opts['convert_djvu']:
            self.djvu_filename = os.path.join(self.opts['book_directory'], self.opts['filename_prefix']+'.djvu')

            if os.path.exists(self.djvu_filename):
                os.remove(self.djvu_filename)

            self.temp_djvu = os.path.join(self.opts['book_directory'], 'TEMP-DJVU-PAGE.djvu')

            self.djvu_size_list = [] # list of djvu sizes to make a guess of the final size

        if self.opts['dump_ocr']:
            self.ocr_dump_file = os.path.join(self.opts['book_directory'], 'OCR_DUMP.txt')
            open(self.ocr_dump_file, 'w').close() #create a blank file
            
            
    def cleanup_files(self):
        """
        Remove any outstanding temporary files
        """

        if self.opts['convert_djvu'] and os.path.exists(self.temp_djvu):
            os.remove(self.temp_djvu)
        

    def process_page(self):
        """
        Demand specified processing on a locally-stored image. This processing
        is actually carried out by the Page item
        
        Return signals when we want to inform the GUI of progress
        """
        
        ocr_performed = False

        if self.opts['perform_ocr']: #if we want OCR 

            ocr_performed = True
            ocr_text = self.pageItem.get_ocr_text(self.opts['use_saved_ocr'])
            self.send_result( (consts.RESULT_OCR_COMPLETE, self.pageNumber) )
            self.print_status()
            
        if self.aborted: return

        if self.opts['convert_djvu']:
            success = self.pageItem.convert_to_djvu(self.temp_djvu)
            self.print_status()
            # this can fail if djvulibre is not installed
            if success:
                self.send_result( (consts.RESULT_DJVU_COMPLETE, self.pageNumber, self.pageItem.djvu_page_filesize) )
            else:
                return
            
            
            
            
        if self.aborted: return #proceed if not aborted or failed

        if self.opts['perform_ocr'] and self.opts['convert_djvu']:
            self.pageItem.add_ocr_to_djvu(self.temp_djvu)
            self.send_result( (consts.RESULT_DJVU_OCRD, self.pageNumber) )
            self.print_status()
            
        if self.aborted: return

        if ocr_performed and self.opts['dump_ocr']:
            self.pageItem.dump_ocr(self.ocr_dump_file)
            print '\t(INF) OCR dumped to file.'
            
        if self.aborted: return

        if self.opts['convert_djvu']:
            self.pageItem.append_to_main_djvu(self.temp_djvu, self.djvu_filename)
            self.send_result( (consts.RESULT_DJVU_APPENDED, self.pageNumber) )
            self.print_status()
            
        if self.aborted: return

        if self.opts['upload_images']:
            self.pageItem.upload_image()
            self.print_status()

    def delay_fetch(self):
        """
        Delay fetch by a given time in case a source implements throttling.
        Signal the GUI and check for aborts every second.
        """

        # delay the grab if needed
        if self.opts['delay'] > 0:
            
            for i in range(self.opts['delay']): #1 sec increments
            
                if self.aborted: break
            
                timeLeft = self.opts['delay'] - i
                self.pageItem.status = 'Waiting to begin file fetch. Delayed by %d seconds.' % timeLeft
                self.send_result((consts.RESULT_WAITING, self.pageNumber))
                
                time.sleep(1) 
                
        else:
            self.pageItem.status = 'Waiting to begin file fetch.'
            self.send_result((consts.RESULT_WAITING, self.pageNumber))
        
            
    def fetch_page(self):
        """
        Get relevant URLs and request a file fetch from the page object.
        
        Returns: success: boolean - did we succeed in getting a valid file?
        """
        
        # get the page URL, if any, from which we can load the image URL
        self.pageItem.get_page_url()

        if self.pageItem.page_url: #send a signal if there is a url to read
            self.print_status()
            self.send_result((consts.RESULT_FOUND_PAGE_URL, self.pageNumber))
        else:
            print "\t(INF) We don't need to load an HTML page to find the image URL."
        
        # find the image url
        self.pageItem.get_image_url()
        self.print_status()
        
        self.send_result((consts.RESULT_FOUND_IMAGE_URL, self.pageNumber))
        
        attempt = 0
        while attempt < consts.DOWNLOAD_ATTEMPTS:
            
            if self.aborted:
                self.pageItem.clear_image_file()#clear up any pointless corrupt files
                return False
            
            self.pageItem.get_image_file()

            if self.pageItem.imageSize > 1000:
                print '\t(INF) Got image file (%s).' % utils.get_size_text(self.pageItem.imageSize, 'kB')
                break
            else:
                print '\t(ERR) Possibly corrupt image, retrying (%s).' % utils.get_size_text(self.pageItem.imageSize, 'B')
                attempt += 1
                

        self.pageItem.save_image()
        self.send_result((consts.RESULT_SAVED_FILE, self.pageNumber))
        self.print_status()

        return True


# THREAD HANDLING ==============================================================
#http://wiki.wxpython.org/LongRunningTasks

EVT_RESULT_ID = wx.NewId()

def EVT_RESULT(win, func):
    """Define Result Event."""
    win.Connect(-1, -1, EVT_RESULT_ID, func)

class ReturnEvent(wx.PyEvent):
    """Simple event to carry arbitrary result data."""
    def __init__(self, data):
        """Init Result Event."""
        wx.PyEvent.__init__(self)
        self.SetEventType(EVT_RESULT_ID)
        self.data = data
        
        

# MAIN LOOP FUNCTION AND PROGRAM LAUNCH ========================================

def main():
    """ interpret any arguments, and launch """

    if not utils.check_deps(['c44', 'djvm', 'cjb2', 'tesseract', 'convert']):
        return

    app = wx.App(False)  # Create a new app, don't redirect stdout/stderr to a window. #TODO fix this
    mainFrame = GrabberMainFrame()
    mainFrame.Show()
    app.MainLoop()


if __name__ == "__main__":
    main()
