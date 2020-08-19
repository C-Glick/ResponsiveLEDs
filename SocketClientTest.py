import socket
HOST='10.37.11.78' #server ip or hostname
PORT=55555 #open port for communication, 1000+ recommended
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.connect((HOST, PORT))

while True:
    command = input('Enter your Command: ')
    s.send(command.encode('ascii'))
    reply = s.recv(1024).decode('ascii')
    if reply == 'Terminate':
        break
    print (reply)