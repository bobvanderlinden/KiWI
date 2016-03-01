import locale
from dialog import Dialog

locale.setlocale(locale.LC_ALL, '')

import sys, os
import glob
import re
import subprocess

import logging
import logging.handlers
logger = logging.getLogger()

from .interface import *
from .mount import *


class WindowsInstallApp(object):
    def __init__(self):
        self.d = Dialog(dialog='dialog')
        self.d.set_background_title('KiWI: Killer Windows Installer')

        networking_items = [
            ('Connect to Wireless Network', self.launch_wicd)]

        networking_submenu = Menu(self.d, networking_items, 'Network Configuration')

        self.source_dir = '/mnt/source'

        source_items = [
            ('Block Device (USB, CD/DVD, etc.)', None),
            ('Network (NFS)', MenuItem(self.prepare_source)),
        ]

        source_submenu = Menu(self.d, source_items, 'Select Installation Source')

        partitioning_items = [
            ('Auto-Prepare (erases the ENTIRE storage drive)', self.auto_partition),
        ]

        partitioning_submenu = Menu(self.d, partitioning_items, title='Partition Drives')

        main_menu_items = [
            ('Configure Networking', networking_submenu),
            ('Prepare Storage Device', partitioning_submenu),
            ('Select Installation Source', MenuItem(self.select_sources)),
            ('Install OS', MenuItem(self.install_os)),
            #('Install Bootloader', self.install_bootloader),
        ]

        self.running = True
        main_menu = Menu(self.d, main_menu_items, title='Main Menu')
        while self.running: main_menu.run(ret=self.exit())

    def launch_wicd(self):
        subprocess.call('wicd-curses', shell=True)

    def detect_blockdevs(self):
        def blockdev_size(device):
            nr_sectors = open(device+'/size').read().rstrip('\n')
            sect_size = open(device+'/queue/hw_sector_size').read().rstrip('\n')

            return (float(nr_sectors)*float(sect_size))/(1024.0*1024.0*1024.0)

        dev_pattern = ['sd.*', 'mmcblk*']

        devices = []
        for device in glob.glob('/sys/block/*'):
            for pattern in dev_pattern:
                if re.compile(pattern).match(os.path.basename(device)):
                    devices.append(tuple([device, blockdev_size(device)]))

        self.d.msgbox('Detected Devices:\n\n' + '\n'.join(
            [' '.join([path, '%.2f GB' % size]) for path, size in devices]),
            width=40, height=10)

        self.devices = devices

    def auto_partition(self):
        self.detect_blockdevs()

        entries = [tuple([path, '-']) for path, _ in self.devices]
        code, tag = self.d.menu('Choose an installation drive', choices=entries)

        if code == self.d.OK: self.drive = tag

        logging.info('Beginning installation on drive {}'.format(self.drive))

    def format_partitions(self):
        if not self.drive:
            logging.error('Cannot format with unpartitioned drive')
            return

        p = subprocess.call('mkfs.ntfs -F {}' + self.drive)

    def select_sources(self):
        code, path = self.d.inputbox('Input the path to your WIM', width=80)
        if code == self.d.OK and path:
            self.source = path
            logging.info('Set installation source to {}'.format(path))

    def mount_partitions(boot, os):
        pass

    def install_os(self):
        pass
        if not self.boot_part or not self.os_part \
        or not self.source or not self.imageid:
            return

        confirmation = self.d.yesno('Install drive: {}\nInstallation Source: {}'.format(
            self.drive, self.source) + '\n\nContinue installation?', width=40, height=15)

        if confirmation == 'ok': self.extract_wim(self.source, self.imageid, self.os_part)

    def extract_wim(self, wimfile, imageid, target):
        r, w = os.pipe()
        process = subprocess.Popen(['sudo', '/usr/bin/wimlib-imagex', 'apply', wimfile, imageid, target], stdout=w, stderr=subprocess.PIPE)

        #self.d.progressbox(fd=r, text='Applying WIM to target...', width=80, height=20)

        filp = os.fdopen(r)

        while True:
            line = filp.readline()
            logging.info('Ignoring line: {}'.format(line))
            if 'Creating files' in line: break

        for stage in ['Creating files', 'Extracting file data', 'Applying metadata to files']:
            self.d.gauge_start(text=stage, width=80, percent=0)

            while(True):
                line = filp.readline()
                logging.info(line)
                if stage not in line: continue
                pct = re.search(r'\d+%', line).group(0)[:-1]

                if pct:
                    self.d.gauge_update(int(pct))
                    logging.info('{}: {}%'.format(stage, pct))
                    if pct == '100': break


        exit_code = self.d.gauge_stop()
        process.communicate()

    def install_bootloader(self):
        pass

    def exit(self):
        self.running = False

def handle_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return

    logger.critical('Unhandled exception', exc_info=(exc_type, exc_value, exc_traceback))

import sys
sys.excepthook = handle_exception

if __name__ == '__main__':
    logger.setLevel(logging.INFO)

    fh = logging.FileHandler('/tmp/kiwi-install.log')
    logger.addHandler(fh)

    app = WindowsInstallApp()
