import socket
import select
import sys
import argparse
import re
from datetime import datetime

BUFFER_SIZE = 4096
CRLF = b'\r\n'
HDR_SEPARATOR = b'\r\n\r\n'
BYTE_ENCODING = 'iso-8859-1'

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


def accept_client(listen_sock):
    try:
        client_conn, client_addr = listen_sock.accept()
        client_conn.setblocking(False)
        inputs.append(client_conn)
        print(f'New client connected from: {client_addr}')

    except Exception as e:
        print(f"[ERROR] Could not set up the relay")
        print(e)

def run(listen_port, forbidden_links_file):
    parseForbiddenList(forbidden_links_file)
    print(f'This is the censored sites {bannedSites}')
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
                    accept_client(listen_sock)
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
        print(sock)
        data = sock.recv(BUFFER_SIZE)
        if not data:
            close_relay(sock)
            return
        
        pairedSocket = socket_map.get(sock)
        print(f'PAIREDSOCKET {pairedSocket}')
        if data.startswith(b'CONNECT'):
            print('[!] HTTPS (CONNECT) request - skipping')
            print(data.decode('iso-8859-1'))
            close_relay(sock)
            return
        # First connection from client
        if pairedSocket is None:
            serverHost, serverPort = parseHTTPHost(data)
            print(f'SERVER HOST {serverHost} SERVER PORT {serverPort}')
            if not serverHost:
                print('ERROR: no host found')
                close_relay(sock)
                return
            
            serverSock = socket.create_connection((serverHost, serverPort))
            serverSock.setblocking(False)

            print(f'SERVER SOCK {serverSock}')

            socket_map[sock] = serverSock
            socket_map[serverSock] = sock

            print(f"This is a test of the socket mapping {socket_map.get(sock)}")
            print(f"This is a test of the socket mappingsecond {socket_map.get(serverSock)}")
            inputs.append(serverSock)

            print(f"New relay: {sock.getpeername()} -> {serverHost}:{serverPort}")
            serverSock.sendall(data)
            return
        if sock in socket_map and pairedSocket:

            # data from client
            # if is_client_socket(sock):
            #     pairedSocket.sendall(data)
            #     return
            # For if the data comes from the server
            recvBuffers[sock] = recvBuffers.get(sock, b'') + data
            if (isHTTPMessageComplete(recvBuffers.get(sock, b''))):
                handleServerResponse(sock, pairedSocket, recvBuffers.get(sock, b''))   
                recvBuffers[sock] = b''
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
            siteAccesed = serverSock.getpeername()
            logClientsForbidden(clientIP, siteAccesed, forbiddenList)
        print(f'clientSock {clientSock}')
        if clientSock:
            fixedHeaders = adjustContentLength(parsedHttpHeaders, censoredBody)
            try:
                print(f"{fixedHeaders.decode(BYTE_ENCODING)}")
                print(f"{censoredBody.decode(BYTE_ENCODING)}")
                print(f"[DEBUG] Sending to clientSock: {clientSock}")
                print(f"[DEBUG] Client peer: {clientSock.getpeername()}")
                clientSock.sendall(fixedHeaders + censoredBody)
            except BlockingIOError:
                print("[!] Socket would block on send")
            except Exception as e:
                print(f"[!] Error sending to client: {e}")
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
    hostline = None
    try:
        headersDecoded = headerBytes.decode('iso-8859-1')
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

def censor(HttpBody: bytes):
    print('entering censor...')
    forbiddenLinksFound = []
    try:
        bodyParsed = HttpBody.decode('iso-8859-1')
    except UnicodeDecodeError:
        print('Error parsing httpbody')
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
                print('log written!')
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

def adjustContentLength(headers: bytes, body: bytes):
    headersDecoded = headers.decode('iso-8859-1')
    newHeaders = []
    contentLengthSet = False
    for line in headersDecoded.split('\r\n'):
        if line.lower().startswith('content-length:'):
            newHeaders.append(f'Content-Length: {len(body)}')
            contentLengthSet = True
        else:
            newHeaders.append(line)
    if not contentLengthSet:
        newHeaders.append(f'Content-Length: {len(body)}')
    return '\r\n'.join(newHeaders).encode('iso-8859-1') + b'\r\n\r\n'

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Simple HTTP Censor")
    parser.add_argument("relay_port", type=int, default=9080, help="Replay port number")
    parser.add_argument("forbidden_links_file", type=str, default='forbidden_list.txt', help='txt file of the forbidden sites')
    args = parser.parse_args()
    run(args.relay_port, args.forbidden_links_file)