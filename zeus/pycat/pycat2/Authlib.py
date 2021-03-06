import hashlib
import common
from sys import exc_info

clients = []              #Format: [[socket, True/False],[socket_connection, True/False]]
                          #        [[socket_connection,authenticated?]]

client_auth_token = ""    #The token used to prove authentication
server_auth_token = ""

def update():
    global clients

    if common.flags['d']:
        print("****************")
        print("[*] Debug Info:")
        print("Raw Connections:")
        print(clients)
        print("****************\n")
    count = 0
    for c in clients:
        if "closed" in str(c):
            try:
                clients.remove(c)
                count =+ 1
                if common.flags['d']:
                    peer = str(c.getpeername()[0]) + ":" + str(c.getpeername()[1])
                    print("[*] Removed Client --> {}".format(peer))
            except ValueError:
                pass
            except:
                print("[!] Unknown Error:",exc_info())
    print("[*] Removed {} Clients".format(count))

def add_new_client(socket,auth_status=False):
    global clients
    count = 0
    for c in clients:
        if socket in c:
#            index = findIndexofClient(c)
            clients[count][1] = True
            break
        else:
            client = [socket,auth_status]
            clients.append(client)
        count =+1
        if common.flags['d']:
            print("[+] Added to Client List:")
            print(client)

def findIndexofClient(attribute):
    global clients
    count = 0
    try:
        for c in clients:
            if attribute == c[0] or attribute == c[1]:
                if common.flags['d']:
                    print("[*] Found Element in Client[{}]:".format(count))
                return count
            else:
                pass
        return False
    except:
        print("[!] Error: Unable to find client index ")
        if common.flags['d']:
            print(exc_info())

def listclients():
    global clients
    update()
    count = 1

    if len(clients) == 0:
        print("[*] There are no connected clients")
    for c in clients:
        print("[*] Client List:")
        label = "("+str(count)+")"
        peer = str(c[0].getpeername()[0])+":"+str(c[0].getpeername()[1])
        print("{n}{s} --> Authenticated: {b}".format(n=label,s=peer,b=str(c[1])))
        count =+1
    print("[*] There are {} connected clients".format(count))

    if common.flags['d']:
        print("[*] Raw List:")
        print(clients)

def countclients():

    total = len(clients)
    print("[*] Total Clients:", total)

def PromptPasswd():
    """Function to get a password either to use as the authentication token or to pass to a server
        Returns a password str
        :type state: bool"""

    global server_auth_token
    global client_auth_token

    if common.flags['key'] and common.flags['l']:
        server_auth_token = common.flags['key']
        return
    elif common.flags['key'] and common.flags['r']:
        client_auth_token = common.flags['key']
        return

    try:
        passwd_plaintext = input("[?] Enter a Passphrase: ")
    except KeyboardInterrupt:
        raise KeyboardInterrupt

    passwd_encoded = hashlib.sha3_256(passwd_plaintext.encode()).hexdigest()
    print("[*] Key:",passwd_encoded)
    if common.flags['l']:
        server_auth_token = passwd_encoded
    if common.flags['r']:
        try:
            token = input("[?] Enter the Authentication Token: ")
        except KeyboardInterrupt:
            raise KeyboardInterrupt

        client_auth_token = token


def CheckPasswd(token=server_auth_token,data=''):
    """Function to determine if a client provided the correct password
    If this function is called from a client, it will prompt for a password
    If this function is called from a server, it will check for a password in a str object
    Returns True if the correct password was found
    :type data: str"""

    if token in data:
        return True

    elif token not in data:
        return False


def AuthenticateClient():
    PromptPasswd()
    return client_auth_token

def AuthenticateServer(socket=None,data=""):
    global clients

    host = socket.getpeername()[0]
    port = socket.getpeername()[1]
    if common.flags['d']:
        print("[*] Authenticating --> {}:{}".format(host, port))
    if common.flags['auth'] or common.flags['key']:
        try:
            if findIndexofClient(socket) == False:
                authenticated = True
                if common.flags['d']:
                    print("[*] Client is already authenticated")
            else:
                authenticated = False
        except ValueError:
            authenticated = False

        if not authenticated:
            token = common.fixmsgformat(data.strip("[auth]"))
            auth = CheckPasswd(server_auth_token, token)
            if auth == False:
                if common.flags['d']:
                    print("[*] Authentication failed -->",str(host)+":"+str(port))
                return False
            else:
                add_new_client(socket,True)
                if common.flags['d']:
                    print("[*] Client authenticated successfully -->",str(host)+":"+str(port))
                return True