#!/usr/bin/python

import threading
import helpfunctions as h
import re
import time
import sys

from datetime import datetime
from os import remove, SEEK_CUR, SEEK_END
from pathlib import Path
from tempfile import gettempdir

#local imports
from smartnet import Smartnet, SmartNetServer


class ArtNetRecord:

    # Global variables

    FILENAME = "Art-Rec_" + datetime.now().strftime("%Y-%m-%d_%H%M%S")
    TMP_PATH = Path(gettempdir(), FILENAME + '.txt')

    timeout = 5  # Seconds
    min_len = 10  # Minimum n s to save

    length = 0  # Records length
    i = 0  # Debug interator

    def __init__(self, universes: list, rec_dur: int, path: Path, debug: int = 0):
        """Initializes Recording Class.

        Args:
            universes (list): List of universes to record
            rec_dur (int): Duration of recording in minutes, 0 is infinite
        """

        # Instance variables
        self.universes = universes
        self.debug = debug
        self.rec_time = rec_dur * 60 if rec_dur > 0 else 86.400  # 1 day if 0

        # Smartnet instance
        self.a = SmartNetServer()

        # Test if output is a empty, adirectory or a file
        if path == Path():
            self.final_path = Path(Path.cwd(), self.FILENAME + '.artrec')

        elif path.name == '':
            self.final_path = Path(path, self.FILENAME + ".artrec")

        elif path.name != '':
            self.final_path = path

        print( h.bcolors.OKBLUE +"----------record----------\nUniverses: {}\nDuration: {}s\nOutput: '{}' ".format(self.universes,
              self.rec_time, self.final_path) + h.bcolors.ENDC)

    def __callback(self, data, universe: int):
        """Callback for every Packet

        Args:
            data (bytearray): Package data to store
            universe (int): Universe
        """
        # write line: "int(time since last packet) int(universe) bytearray[data]"
        delay = time.time_ns() - self.last
        
        try:
            self.writer.write(str(delay) + " " + str(universe) + " " + str(data) + "\n")
        
        except Exception as e:
            print(h.bcolors.FAIL + "Error writing to file: {}".format(e) + h.bcolors.ENDC)

        self.last = time.time_ns()

        if self.debug:
            self.i += 1
            # every n-th packet print info
            if self.i == self.debug:
                print('U: {}, Size: {}, Delay: {}ms\n'.format(universe, len(data), round(delay * 10**-6, 6)))
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
            self.start = time.time()

            # Register universe listeners on other threads
            self.a.register_multiple_listeners(self.universes, callback_function=self.__callback)

            try:
                # Test for elapsed time
                while time.time() - self.start < self.rec_time:
                    self.length = round(time.time() - self.start)

                    # Refresh console writeout time
                    sys.stdout.write("\r%is" % self.length)
                    sys.stdout.flush()

                    # Timeout if no data is received for the given time
                    if time.time_ns() - self.last > self.timeout * 10**9:
                        raise TimeoutError

                    time.sleep(1)

            # User abort
            except KeyboardInterrupt:
                self.debug = False
                print("\n\n" + h.bcolors.WARNING + "TERMINATED BY USER, Saving Data...\n" + h.bcolors.ENDC)

            # Timeout abort
            except TimeoutError:
                print("\n\n" + h.bcolors.FAIL + "No data received for {} seconds. Stopped recording.".format(self.timeout) + h.bcolors.ENDC)

            # Close properly
            del self.a

        # Check for minimal lenght
        if self.length > self.min_len:

            # Add length and universes to end of file
            with open(self.TMP_PATH, 'a') as self.writer:
                self.writer.write('!' + ','.join(str(u)
                                  for u in self.universes) + " " + str(int(self.length * 1000)) + "\n")

            # Compress file to final location
            with open(self.TMP_PATH, 'rb') as tmp:
                h.write_file(tmp.read(), self.final_path)

        else:
            print(h.bcolors.FAIL + "File must be longer than {} seconds, NOT SAVING.".format(self.min_len) + h.bcolors.ENDC)

        # Remove temp file
        remove(self.TMP_PATH)


class ArtNetPlayback:

    halt = False  # Stop-thread flag
    i = 0  # Debug counter

    # Regex pattern for parsing a line
    pattern = re.compile(r"(?P<delay>[0-9]+)\s(?P<universe>[0-9]+)\s\[(?P<data>[0-9, ]*)\]")

    def __init__(self, target_ip: str, filepath: Path, debug: int = 0):
        """Initializes Replay function.

        Args:
        target_ip (str): IP of the ArtNet Server
        filepath (Path): Path to the file to replay
        debug (int): n-th packet to print debug info
        """

        # Instance variables
        self.target_ip = target_ip
        self.filepath = filepath
        self.debug = debug

        # Get file info
        self.duration, self.universes = self.get_footer_info()

        if self.debug:
            print(h.bcolors.OKBLUE + "----------playback----------\nAdress: {}\nFile: '{}' ".format(self.target_ip, self.filepath) + h.bcolors.ENDC)

        self.textfile = open(h.unzip_file(self.filepath), 'r')

        # Create Smartnet instance
        self.a = Smartnet(self.target_ip, self.universes, 40, True)

    def playback(self):

        self.last = time.time_ns()
    
        def send(m):
            """Send data over ArtNet through socket"""
            # prepare data
            data = bytearray(list(map(int, m.group('data').split(','))))

            # send data and set last timestamp
            self.a.send_data(data, int(m.group('universe')))
            self.last = time.time_ns()

        while self.textfile:
            # Get new line
            line = self.textfile.readline()

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
                    print("U: {}, Timing: {}ms".format(match.group('universe'), round(time_left * 10**-6, 6)))
                    self.i = 0
        
        # Close textfile after break
        self.textfile.close()

    def start_playback(self):
        """Starts the playback thread"""
        try:
            self.start = time.time_ns()

            # Start thread
            self.worker = threading.Thread(target=self.playback)
            self.worker.start()

            # Wait for  thread to die
            while self.worker.is_alive():
                #refresh remaining time
                sys.stdout.write("\r%is" % round((self.duration * 10**6 - (time.time_ns() - self.start)) * 10**-9))
                sys.stdout.flush()

                time.sleep(1)

            print('\n')

        # User abort
        except KeyboardInterrupt:
            self.close()
            print("\n\nTERMINATED BY USER, Stopping playback.\n")

    def close(self):
        """Closes the playback thread and the ArtNet instance"""
        self.halt = True
        self.worker.join()
        self.a.close()

    def get_footer_info(self):
        """Returns the duration and universes from the footer of the file

        Returns:
            tuple(int[duration in ms], list[int(universes)])
        """

        with open(h.unzip_file(self.filepath), 'rb') as tf:
            
            try:  
                tf.seek(-2, SEEK_END)
                while tf.read(1) != b'\n':
                    tf.seek(-2, SEEK_CUR)

            # catch OSError in case of a one line file
            except OSError:
                tf.seek(0)
            
            last_line_info = tf.readline().decode().replace('!', '').split(' ')

        return int(last_line_info[1]), list(map(int, last_line_info[0].split(',')))
