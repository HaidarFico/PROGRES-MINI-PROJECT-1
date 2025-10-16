import socket
import os
import argparse
from pathlib import Path

BUFF_SIZE = 1024
BASE_DIR = Path('.')

def list_files(dir_name=""):
    files = os.listdir(BASE_DIR)
    html = "<html><body><h1>Files</h1><ul>"
    for f in files:
        path = f"/{f}"
        html += f'<li><a href="{path}">{f}</a></li>'
    html += "</ul></body></html>"
    return html

def server(interface, port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((interface, port))
    sock.listen(1)
    print('Listening at {}'.format(sock.getsockname()))
    while True:
        sc, sockname = sock.accept()
        print("Accepted the connection from {}".format(sockname))
        request = sc.recv(BUFF_SIZE).decode('utf-8')
        print("Request received:\n{}".format(request))
        if request.split()[0] == 'GET':
            resource = request.split()[1]
            if resource == '/':
                block_length = len(list_files())
                response = (
                    "HTTP/1.1 200 OK\r\n"
                    "Content-Type: text/html\r\n"
                    f"Content-Length: {block_length}\r\n\r\n"
                    f"{list_files()}"
                )
            else:
                resource = resource.lstrip('/')
                if resource in list(map(Path.as_posix, BASE_DIR.rglob("*"))):
                    for file in BASE_DIR.rglob('*'):
                        if file.name == resource and file.is_file():
                            resource_path = file.as_posix()
                            with open(resource_path, 'rb') as f:
                                txt = f.read()
                            block_length = len(txt)
                            response = (
                                "HTTP/1.1 200 OK\r\n"
                                "Content-Type: text/plain\r\n"
                                f"Content-Length: {block_length}\r\n\r\n"
                                f"{txt.decode('utf-8')}"
                            )
                            break
                else:
                    response = (
                        "HTTP/1.1 404 Not Found\r\n"
                        "Content-Type: text/plain\r\n"
                        "Content-Length: 9\r\n\r\n"
                        f"{resource} Not Found"
                    )
        else:
            response = (
                "HTTP/1.1 405 Not Found\r\n"
                "Content-Type: text/plain\r\n"
                "Content-Length: 9\r\n\r\n"
                "THE REQUESTED METHOD IS NOT SUPPORTED"
            )
        sc.sendall(response.encode('utf-8'))
        sc.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Simple Webserver over TCP")
    parser.add_argument("host", help="Interface of server")
    parser.add_argument("-p", default=80, type=int, help="Port webserver listening to")
    args = parser.parse_args()
    server(args.host, args.p)
