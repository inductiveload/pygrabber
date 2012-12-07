#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Part of pyGrabber

Routines for cleaning HTML text, removing tags, etc.
"""

import re
import htmlentitydefs


def clean_html(text, newline_at_br=True):

    text = strip_br(text, newline_at_br)

    text = strip_html(text)
    text = clean_whitespace(text)

    return text

def strip_br(text, newline_at_br=True):

    if newline_at_br:
        repl_text = '\n'
    else:
        repl_text = ''

    text = re.sub(r'<\s*[Bb][Rr]\s*/?>', repl_text, text)
    return text


def clean_whitespace(text):
    text = re.sub(r'^[\s]*', '', text) #whitespace at start of lines

    text = re.sub(r'^[ \t]*', '', text) #leading whitespace
    text = re.sub(r'[ \t]*$', '', text) #trailing whitespace

    return text

# http://effbot.org/zone/re-sub.htm#strip-html
def strip_html(text):
    def fixup(m):
        text = m.group(0)
        if text[:1] == "<":
            return "" # ignore tags
        if text[:2] == "&#":
            try:
                if text[:3] == "&#x":
                    return unichr(int(text[3:-1], 16))
                else:
                    return unichr(int(text[2:-1]))
            except ValueError:
                pass
        elif text[:1] == "&":
            import htmlentitydefs
            entity = htmlentitydefs.entitydefs.get(text[1:-1])
            if entity:
                if entity[:2] == "&#":
                    try:
                        return unichr(int(entity[2:-1]))
                    except ValueError:
                        pass
                else:
                    return unicode(entity, "utf-8")
        return text # leave as is
    return re.sub("(?s)<[^>]*>|&#?\w+;", fixup, text)


