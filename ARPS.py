#!/usr/bin/python

from pathlib import Path
from os import walk
from random import shuffle
from turtle import bgcolor
from artnet_tools import ArtNetPlayback, ArtNetRecord
import sys, getopt

from helpfunctions import bcolors

#TODO:
# Test IP with regex mask
# Dispalyed time gets negative


class Menu:

    menu_state = 0 #current menu
    record_dur = 600  # 10min default

    # Menu ID: 1
    mainmenu_options = {
        1: 'Record Art-Net',
        2: 'Replay Art-Rec File',
        3: bcolors.FAIL + 'Exit' + bcolors.ENDC,
    }

    # Menu ID: 2
    recordmenu_options = {
        1: bcolors.OKGREEN + 'Start Recording' + bcolors.ENDC,
        2: 'Set Duration (Default 10 Minutes)',
        3: 'Back',
        4: bcolors.FAIL + 'Exit' + bcolors.ENDC,
    }

    # Menu ID: 3
    replaymenu_options = {
        1:  bcolors.OKGREEN + 'Play one or more files in dir' + bcolors.ENDC,
        2: 'Shuffle all local files (not implemented)',
        3: 'Back',
        4: bcolors.FAIL + 'Exit' + bcolors.ENDC,
    }

    menus = {
        1: mainmenu_options,
        2: recordmenu_options,
        3: replaymenu_options,
    }

    def wait_for_input(self, promt: str = 'Enter option: ', example: str = None, data_type=None):
        """Asks for input from user and returns it.

        Args:
            promt (str, optional): Promt to show. Defaults to 'Enter option: '.
            example (str, optional):Example to add. Defaults to None.
            data_type (type, optional):Desired Datatype to return. Defaults to None.

        Returns:
            user input: user inout in datatype, if type matches
        """
        ret = ''
        try:
            if example:
                promt = promt.strip(':') + ' (' + example + '): '

            ret = input(bcolors.WARNING + promt + bcolors.ENDC)

            # Apply data type if any
            if data_type:
                ret = data_type(ret)

        except KeyboardInterrupt:
            self.exit_skript()

        except:
            print('Wrong input.', end=' ')

            if data_type:
                print('Please enter a', str(data_type))
            self.wait_for_input(promt, example, data_type)

        return ret

    def get_artrec_files(self, path):

        # Get all files in current directory
        files = next(walk(path), (None, None, []))[2]

        if files != []:
            # Filter out all non-artrec files
            files = [f for f in files if f.endswith('.artrec')]
        
        return files

    def shuffle_loop(self, path, ip):
        playlist = self.get_artrec_files(path)
        if playlist != []:
            try:
                while(1):
                    # Play all files in dir
                    for file in playlist:
                        self.rep = ArtNetPlayback(ip, Path.cwd() / file)
                        print("Replaying: {}".format(file))
                    
                    # Re-shuffle playlist
                    shuffle(playlist)

            # Exit skript if user presses Ctrl+C
            except KeyboardInterrupt:
                print(bcolors.WARNING + "\nExiting loop..." + bcolors.ENDC)
                return

    def print_menu(self, ID):
        """prints the menu with the given ID

        Args:
            ID (int): Menu ID of "menus" dict above
        """
        for key in self.menus[ID].keys():
            print(key, '--',  self.menus[ID][key])

        self.menu_state = ID

    def __init__(self):
        pass

    def init_replay(self, path: Path, ip):
        """Determine if path is a file or a directory and start playback accordingly

        Args:
            path (Path): Directory or file to play
            ip (_type_): IP of Art-Net receiver
        """

        if ip != '':
        
            if path.name.endswith('.artrec'):
                self.rep = ArtNetPlayback(ip, path)
                print(bcolors.OKGREEN + "Replaying..." + bcolors.ENDC)
                self.rep.start_playback()

            elif path.is_dir():
                playlist = self.get_artrec_files(path)

                if playlist != []:
                    
                    for i,artrec in enumerate(playlist):
                        self.rep = ArtNetPlayback(ip, path / artrec)
                        print(bcolors.OKGREEN + f"Replaying...{i+1}/{len(playlist)}" + bcolors.ENDC)
                        self.rep.start_playback()
                else:
                    print(bcolors.FAIL + "No files found in directory." + bcolors.ENDC)

            else:
                print(bcolors.FAIL + "Can't handle the path input." + bcolors.ENDC)

        else:
            print("No IP address given.")

    def init_record(self, path: Path, universes):
        if universes != "":
            universes = [int(i) for i in universes.strip('" ').split(',')]

            self.rec = ArtNetRecord(universes, self.record_dur, path)
            self.rec.record()
        
        else:
            print(bcolors.FAIL + "No universes given." + bcolors.ENDC)

    def exit_skript(self):
        print(bcolors.PINK + 'Alright, bye!' + bcolors.ENDC)
        sys.exit(0)

    def menu_logic(self):
        #Print Welcome Message
        print(self.logo() + "Use it directly with arguments, see -h for help.\n")

        self.print_menu(1)

        while(True):

            option = self.wait_for_input(data_type=int)
            ### Main Menu ###
            if self.menu_state == 1:
                if option == 1:
                    self.print_menu(2)
                    continue
                elif option == 2:
                    self.print_menu(3)
                    continue
                elif option == 3:
                    self.exit_skript()
                else:
                    print('Invalid option. Please enter a number between 1 and 3.')

            ### Record menu ###
            if self.menu_state == 2:
                if option == 1:
                    
                    # Get user input
                    universes = self.wait_for_input(promt='Universes to record', example='"0,1,2,3"', data_type=str)
                    path = self.wait_for_input(promt = "Output dir/file path [leave empty for current dir]:", example = '"C:/Users/output.dat"', data_type=Path)

                    # Start recording
                    self.init_record(path, universes)

                    # Exit after recording
                    return

                if option == 2:

                    # Get user input
                    self.record_dur = self.wait_for_input(promt='Set Duration in Minutes, 0 is infinite: ', data_type=int)

                    # Return to record menu
                    self.print_menu(2)
                    continue

                if option == 3:
                    
                    # Return to main menu
                    self.print_menu(1)

                if option == 4:

                    # Exit
                    return

            ### Replay menu ###
            if self.menu_state == 3: 
                if option == 1:
                    
                    # Get user input
                    path = self.wait_for_input(promt='Enter Filepath or Directory:', example='"C:/User/example.dat"', data_type=Path)
                    ip = self.wait_for_input(promt='Enter IP:', example='"10.0.0.5"', data_type=str)

                    # Start playback
                    self.init_replay(path, ip)

                    # Exit after playback
                    return

                if option == 2:
                    
                    path = self.wait_for_input(promt='Enter Filepath or Directory (None for current path):', data_type=Path)
                    ip = self.wait_for_input(promt='Enter IP:', example='"10.0.0.5"', data_type=str)

                    self.shuffle_loop(path, ip)
                    self.print_menu(3)
                    continue


                if option == 3:

                    # Return to main menu
                    self.print_menu(1)

                if option == 4:
                    return

    def logo(self) -> str:
        return(bcolors.PINK + """
          _____  _____   _____ 
    /\   |  __ \|  __ \ / ____|
   /  \  | |__) | |__) | (___  
  / /\ \ |  _  /|  ___/ \___ \ 
 / ____ \| | \ \| |     ____) |
/_/    \_\_|  \_\_|    |_____/ 
""" +  bcolors.BOLD  + "Art-Net Record and Playback Script\n"
 + bcolors.ENDC)

    def argparse(self, argv) -> int:
        input_file = Path()
        output = Path()
        mode = ''
        ip = ''
        universes = []
        debug = 0
        help = self.logo() + """
Usage: ARPS.py [OPTIONS] or with menu.

-h, --help: Print this help
-v, --verbose (40): Prints debug msg every n frames 
-m, --mode (r,rec,record / p,play,playback): Mode to run in

""" + bcolors.OKGREEN +"""----------playback----------
-a, --adress (10.1.2.3): IP of Art-Net destination
-i, --ifile (C:/User/example.dat): File or Dir to play

""" + bcolors.OKBLUE +"""----------record----------
-u, --universes (0,1,2,3): Universes to record
-d, --duration (30): Duration of recording in minutes
-o, --out (C:/User/[example.dat]): Output file or directory
""" + bcolors.ENDC

        try:
            opts, args = getopt.getopt(
                argv, "hm:i:a:u:d:o:v:",
                ["help", "mode=", "adress=", "ifile=", "universes=", "duration=", "out=", "verbose="])
        except getopt.GetoptError:
            print(help)
            sys.exit(2)

        if opts == []:
            return 0

        try:

            for opt, arg in opts:
                if opt in ('-h', '--help'):
                    print(help)
                    sys.exit()

                elif opt in ("-m", "--mode"):
                    if arg in ('record','r','rec'):
                        mode = 'rec'

                    elif arg in ('play','p','playback'):
                        mode = 'rep'

                elif opt in ("-i", "--ifile"):
                    input_file = Path(arg.strip('" '))

                elif opt in ("-a", "--adress"):
                    ip = arg.strip('"')

                elif opt in ("-u", "--universes"):
                    universes = list(map(int, arg.split(',')))

                elif opt in ("-d", "--duration"):
                    self.record_dur = int(arg)

                elif opt in ("-o", "--output"):
                    output = Path(arg.strip('" '))

                elif opt in ("-v", "--verbose"):
                    debug = int(arg)

        except Exception as e:
            print("Something went wrong parsing the arguments:", e)
            return -1
            
        if mode == 'rec':
            self.rec = ArtNetRecord(universes, self.record_dur, output, debug)
            self.rec.record()

        elif mode == 'rep':
            self.rep = ArtNetPlayback(ip, input_file, debug)
            self.rep.start_playback()


if __name__ == '__main__':
    # Create a new menu instance
    m = Menu()

    # See if args were given
    ret = m.argparse(sys.argv[1:])

    # If no args were given, run the menu
    if ret == 0:
        m.menu_logic()
    
    # When leaving function, exit skript
    m.exit_skript()
