import socket
import select
import sys
import argparse
import re
from datetime import datetime

BUFFER_SIZE = 4096
CRLF = b'\r\n'
HDR_SEPARATOR = b'\r\n\r\n'

socket_map = {}
inputs = []
bannedSites = []
recvBuffers = {}
def close_relay(conn):
    pair = socket_map.pop(conn, None)
    if pair in socket_map:
        del socket_map[pair]
    if conn in inputs:
        inputs.remove(conn)
    if pair in inputs:
        inputs.remove(pair)

    try:
        conn.close()
    except Exception as e:
        print(f"[ERROR] Closing {conn}")
    if pair:
        try:
            pair.close()
        except Exception as e:
            print(f"[ERROR] Closing {pair}")


def accept_client(listen_sock, remote_host, remote_port):
    try:
        client_conn, client_addr = listen_sock.accept()
        client_conn.setblocking(False)

        server_conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_conn.connect((remote_host, remote_port))
        server_conn.setblocking(False)

        inputs.append(client_conn)
        inputs.append(server_conn)

        socket_map[client_conn] = server_conn
        socket_map[server_conn] = client_conn

        print(f"New relay: {client_addr} -> {remote_host}:{remote_port}")

    except Exception as e:
        print(f"[ERROR] Could not set up the relay")
        print(e)

# def  data_transfer(sock, remote_host, remote_port):
#     try:
#         data = sock.recv(BUFFER_SIZE)

#         if data:
#             paired_sock = socket_map.get(sock)
#             if paired_sock:
#                 paired_sock.sendall(data)
#             else:
#                 close_relay(sock)
#         else:
#             close_relay(sock)
#     except (ConnectionResetError, OSError):
#         close_relay(sock)


def run(listen_port, remote_host, remote_port, forbidden_links_file):
    parseForbiddenList(forbidden_links_file)
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
            readable, _, _ = select.select(inputs, [], inputs)

            for sock in readable:
                if sock is listen_sock:
                    accept_client(listen_sock, remote_host, remote_port)
                else:
                    handleSocket(sock)
    except Exception as e:
        print(f"Shutting Down...")
        print(e)
    finally:
        for sock in inputs:
            if sock is not listen_sock:
                close_relay(sock)
            else:
                sock.close()
        print(f"Relay stopped")

def handleSocket(sock: socket):
    try:
        
        pairedSocket = socket_map.get(sock)
        if not pairedSocket:
            close_relay(sock)
            return
        
        # For if the data comes from client
        if sock in socket_map and socket_map[sock] and sock.getpeername():
            data = sock.recv(BUFFER_SIZE)
            if not data:
                close_relay(sock)
                return
            recvBuffers[sock] = recvBuffers.get(sock, b'') + data
            if (isHTTPMessageComplete(recvBuffers.get(sock, b''))):
                pairedSocket.sendall(data)
        else:
            # For if the data comes from the server
            if (isHTTPMessageComplete(recvBuffers.get(sock, b''))):
                handleServerResponse(sock, pairedSocket, recvBuffers.get(sock, b''))   
    except:
        return

def handleServerResponse(serverSock: socket, clientSock: socket, currentBuffer: bytes):
    isHeaderParsed = False
    isBodyParsed = False
    buffer = currentBuffer
    while not isHeaderParsed: 
        parsedHttpHeaders, buffer = parseHTTPHeaders(buffer)
        if parsedHttpHeaders is not None:
            isHeaderParsed = True


    while (not isBodyParsed) and isHeaderParsed:
        bodyLength = getHTTPBodyContentLength(parsedHttpHeaders)
        parsedHttpBody, buffer = parseHTTPBody(buffer, bodyLength)
        if parsedHttpBody is not None:
            isBodyParsed = True

    if isBodyParsed and isHeaderParsed:
        # Parse the body for censors
        censoredBody, forbiddenList = censor(parsedHttpBody)
        if(censoredBody != parsedHttpBody):
            clientIP = clientSock.getpeername()[0]
            siteAccesed = parseHTTPHost(parsedHttpHeaders)
            logClientsForbidden(clientIP, siteAccesed, forbiddenList)

        if clientSock:
            clientSock.sendall(parsedHttpHeaders + censoredBody)
        else:
            close_relay(serverSock)
    else:
        close_relay(serverSock)

def parseHTTPHeaders(data: bytes):
    # Parse the buffer to find header
    headerSeperator = data.find(HDR_SEPARATOR)
    if headerSeperator == -1:
        return None
    headerBytes = data[:headerSeperator + len(HDR_SEPARATOR)]
    remainingBytes = data[headerSeperator + len(HDR_SEPARATOR):]
    return headerBytes, remainingBytes

def getHTTPBodyContentLength(headerBytes: bytes):
    try:
        headersParsed = headerBytes.decode('iso-8859-1')
    except UnicodeDecodeError:
        return 0
    for headerLine in headersParsed.split('\r\n'):
        if headerLine.lower().startswith('content-length:'):
            try:
                return int(headerLine.split(':', 1)[1].strip())
            except ValueError:
                return 0
    return 0

def parseHTTPBody(data:bytes, bodyLength: int):
    if bodyLength == 0:
        return b'', data
    
    if len(data) < bodyLength:
        return None, data
    
    body = data[:bodyLength]
    remaining = data[bodyLength:]
    return body, remaining

def parseHTTPHost(headerBytes: bytes):
    try:
        headersDecoded = headerBytes.decode('iso-8859-1')
        for headerLine in headersDecoded.split('\r\n'):
            if headerLine.lower().startswith('host:'):
                return headerLine.split(':', 1)[1].strip()
    except:
        return "unknown"

def censor(HttpBody: bytes):
    forbiddenLinksFound = []
    try:
        bodyParsed = HttpBody.decode('iso-8859-1')
    except UnicodeDecodeError:
        return HttpBody
    # Regex to get all instances of <a href="...">...</a>
    regexPattern = re.compile(r'<a\s+href="([^"]+)">(.*?)</a>', re.IGNORECASE | re.DOTALL)

    def replace_link(match):
        url = match.group(1)
        inner = match.group(2)
        for forbidden in bannedSites:
            if forbidden in url:
                forbiddenLinksFound.append(forbidden)
                return "<a>FORBIDDEN</a>"
        return match.group(0)  # leave unchanged

    censoredText = regexPattern.sub(replace_link, bodyParsed)

    return censoredText.encode('iso-8859-1'), forbiddenLinksFound

def logClientsForbidden(clientIP, siteAccessed, forbiddenSites):
    try:
        with open('logClientForbidden.txt', "a") as f:
            currentTime = datetime.now()
            for forbiddenSite in forbiddenSites:
                f.write(f'{currentTime};{clientIP};{siteAccessed};{forbiddenSite}\n')
                f.close()
    except:
        with open('logClientForbidden.txt', "w") as f:
            f.write(f'date_time;client_ip;site_accessed;forbidden_site\n')
            f.close()
            logClientsForbidden(clientIP, siteAccessed, forbiddenSites)

def parseForbiddenList(fileName: str):
    try:
        with open(fileName, "r") as f:
            sites = f.read()
            for site in sites.split('\n'):
                bannedSites.append(site)
    except:
        print('Failed to read site list! List is empty.')

def isHTTPMessageComplete(buffer: bytes):
    endOfHeader = buffer.find(b'\r\n\r\n')
    if endOfHeader == -1:
        return False
    
    headers = buffer[:endOfHeader + 4]

    # decode header to find content length
    contentLength = getHTTPBodyContentLength(headers)

    totalLength = contentLength + 4 + endOfHeader

    return len(buffer) >= totalLength

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Simple HTTP Censor")
    parser.add_argument("host", help="Host address of server")
    parser.add_argument("port", type=int, help="Port number of server")
    parser.add_argument("relay_port", type=int, default=9080, help="Replay port number")
    parser.add_argument("forbidden_links_file", type=str, default='forbidden_list.txt', help='txt file of the forbidden sites')
    args = parser.parse_args()
    run(args.relay_port, args.host, args.port, args.forbidden_links_file)