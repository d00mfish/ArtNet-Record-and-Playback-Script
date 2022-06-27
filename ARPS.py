#!/usr/bin/python

from pathlib import Path
from turtle import bgcolor
from artnet_tools import ArtNetPlayback, ArtNetRecord
import sys, getopt

from helpfunctions import bcolors


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
        1:  bcolors.OKGREEN + 'Start (path input)' + bcolors.ENDC,
        2: 'Shuffle all local files',
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
                    try:
                        option = self.wait_for_input(promt='Universes to record', example='"0,1,2,3"', data_type=str)

                        if option != "":
                            universes = [int(i) for i in option.strip('" ').split(',')]
                            
                            option = self.wait_for_input(promt = "Output dir/file path [leave empty for current dir]:", example = '"C:/Users/output.dat"', data_type=str)
                            output_path = Path(option.strip('" '))

                            self.rec = ArtNetRecord(universes, self.record_dur, output_path)
                            self.rec.record()

                    except Exception as e:
                        print("An Error occured:", e)

                    return

                if option == 2:
                    option = self.wait_for_input(promt='Set Duration in Minutes, 0 is infinite: ', data_type=int)

                    if option > 0:
                        self.record_dur = option * 60
                    else:
                        self.record_dur = 0

                    self.print_menu(2)
                    continue

                if option == 3:
                    self.print_menu(1)

                if option == 4:
                    return

            ### Replay menu ###
            if self.menu_state == 3:  # Replay menu
                if option == 1:
                    path = self.wait_for_input(promt='Enter Filepath:', example='"C:/User/example.dat"', data_type=Path)
                    

                    ip = self.wait_for_input(promt='Enter IP:', example='"10.0.0.5"', data_type=str)
                    if ip != '':
                        try:
                            self.rep = ArtNetPlayback(ip, path)
                            print("Replaying...")
                            self.rep.start_playback()

                        except Exception as e:
                            print("An Error occured:", e)

                        self.print_menu(2)
                        continue

                if option == 2:
                    print("Not implemented yet")

                if option == 3:
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
-i, --ifile (C:/User/example.dat): File to play

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
            self.rec.start_recording()
        elif mode == 'rep':
            print("""
----------playback----------
Adress: {}
File: "{}"
""".format(ip, input_file))
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
