#!/bin/sh

echo "Enter version number:"
read VERSION

sed -i "s/VERSION *= *'[^']*'/VERSION = '"$VERSION"'/" pygrabber.py

bzr push bzr+ssh://inductiveload@pygrabber.bzr.sourceforge.net/bzrroot/pygrabber

ARCHIVEDIR=pygrabber-$VERSION

bzr export $ARCHIVEDIR

tar -zcf dists/$ARCHIVEDIR.tar.gz $ARCHIVEDIR

cp README dists/README

rm -rf $ARCHIVEDIR

firefox https://sourceforge.net/projects/pygrabber/files/
