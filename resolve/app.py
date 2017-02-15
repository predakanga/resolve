#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division, print_function, absolute_import

import argparse
import sys
import logging
import re
import os
from pathlib import Path
from shutil import copy, copymode
from tempfile import mkstemp
from socket import gethostbyname

from resolve import __version__

__author__ = "Predatory Kangaroo"
__copyright__ = "Predatory Kangaroo"
__license__ = "MIT"

_logger = logging.getLogger(__name__)

BACKUP_EXT = ".bk"


def parse_args(args):
    """Parse command line parameters

    Args:
      args ([str]): command line parameters as list of strings

    Returns:
      :obj:`argparse.Namespace`: command line parameters namespace
    """
    parser = argparse.ArgumentParser(
        description="Resolves domain references in a config file",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument(dest="input", help="input file", nargs="+", type=Path)
    parser.add_argument(
        '--version',
        action='version',
        version='resolve {ver}'.format(ver=__version__))
    parser.add_argument(
        '-v',
        '--verbose',
        dest="loglevel",
        help="set loglevel to INFO",
        action='store_const',
        const=logging.INFO)
    parser.add_argument(
        '-vv',
        '--very-verbose',
        dest="loglevel",
        help="set loglevel to DEBUG",
        action='store_const',
        const=logging.DEBUG)
    parser.add_argument(
        '-r',
        '--recursive',
        dest="recursive",
        help="operate on directories recursively",
        action='store_true')
    parser.add_argument(
        '-c',
        '--comment-string',
        dest="comment",
        help="set the comment character or string to search for",
        default="#")
    parser.add_argument(
        '-b',
        '--backup',
        dest="backup",
        help="create backups",
        action='store_true')

    return parser.parse_args(args)


def setup_logging(loglevel):
    """Setup basic logging

    Args:
      loglevel (int): minimum loglevel for emitting messages
    """
    logformat = "[%(asctime)s] %(levelname)s:%(name)s:%(message)s"
    logging.basicConfig(level=loglevel, stream=sys.stdout,
                        format=logformat, datefmt="%Y-%m-%d %H:%M:%S")


# N.B. All the str casts in the below code are due to shutil not supporting path-like objects
def _resolve(path: Path, recursive: bool, backup: bool, trigger_re, replace_re):
    if not path.exists():
        _logger.error("Input file '%s' does not exist", path)
        return False
    if path.is_dir():
        if not recursive:
            _logger.error("Input file '%s' is a directory")
            return False
        for child in path.iterdir():
            if not _resolve(child, recursive, backup, trigger_re, replace_re):
                return False
    else:
        # TODO: Should we exclude files ending with BACKUP_EXT?
        # Create a backup if necessary
        if backup:
            _logger.info("Backing up %s", path)
            copy(str(path), str(path.with_name(path.name + BACKUP_EXT)))

        # Create a temp file to work in
        # N.B. Using mkstemp instead of NamedTemporaryFile as that only supports bytes-like output
        out_no, out_fn = mkstemp()
        _logger.debug("Outputting to %s", out_fn)
        # Ensure that the modes are correct
        copymode(str(path.resolve()), out_fn)
        with os.fdopen(out_no, 'w') as out:
            with path.open() as input:
                line_no = 0
                for line in input:
                    line_no += 1
                    match = trigger_re.search(line)
                    if match:
                        # Make sure there's only one IP on the line
                        ip_count = replace_re.findall(line)
                        if len(ip_count) != 1:
                            _logger.warning("Unable to resolve domain on line %d of %s. Found %d IP addresses, expected 1", line_no, path, len(ip_count))
                        else:
                            host = match.group(1)
                            try:
                                ip = gethostbyname(host)
                                _logger.debug("Resolved %s to %s on line %d of %s.", host, ip, line_no, path)

                                line = replace_re.sub(ip, line)
                            except:
                                _logger.exception("Failed to resolve %s on line %d of %s.", host, line_no, path)
                    out.write(line)

        # Replace the original file with the temp file, eventually
        os.replace(out_fn, str(path.resolve()))
        _logger.info("Processed %s", path)

        pass

    return True


def main(args):
    """Main entry point allowing external calls

    Args:
      args ([str]): command line parameter list
    """
    args = parse_args(args)
    setup_logging(args.loglevel)
    # Using a simplified IP regex because why not?
    trigger_re = re.compile(re.escape(args.comment) + r'\s*resolve:\s*(\S+)$')
    replace_re = re.compile(r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})')
    for path in args.input:
        assert(isinstance(path, Path))
        _logger.info("Resolving references in %s", str(path))
        if not _resolve(path, args.recursive, args.backup, trigger_re, replace_re):
            break


def run():
    """Entry point for console_scripts
    """
    main(sys.argv[1:])


if __name__ == "__main__":
    run()
