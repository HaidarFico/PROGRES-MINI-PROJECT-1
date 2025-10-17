import socket
import re
import select
import sys
import argparse
import datetime

BYTE_ENCODING = 'iso-8859-1'
BUFFER_SIZE = 4096

socket_map = {}
inputs = []
cache = {}

def logServerResponse(serverIP, clientIP, status, length):
    try:
        with open('loggersLog.txt', "a") as f:
            currentTime = datetime.datetime.now()
            f.write(f'{currentTime};RESPONSE;{serverIP};{clientIP};{status};{length}\n')
            print('Response logged!')
            f.close()
    except:
        with open('loggersLog.txt', "w") as f:
            f.close()
            logServerResponse(serverIP, clientIP, status, length)

def logClientRequest(clientIP, siteIP, URI):
    try:
        with open('loggersLog.txt', "a") as f:
            currentTime = datetime.datetime.now()
            f.write(f'{currentTime};REQUEST;{clientIP};{siteIP};{URI};GET\n')
            f.close()
            print('Client request logged!')
    except Exception as e:
        print(f'Exception writing client request with {e}')
        with open('loggersLog.txt', "w") as f:
            f.close()
            logClientRequest(clientIP, siteIP, URI)
    
def close_relay(conn):
    pair = socket_map.pop(conn, None)
    if pair in socket_map:
        del socket_map[pair]
    if conn in inputs:
        inputs.remove(conn)
    try:
        conn.close()
    except Exception as e:
        print(f"[ERROR] Closing {conn}")
    if pair:
        try:
            pair.close()
        except Exception as e:
            print(f"[ERROR] Closing {pair}")

def accept_client(listen_sock):
    try:
        client_conn, client_addr = listen_sock.accept()
        client_conn.setblocking(False)
        inputs.append(client_conn)
        socket_map[client_conn] = None
        print(f"[#] Client connected: {client_addr}")
    except Exception as e:
        print(f"[ERROR] Could not set up the relay")


def handle_http_request(sock):
    try:
        data = sock.recv(BUFFER_SIZE)
        if not data:
            close_relay(sock)
            return

        request = data.decode(BYTE_ENCODING)
        uri_match = re.match(r"GET\s+(\S+)", request)
        uri = uri_match.group(1) if uri_match else None

        logClientRequest(sock.getpeername(), parseURLForLog(request), uri)

        remote_host, remote_port = parseHTTPHost(request)
        # print(f'this is remote host and port {remote_host} {remote_port}')
        if not remote_host:
            close_relay(sock)
            return

        server_conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_conn.connect((remote_host, remote_port))
        server_conn.sendall(data)

        response = b''
        while True:
            chunk = server_conn.recv(BUFFER_SIZE)
            if not chunk:
                break
            response += chunk

        logServerResponse(server_conn.getpeername(), sock.getpeername(), 'TEMP', len(response))
        sock.sendall(response)
        server_conn.close()
        close_relay(sock)

    except (ConnectionResetError, OSError) as e:
        close_relay(sock)

def run(listen_port):
    listen_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listen_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        listen_sock.bind(("", listen_port))
    except Exception as e:
        print(f"[ERROR] Could not bind to port {listen_port}")
        sys.exit(1)
    listen_sock.listen()
    listen_sock.setblocking(False)
    inputs.append(listen_sock)
    print(f"[#] Relay running on port {listen_port}")

    try:
        while inputs:
            readable, _, _ = select.select(inputs, [], [])
            for sock in readable:
                if sock is listen_sock:
                    accept_client(listen_sock)
                else:
                    handle_http_request(sock)
    except Exception as e:
        print(f"Shutting Down...")
        print(e)
    finally:
        for s in inputs:
            s.close()
        print(f"Relay stopped")

def parseHTTPHost(headersDecoded: bytes):
    hostline = None
    try:
        for headerLine in headersDecoded.split('\r\n'):
            if headerLine.lower().startswith('host:'):
                hostline = headerLine.split(':', 1)[1].strip()
            if hostline:
                if ':' in hostline:
                    host, port = hostline.split(':', 1)
                    return host, int(port)
                return hostline, 80
        return None, None
    except:
        return None, None

def parseURLForLog(headersDecoded: str):
    try:
        for headerLine in headersDecoded.split('\n'):
            if headerLine.lower().startswith('get'):
                return headerLine
        return 'NONE'
    except:
        return 'NONE'

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="HTTP Relay")
    parser.add_argument("relay_port", type=int, default=9080, help="Relay port number")
    args = parser.parse_args()
    run(args.relay_port)