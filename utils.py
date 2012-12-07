#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
General utilities for pyGrabber. Functions that are not specifically 
to do with image grabbing or processing.

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

import os
import glob
import wx
import subprocess

def get_size_text(size, unit='MB'):
    """
    Get a readable reprentation of the filesize (and deal with unknown).
    
    
    
    size    : size in bytes
    unit    : size unit: b, B, kB, MB
    
    """

    if not size:
        return '?'
    elif unit== 'b':
        return '%d b' % (size *8)
    elif unit=='kB' or size < 1024*1024:
        return '%d kB' % (size // 1024)
    elif unit=='MB' or size < 1024*1024*1024:
        return '%d MB' % (size // (1024*1024))
    else:
        return '%d B' % size


def get_file_manager_cmd():
     """Get the file manager open command for the current os.

     http://wxpython-users.1045709.n5.nabble.com/GetOpenCommand-and-problems-under-KDE-td2269560.html

     @return: string, holding the command to use
     """
     if wx.Platform == '__WXMAC__':
         return 'open'
     elif wx.Platform == '__WXMSW__':
         return 'explorer'
     else:
         # Check for common linux filemanagers returning first one found
         #          Gnome/ubuntu KDE/kubuntu  xubuntu, lxde
         for cmd in ('nautilus', 'konqueror', 'Thunar', 'pcmanfm'):
             result = os.system("which %s > /dev/null" % cmd)
             if result == 0:
                 return cmd
         else:
             return 'nautilus'
             
             
def which(program):
    """
    Return the path of a program, or None if it is not found
    
    #http://stackoverflow.com/questions/377017/test-if-executable-exists-in-python/377028#377028
    
    program     : name or path of a program to check for
    """

    def is_exe(fpath):
        return os.path.exists(fpath) and os.access(fpath, os.X_OK)

    fpath, fname = os.path.split(program)
    if fpath:
        if is_exe(program):
            return program
    else:
        for path in os.environ["PATH"].split(os.pathsep):
            exe_file = os.path.join(path, program)
            if is_exe(exe_file):
                return exe_file

    return None
             
             
def check_deps(command_list):
    """
    Check a list of dependency programs. If any are not found, return False,
    else return True.
    
    Should work on *nixes, but always returns true on Windows.
    
    command_list :  list of paths or programs to search for
    """
    
    if wx.Platform == '__WXMSW__':
        print("(INF) Cannot check dependecies on Windows, let's hope everything is installed!")
        return True
    
    else: #this should work on *NIXes
    
        invalid_list = []
        
        for command in command_list:
            
            if not which(command):
                print("(ERR) Command '%s' is missing" % command)
                invalid_list.append(command)
                
        return (len(invalid_list) == 0)
        

def run_cmd(cmd, show_cmd=False):
    """
    Run a given command, apply niceness if running on *nixes
    
    cmd         : list of command line parts eg. ['convert', 'file1.jp2', 'file2.png']
    show_cmd    : print the command to console before executing
    """
    
    if len(cmd) < 1:
        return
    
    if wx.Platform == '__WXMSW__':
        if show_cmd:
            print cmd
            
        subprocess.call(cmd)
        
    else: #for *nixes:
        nice_cmd = ['nice', '-n', consts.NICENESS]
        nice_cmd.extend(cmd)

        if show_cmd:
            print "Nice cmd:",  nice_cmd

        subprocess.call(nice_cmd)
        
def format_time(seconds):
    """
    Return a time in seconds in the format HH:MM:SS
    """
    
    m, s = divmod(seconds, 60)
    
    h, m = divmod(m, 60)
    
    return "%02d:%02d:%02d" % (h,m,s)
    

def is_file_in_directory(directory, imageNumber,  type, format='%04d'):
    """
    Returns the first file with a number in it matching the requested format
    
    directory  : directroy to search in
    fileNumber : the number in the filename
    type       : category of file
    format     : the number format in %-style
    
    REturns True if the file does not exist in that directory, False if not, or the directory doesn't exist
    """
    
    if not os.path.isdir(directory):
        return False

    if type == 'IMAGE':
        extList = ['.jpg', '.jpeg', '.png', '.gif', '.tif', '.tiff', '.jp2', '.ppm', '.pgm', '.pnm', '.pbm']
    else:
        print "(ERR) Unknown filetype category: %s" % type
        return False
        
        
    matching_files = glob.glob(os.path.join(directory, ('*%s*'% format) % imageNumber) + '.*')

    existing_file = None
    for matching_file in matching_files:

        root, ext = os.path.splitext(matching_file)

        if ext.lower() in extList:
            existing_file = matching_file   
            break     
        
    return existing_file
        
