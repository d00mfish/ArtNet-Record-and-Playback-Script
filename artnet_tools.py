#!/usr/bin/env python
import re
import sys
import threading
import time

from datetime import datetime
from os import remove, SEEK_CUR, SEEK_END, walk, rename
from pathlib import Path
from random import shuffle
from tempfile import gettempdir

# local imports
import helpfunctions as h
from smartnet import Smartnet, SmartNetServer


class ArtNetRecord:

    # Global variables

    FILENAME = "Art-Rec_" + datetime.now().strftime("%Y-%m-%d_%H%M%S")
    TMP_PATH = Path(gettempdir(), FILENAME + '.txt')

    TIMEOUT = 5 *10**9  # 5 Seconds
    MIN_LEN = 10 *10**9  # Minimum n s to save

    RunCallback = True # Stop Thread Flag
    length = 0  # Records length
    i = 0  # Debug interator

    def __init__(self, universes: list, rec_dur: int, path: Path, compress = False, debug: int = 0):
        """Initializes Recording Class.

        Args:
            universes (list): List of universes to record
            rec_dur (int): Duration of recording in minutes, 0 is infinite
        """

        # Instance variables
        self.compress = compress
        self.universes = universes
        self.debug = debug

        self.rec_time = rec_dur * 10**9 if rec_dur > 0 else 86.400*10**9  # 1 day if 0

        # Smartnet instance
        self.a = SmartNetServer()

        # Test if output is a empty, adirectory or a file
        if path == Path():
            self.final_path = Path(Path.cwd(), self.FILENAME + '.artrec' if self.compress else self.FILENAME +  '.rawrec')

        elif path.name == '':
            self.final_path = Path(path, self.FILENAME + ".artrec" if self.compress else self.FILENAME +  ".rawrec")

        elif path.name != '':
            self.final_path = path

        print(h.bcolors.OKBLUE + "----------record----------\nUniverses: {}\nDuration: {}s\nOutput: '{}' ".format(self.universes,
                                                                                                                  round(self.rec_time*10**-9), self.final_path) + h.bcolors.ENDC)

    def __callback(self, data, universe: int):
        """Callback for every Packet

        Args:
            data (bytearray): Package data to store
            universe (int): Universe
        """
        if self.RunCallback:
            # write line: "int(time since last packet) int(universe) bytearray[data]"
            delay = time.time_ns() - self.last

            try:
                self.writer.write(str(delay) + " " +
                                str(universe) + " " + str(data) + "\n")

            except Exception as e:
                print(h.bcolors.FAIL +
                    "Error writing to file: {}".format(e) + h.bcolors.ENDC)

            self.last = time.time_ns()

            if self.debug:
                self.i += 1
                # every n-th packet print info
                if self.i == self.debug:
                    print('U: {}, Size: {}, Delay: {}ms\n'.format(
                        universe, len(data), round(delay * 10**-6, 6)))
                    self.i = 0

    def record(self):
        """Opens a temp file and writes the data to it.
        When recording is finished or timeouted, the file is zipped and moved to the final path


        Raises:
            TimeoutError: When no data is received for the given time
        """

        print("Recording started...\nPress Ctrl+C to stop prematurely.")

        with open(self.TMP_PATH, 'w') as self.writer:
            # Timing variables
            self.last = time.time_ns()
            self.start = self.last

            # Register universe listeners on other threads
            self.a.register_multiple_listeners(
                self.universes, callback_function=self.__callback)

            try:
                # Test for elapsed time
                while time.time_ns() - self.start < self.rec_time*10**9:
                    self.length = time.time_ns() - self.start # Length in ns

                    # Refresh console writeout time
                    sys.stdout.write("\r%.1fs" % (self.length*10**-9))
                    sys.stdout.flush()

                    # Timeout if no data is received for the given time
                    if time.time_ns() - self.last > self.TIMEOUT:
                        raise TimeoutError
                    time.sleep(0.2)

            # User abort
            except KeyboardInterrupt:
                self.debug = False
                print("\n\n" + h.bcolors.WARNING +
                      "TERMINATED BY USER, Saving Data...\n" + h.bcolors.ENDC)

            # Timeout abort
            except TimeoutError:
                print("\n\n" + h.bcolors.FAIL +
                      "No data received for {} seconds. Stopped recording.".format(round(self.TIMEOUT*10**-9)) + h.bcolors.ENDC)

            # Close properly
            self.RunCallback = False
            del self.a

        # Check for minimal lenght
        if self.length > self.MIN_LEN:

            # Add length and universes to end of file
            with open(self.TMP_PATH, 'a') as self.writer:
                self.writer.write('!' + ','.join(str(u)
                                  for u in self.universes) + " " + str(round(self.length*10**-6)) + "\n")

            if self.compress:
                # Compress file to final location
                with open(self.TMP_PATH, 'rb') as tmp:
                    h.write_file(tmp.read(), self.final_path)
                remove(self.TMP_PATH)
            
            else:
                # Move file to final location
                rename(self.TMP_PATH, self.final_path)

        else:
            print(h.bcolors.FAIL + "File must be longer than {} seconds, NOT SAVING.".format(
                int(self.MIN_LEN*10**-9)) + h.bcolors.ENDC)


class ArtNetPlayback:

    halt = False  # Stop-thread flag
    i = 0  # Debug counter

    # Regex pattern for parsing a line
    pattern = re.compile(
        r"(?P<delay>[0-9]+)\s(?P<universe>[0-9]+)\s\[(?P<data>[0-9, ]*)\]")

    def __init__(self, target_ip: str, filepath: Path, ShuffleLoop=False, debug: int = 0):
        """Initializes Replay function.

        Args:
        target_ip (str): IP of the ArtNet Server
        filepath (Path): Path to the file or directory to replay
        debug (int): n-th packet to print debug info
        """

        # Validate IP
        ip_regex = re.compile(
            r"^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$")
        if not ip_regex.match(target_ip):
            raise ValueError("Invalid IP address")
        self.target_ip = target_ip

        # Create List of Filenames + directory variable
        if filepath.name.endswith(('.artrec', '.rawrec')):
            self.dir = filepath.parent
            self.playlist = [filepath.name]

        elif filepath.is_dir():
            self.playlist = self.get_artrec_files(filepath)
            self.dir = filepath

        else:
            print(h.bcolors.FAIL + "Can't handle the path input." + h.bcolors.ENDC)

        # Instance variables
        self.debug = debug
        self.shuffle_loop = ShuffleLoop

        if self.debug:
            print(h.bcolors.OKBLUE + "----------playback----------\nAdress: {}\nFile: '{}' ".format(
                self.target_ip, self.dir) + h.bcolors.ENDC)

    def get_artrec_files(self, path):

        # Get all files in current directory
        files = next(walk(path), (None, None, []))[2]

        if files != []:
            # Filter out all non-artrec files
            files = [f for f in files if f.endswith(('.artrec', '.rawrec'))]

        return files

    def playback_thread(self, textfile):

        self.last = time.time_ns()

        def send(m):
            """Send data over ArtNet through socket"""
            # prepare data
            data = bytearray(list(map(int, m.group('data').split(','))))

            # send data and set last timestamp
            self.a.send_data(data, int(m.group('universe')))
            self.last = time.time_ns()

        while textfile:
            # Get new line
            line = textfile.readline()

            # Break at footer
            if line[0] == "!" or self.halt:
                break

            # Apply regex pattern
            match = self.pattern.match(line)

            # Calculate time before packets must be sent
            time_left = time.time_ns() - self.last - int(match.group('delay'))

            # Wait, if time left before due is more than 0.5ms
            if (time_left < -0.5 * 10**6):
                time.sleep(abs(time_left)*10**-9)

            send(match)

            # Debug info every n-th packet
            if self.debug:
                self.i += 1

                if self.i == self.debug:
                    print("U: {}, Timing: {}ms".format(match.group(
                        'universe'), round(time_left * 10**-6, 6)))
                    self.i = 0

        # Close textfile after break
        textfile.close()

    def start_playback(self):
        """Starts the playback thread"""
        try:

            if self.playlist != []:

                for i, artrec in enumerate(self.playlist):

                    print(
                        h.bcolors.OKGREEN + f"Replaying...{i+1}/{len(self.playlist)}" + h.bcolors.ENDC)

                    # Create path of file
                    path = Path(self.dir, artrec)

                    # Get start time
                    self.start = time.time_ns()

                    # Get file info
                    self.duration, self.universes = self.get_footer_info(path)

                    # Create Smartnet instance
                    self.a = Smartnet(self.target_ip, self.universes, 40)

                    # Open file
                    # Unzips if file is zipped
                    if path.suffix == '.artrec':
                        textfile = open(h.unzip_file(path), 'r')
                    elif path.suffix == '.rawrec':
                        textfile = open(path, 'r')

                    # Start thread
                    self.worker = threading.Thread(
                        target=self.playback_thread, args=(textfile,))
                    self.worker.start()

                    # Print remaining time
                    while self.worker.is_alive():
                        remaining = round(
                            ((self.duration * 10**6) - (time.time_ns() - self.start)) * 10**-9, 1)
                        # refresh remaining time
                        if remaining > 0:
                            sys.stdout.write("\r%.1fs" % remaining)
                            sys.stdout.flush()
                        else:
                            sys.stdout.write("\rFinished!")
                            sys.stdout.flush()
                        time.sleep(0.2)

                    print('\n')

                if self.shuffle_loop:
                    print(h.bcolors.PINK +
                          "Shuffled Playlist. Repeating..." + h.bcolors.ENDC)
                    shuffle(self.playlist)
                    self.start_playback()

            else:
                print(h.bcolors.FAIL +
                      "No files found in directory." + h.bcolors.ENDC)

        # User abort
        except KeyboardInterrupt:
            self.close()
            print("\n\nTERMINATED BY USER, Stopping playback.\n")

    def close(self):
        """Closes the playback thread and the ArtNet instance"""
        self.halt = True
        self.worker.join()
        self.a.close()

    def get_footer_info(self, filepath):
        """Opens the file in binary to look for last line (faster)

        Returns:
            tuple(int[duration in ms], list[int(universes)])
        """
        # Unzips if file is zipped
        if filepath.suffix == '.artrec':
            tf = open(h.unzip_file(filepath), 'rb')
        elif filepath.suffix == '.rawrec':
            tf = open(filepath, 'rb')

        try:
            tf.seek(-2, SEEK_END)
            while tf.read(1) != b'\n':
                tf.seek(-2, SEEK_CUR)

        # catch OSError in case of a one line file
        except OSError:
            tf.seek(0)

        last_line_info = tf.readline().decode().replace('!', '').split(' ')

        tf.close()

        return int(last_line_info[1]), list(map(int, last_line_info[0].split(',')))
