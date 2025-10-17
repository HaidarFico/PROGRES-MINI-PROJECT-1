import socket
import os
import argparse
from pathlib import Path
from urllib.parse import unquote

BUFF_SIZE = 4096
BASE_DIR = Path('.')

def get_content_type(file_path):
    ext = file_path.suffix.lower()
    return {
        '.html': 'text/html',
        '.css': 'text/css',
        '.js': 'application/javascript',
        '.txt': 'text/plain',
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.png': 'image/png',
    }.get(ext)

def list_directory(path):
    entries = sorted(path.iterdir())
    display_path = f"/{path.relative_to(BASE_DIR)}" if path != BASE_DIR else "/"

    html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Index of {display_path}</title>
            <style>
            body {{ font-family: Arial; background: #f9f9f9; padding: 20px; }}
                h1 {{ color: #333; }}
                a {{ text-decoration: none; color: #007acc; }}
                a:hover {{ text-decoration: underline; }}
            </style>
        </head>
        <body>
            <h1>Index of {display_path}</h1>
            <ul>
        """

    if path != BASE_DIR:
        parent = path.parent.relative_to(BASE_DIR)
        html += f'<li><a href="/{parent}">../</a></li>\n'

    for entry in entries:
        name = entry.name + '/' if entry.is_dir() else entry.name
        link = f"{entry.relative_to(BASE_DIR)}"
        html += f'<li><a href="/{link}">{name}</a></li>\n'

    html += "</ul></body></html>"
    return html.encode('utf-8')

def get_request_line(request):
    lines = request.split('\r\n')
    request_line = lines[0]
    return request_line.split()

def get_headers(request):
    lines = request.split('\r\n')
    headers = {}
    for line in lines[1:]:
        if ': ' in line:
            key, value = line.split(': ', 1)
            headers[key.lower()] = value
    return headers

def handle_request(request):
    method, raw_path, _ = get_request_line(request)
    headers = get_headers(request)
    path = unquote(raw_path.lstrip('/'))
    full_path = BASE_DIR / path

    if method != 'GET':
        body = b"405 Method Not Allowed"
        return (
            "HTTP/1.1 405 Method Not Allowed\r\n"
            "Content-Type: text/plain\r\n"
            f"Content-Length: {len(body)}\r\n\r\n"
        ).encode() + body

    if full_path.is_dir():
        body = list_directory(full_path)
        return (
            "HTTP/1.1 200 OK\r\n"
            "Content-Type: text/html\r\n"
            f"Content-Length: {len(body)}\r\n\r\n"
        ).encode() + body

    elif full_path.is_file():
        with open(full_path, 'rb') as f:
            body = f.read()
        content_type = get_content_type(full_path)
        return (
            "HTTP/1.1 200 OK\r\n"
            f"Content-Type: {content_type}\r\n"
            f"Content-Length: {len(body)}\r\n\r\n"
        ).encode() + body

    else:
        body = b"404 Not Found"
        return (
            "HTTP/1.1 404 Not Found\r\n"
            "Content-Type: text/plain\r\n"
            f"Content-Length: {len(body)}\r\n\r\n"
        ).encode() + body

def server(interface, port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((interface, port))
    sock.listen(5)
    print(f"[#] Web server listening on {interface}:{port}")

    while True:
        conn, addr = sock.accept()
        print(f"[+] Connection from {addr}")
        request = b""
        while True:
            chunk = conn.recv(BUFF_SIZE)
            request += chunk
            if b"\r\n\r\n" in request or not chunk:
                break

        if request:
            response = handle_request(request.decode('utf-8', errors='ignore'))
            conn.sendall(response)
        conn.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Improved Web Server")
    parser.add_argument("host", help="Interface to bind")
    parser.add_argument("-p", default=8080, type=int, help="Port to listen on")
    args = parser.parse_args()
    server(args.host, args.p)
