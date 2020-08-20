#use python3 <file_nanme> to run
import socket
import rpi_ws281x


HOST = '101fdisplay.lib.iastate.edu' #server ip or hostname
PORT = 55555 #open port for communication, 1000+ recommended
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
print('Socket created')

try:
        s.bind((HOST, PORT))
except socket.error:
        print('Bind failed')

s.listen(1)
print('Socket awaiting messages')
(conn, addr) = s.accept()
print('Connected')

#awaiting for message
while True:
        try:
                data = conn.recv(1024).decode('ascii')
                #sending reply
                conn.send(b'Ok')
                print('Recieved: ' + data)

                #print('I sent a message back in response to: ' + data)

                #process message
                #if data == 'Hello':
                #       reply = 'Hi back!'
                #elif data == 'important':
                #       reply = 'I have done the important thing!'
                if data == 'close':
                        conn.send(b'Terminate')
                        break
                else:
                        exec(data)

        #client disconnected, restart socket and wait for client
        except ConnectionResetError as e:
                print("Client disconnected")
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                try:
                        s.bind((HOST, PORT))
                except socket.error:
                        print('Bind failed')
                s.listen(1)
                print('Socket awaiting messages')
                (conn, addr) = s.accept()
                print('Connected')
                continue


conn.close() #close connection
