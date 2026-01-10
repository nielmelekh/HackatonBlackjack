import socket
import struct
import sys
import time
from Utilities import *
from Deck import hand_value, format_card  # Import shared logic

TEAM_NAME = "ThunderCobras"


# --- Helpers ---
def unpack_offer(data):
    try:
        cookie, msg_type, port, name_bytes = struct.unpack('!IBH32s', data)
        return cookie, msg_type, port, name_bytes.decode('utf-8').strip('\x00')
    except:
        return None


def pack_request(rounds, name):
    padded_name = name.encode('utf-8').ljust(32, b'\x00')[:32]
    return struct.pack('!IBB32s', MAGIC_COOKIE, MSG_TYPE_REQUEST, rounds, padded_name)


def pack_decision(decision):
    padded_decision = decision.encode('utf-8')
    return struct.pack('!IB5s', MAGIC_COOKIE, MSG_TYPE_PAYLOAD, padded_decision)


def unpack_server_payload(data):
    try:
        cookie, msg_type, result, rank, suit = struct.unpack('!IBBHB', data)
        return cookie, msg_type, result, rank, suit
    except:
        return None


# --- Game Logic ---
def play_session(ip, port, rounds):
    tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        tcp_sock.connect((ip, port))
        tcp_sock.sendall(pack_request(rounds, TEAM_NAME))

        wins = 0

        for r in range(rounds):
            print(f"\n{BOLD}--- Round {r + 1} ---{RESET}")

            # Store full card tuples (rank, suit) to use Deck.hand_value
            my_hand = []
            dealer_hand = []

            def read_packet():
                buf = tcp_sock.recv(9)
                if not buf: raise Exception("Server disconnect")
                return unpack_server_payload(buf)

            # Initial Deal: P1, P2, D1
            p1 = read_packet();
            my_hand.append((p1[3], p1[4]))
            print(f"You: {format_card(p1[3], p1[4])}")

            p2 = read_packet();
            my_hand.append((p2[3], p2[4]))
            print(f"You: {format_card(p2[3], p2[4])}")

            # Use shared hand_value
            print(f"{YELLOW}Your Sum: {hand_value(my_hand)}{RESET}")

            d1 = read_packet();
            dealer_hand.append((d1[3], d1[4]))
            print(f"Dealer: {format_card(d1[3], d1[4])}")
            # Note: We don't show Dealer Sum yet because one card is hidden

            playing = True
            while playing:
                choice = input("Hit or Stand? ").strip().lower()

                if choice in ['hit', 'h']:
                    tcp_sock.sendall(pack_decision("Hittt"))
                    resp = read_packet()
                    _, _, res, rank, suit = resp

                    if rank != 0:
                        print(f"You: {format_card(rank, suit)}")
                        my_hand.append((rank, suit))
                        print(f"{YELLOW}Your Sum: {hand_value(my_hand)}{RESET}")

                    if res != 0:
                        if res == 2:
                            print(f"{RED}Bust! You lost.{RESET}")
                        elif res == 3:
                            print(f"{GREEN}You Won!{RESET}")
                        playing = False
                        break

                elif choice in ['stand', 's']:
                    tcp_sock.sendall(pack_decision("Stand"))
                    playing = False

                    # Dealer Phase
                    while True:
                        resp = read_packet()
                        _, _, res, rank, suit = resp

                        if res != 0:  # Game Over
                            if res == 3:
                                print(f"{GREEN}You Won!{RESET}")
                                wins += 1
                            elif res == 2:
                                print(f"{RED}Dealer Won!{RESET}")
                            elif res == 1:
                                print(f"{BLUE}It's a Tie!{RESET}")
                            break
                        else:
                            # This is a Dealer card (Hidden reveal OR new draw)
                            print(f"Dealer: {format_card(rank, suit)}")
                            dealer_hand.append((rank, suit))
                            print(f"{YELLOW}Dealer Sum: {hand_value(dealer_hand)}{RESET}")
                else:
                    print("Invalid input.")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        tcp_sock.close()
        print(f"Finished playing {rounds} rounds, win rate: {wins / rounds}")


def start_client():
    print(f"{GREEN}Client started, listening for offer requests...{RESET}")
    udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
    except:
        udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    udp_sock.bind(('', UDP_PORT))

    while True:
        data, addr = udp_sock.recvfrom(1024)
        offer = unpack_offer(data)
        if offer and offer[0] == MAGIC_COOKIE and offer[1] == MSG_TYPE_OFFER:
            print(f"Received offer from {addr[0]}")
            try:
                rounds = int(input("How many rounds? "))
            except:
                rounds = 1
            play_session(addr[0], offer[2], rounds)
            print(f"{GREEN}Listening...{RESET}")


if __name__ == "__main__":
    start_client()