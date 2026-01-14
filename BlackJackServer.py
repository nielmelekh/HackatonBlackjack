import socket
import struct
import threading
import time
from Utilities import *
from Deck import Deck, hand_value

SERVER_NAME = "Dealer"


# --- Protocol Helpers ---
def pack_offer(tcp_port, name):
    padded_name = name.encode('utf-8').ljust(32, b'\x00')[:32]
    return struct.pack('!IBH32s', MAGIC_COOKIE, MSG_TYPE_OFFER, tcp_port, padded_name)


def unpack_request(data):
    try:
        cookie, msg_type, rounds, name_bytes = struct.unpack('!IBB32s', data)
        return cookie, msg_type, rounds, name_bytes.decode('utf-8').strip('\x00')
    except struct.error:
        return None


def pack_server_payload(result, rank, suit):
    return struct.pack('!IBBHB', MAGIC_COOKIE, MSG_TYPE_PAYLOAD, result, rank, suit)


def unpack_client_payload(data):
    try:
        cookie, msg_type, decision = struct.unpack('!IB5s', data)
        return cookie, msg_type, decision.decode('utf-8')
    except struct.error:
        return None


# --- Networking ---
def udp_broadcast_thread(tcp_port):
    udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

    offer_packet = pack_offer(tcp_port, SERVER_NAME)

    print(f"{GREEN}Server started, listening on IP address {socket.gethostbyname(socket.gethostname())}{RESET}")
    # print(f"Broadcasting offers with TCP port {tcp_port}")

    while True:
        try:
            udp_sock.sendto(offer_packet, ('<broadcast>', UDP_PORT))
            time.sleep(BROADCAST_INTERVAL)
        except Exception as e:
            print(f"{RED}Broadcast error: {e}{RESET}")

def handle_client(conn, addr):
    print(f"{CYAN}Connection from {addr}{RESET}")
    conn.settimeout(60)

    try:
        req_data = conn.recv(38)
        if not req_data: return
        cookie, msg_type, rounds, team_name = unpack_request(req_data)
        if cookie != MAGIC_COOKIE or msg_type != MSG_TYPE_REQUEST: return

        print(f"Team {YELLOW}{team_name}{RESET} connected for {rounds} rounds.")

        player_wins = 0

        for r in range(1, rounds + 1):
            print(f"--- Round {r} with {team_name} ---")

            # Use the Deck class
            deck = Deck()
            player_hand = []
            dealer_hand = []

            # -- Initial Deal --
            p_card1 = deck.draw()
            player_hand.append(p_card1)
            conn.sendall(pack_server_payload(0, p_card1[0], p_card1[1]))

            p_card2 = deck.draw()
            player_hand.append(p_card2)
            conn.sendall(pack_server_payload(0, p_card2[0], p_card2[1]))

            d_card1 = deck.draw()
            dealer_hand.append(d_card1)
            conn.sendall(pack_server_payload(0, d_card1[0], d_card1[1]))

            d_card2 = deck.draw()
            dealer_hand.append(d_card2)  # Hidden initially

            # -- Player Turn --
            player_active = True
            player_bust = False

            while player_active:
                try:
                    payload_data = conn.recv(10)
                    if not payload_data: break
                    _, _, decision = unpack_client_payload(payload_data)
                    decision = decision.strip('\x00')

                    if decision == "Hittt":
                        new_card = deck.draw()
                        player_hand.append(new_card)

                        # Use shared hand_value function
                        if hand_value(player_hand) > 21:
                            player_bust = True
                            player_active = False
                            conn.sendall(pack_server_payload(2, new_card[0], new_card[1]))  # 2 = Loss
                            print(f"{team_name} busted.")
                        else:
                            conn.sendall(pack_server_payload(0, new_card[0], new_card[1]))

                    elif decision == "Stand":
                        player_active = False
                except Exception:
                    return

            # -- Dealer Turn --
            if not player_bust:
                # 1. Reveal the hidden card first!
                conn.sendall(pack_server_payload(0, d_card2[0], d_card2[1]))

                # 2. Dealer logic: Hit until >= 17 using shared logic
                dealer_bust = False
                while hand_value(dealer_hand) < 17:
                    new_d_card = deck.draw()
                    dealer_hand.append(new_d_card)
                    conn.sendall(pack_server_payload(0, new_d_card[0], new_d_card[1]))

                if hand_value(dealer_hand) > 21: dealer_bust = True

                p_score = hand_value(player_hand)
                d_score = hand_value(dealer_hand)
                result_code = 0

                if dealer_bust:
                    result_code = 3
                    player_wins += 1
                    print(f"Server busted. {team_name} wins.")
                elif p_score > d_score:
                    result_code = 3
                    player_wins += 1
                    print(f"{team_name} wins ({p_score} vs {d_score}).")
                elif d_score > p_score:
                    result_code = 2
                    print(f"Server wins ({d_score} vs {p_score}).")
                else:
                    result_code = 1
                    print(f"Tie ({p_score}).")

                conn.sendall(pack_server_payload(result_code, 0, 0))

            time.sleep(0.5)

        print(f"Finished. Closing connection.")

    except Exception as e:
        print(f"{RED}Error: {e}{RESET}")
    finally:
        conn.close()


def start_server():
    # 1) Create TCP socket and let OS choose a free port (bind port 0)
    tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    tcp_sock.bind(('', 0))  # 0 => OS picks an available port
    tcp_port = tcp_sock.getsockname()[1]
    tcp_sock.listen(5)

    # 2) Start UDP broadcast thread with the chosen TCP port
    udp_thread = threading.Thread(target=udp_broadcast_thread, args=(tcp_port,), daemon=True)
    udp_thread.start()

    print(f"Listening for TCP connections on port {tcp_port}...")

    while True:
        conn, addr = tcp_sock.accept()
        threading.Thread(target=handle_client, args=(conn, addr)).start()


if __name__ == "__main__":
    start_server()