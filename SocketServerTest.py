import socket

HOST = '10.37.11.78' #server ip or hostname
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
        data = conn.recv(1024).decode('ascii')
        print('I sent a message back in response to: ' + data)

        #process message
        if data == 'Hello':
                reply = 'Hi back!'
        elif data == 'important':
                reply = 'I have done the important thing!'
        elif data == 'quit':
                conn.send(b'Terminate')
                break
        else:
                reply = 'Recieved: ' + data

        #sending reply
        conn.send(reply.encode('ascii'))
conn.close() #close connection

