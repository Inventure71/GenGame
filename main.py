import os
os.environ['SDL_VIDEODRIVER'] = 'cocoa'
import random
import argparse
from BASE_files.BASE_menu import BaseMenu
from coding.non_callable_tools.action_logger import action_logger

# TODO: Remember to call client.update() regularly in your main loop to process incoming messages and send outgoing ones.")


def run_menu():
    menu = BaseMenu(action_logger=action_logger)
    menu.run_menu_loop()

if __name__ == "__main__":
    random.seed(69)

    parser = argparse.ArgumentParser(description='GenGame Multiplayer Client')
    parser.add_argument('--player', default='Player', help='Player name')
    parser.add_argument('--host', default='127.0.0.1', help='Server host (default: 127.0.0.1)')
    parser.add_argument('--port', type=int, default=5555, help='Server port (default: 5555)')

    args = parser.parse_args()

    #network_client = NetworkClient(args.host, args.port)
    #run_client(network_client, player_id=args.player)
    run_menu()
