from instagrapi import Client
from getpass import getpass
import logging # TODO
import os
import time
import subprocess
import argparse
import random

from rds_connector import DatabaseConnection

DEFAULT_SESSION_JSON_PATH = '/tmp/session.json'
SLEEP_TIME = 1200
LOG_FILE = '/tmp/logger.log'
DEBUG_MODE = True
STATUSES_TO_APPROVE = ['ASSIGNED TO QUEST']

def setup_logging(log_path):
    # Create a logger
    logger = logging.getLogger('my_logger')
    logger.setLevel(logging.DEBUG)

    # Create a file handler and set the logging level
    file_handler = logging.FileHandler(log_path)
    file_handler.setLevel(logging.DEBUG)

    # Create a console handler and set the logging level
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)

    # Create a formatter and add it to the handlers
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    # Add the handlers to the logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger


# Set up logging with the specified log file path
logger = None

username = ''
password = ''
client = Client()

def log_debug(data):
    if DEBUG_MODE:
        logger.debug(data)
        
def create_new_session(session_path=DEFAULT_SESSION_JSON_PATH):
    log_debug('Create New Session')
    global username, password, client
    username = input('Username: ')
    password = getpass() # Works only for linux. use win_getpass on windows
    client.delay_range = [1,3]

    if not client.login(username, password):
        logger.error(f'{username} login failed')			
        return False		 
    
    if not client.dump_settings(session_path):
        logger.error(f'dump settings into {session_path} failed')			
        return False

    log_debug(f'Successfull new session for user {username}')
    return True


def get_license_checker(db):
    def is_approved(user):
        query = f"SELECT * FROM learners WHERE instagram_handle = '{user.username}'"
        result = db.query(query)
        if len(result) == 1:
            return result[0][6] in STATUSES_TO_APPROVE
        if len(result) > 1:
            logger.error(f'Found multiple users with instagram handle {user.username}')
            return False
        if len(result) == 0:
            return False
    return is_approved

def login_from_session(session_path=DEFAULT_SESSION_JSON_PATH): 
    if not os.path.exists(session_path):	
        logger.error(f'session file {session_path} is not exist')			
    
    client.load_settings(session_path)
    client.login(username, password)
    
    approved = []

    try: # check session
        client.get_timeline_feed()
    except:
        client.relogin()
        try:
            client.get_timeline_feed()
        except:
            logger.error(f'load broken session from {session_path}')
            return approved, False
    
    client.dump_settings(session_path)
    log_debug(f'successfully connect to session')

def accept_licensed_pending_users(session_path=DEFAULT_SESSION_JSON_PATH):
    log_debug(f'accept licensed pending users. session path - {session_path}')
    login_from_session(session_path)
    
    try:
        pending_requests = client.get_pending_requests()
        log_debug(f'all requests - {list(map(lambda user: user.username, pending_requests))}')
        with DatabaseConnection() as db:
            licensed_users = filter(get_license_checker(db), pending_requests)
            for user in licensed_users:
                if client.approve_pending_request(user.pk):
                    approved.append(user.username)
                    log_debug(f'user {user.username} approved')
                else:
                    logger.error(f'Failed approve user {user.username} request')
            
            if approved: 
                db.commit("UPDATE learners SET status = 'FOLLOWING ASSIGNED QUEST' WHERE instagram_handle IN ({})".format(','.join(map(lambda user: f'\'{user}\'', approved))))
                log_debug("change status for new users {}".format(approved))
    except Exception as e:
        logger.error(f'Failed approve users requests.\n{e}')

    log_debug(f'successfull accepting licensed users - {approved}')
    return approved, True

def run(session_path, log_file_path):
    global logger 
    logger = setup_logging(log_file_path)

    logger.info(f'Run - load session from {session_path}')

    while True:
        approved, valid_session = accept_licensed_pending_users(session_path)
        if not valid_session:
            break # TODO make new session
        
        if approved:			
            logger.info(f'New accepted followers - {approved}')
        time.sleep(SLEEP_TIME * (1 + (random.random() - 0.5) / 2)) # for making the instagram automation detector work harder 

def new_subprocess(session_path=DEFAULT_SESSION_JSON_PATH, log_file_path=LOG_FILE):
    popen_args = ['python3', '-c', f'from {os.path.basename(__file__)[:-3]} import run; run(\"{session_path}\", \"{log_file_path}\");', '&']
    log_debug(popen_args)
    subprocess.Popen(popen_args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL, start_new_session=True)
    time.sleep(4)

def main(args):
    global logger 
    logger = setup_logging(args.log_file_path)

    if args.make_new_session:
        create_new_session(args.session_path)
    
    new_subprocess(args.session_path, args.log_file_path)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Argument Parser Example")
    
    # Add command-line arguments
    parser.add_argument("session_path", type=str, help="Path to the session")
    parser.add_argument("log_file_path", type=str, help="Path to the log file")
    parser.add_argument(
        "--make_new_session", action="store_true", help="Flag to make a new session"
    )
    args = parser.parse_args()
    main(args)
