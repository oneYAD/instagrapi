from instagrapi import Client
from instagrapi.exceptions import LoginRequired, PleaseWaitFewMinutes
from instagrapi.exceptions import LoginRequired, PleaseWaitFewMinutes

from getpass import getpass
import logging # TODO
import os
import time
import subprocess
import argparse
import random
from rds_connector import DatabaseConnection

DEFAULT_SESSION_JSON_PATH = '/tmp/session.json'
DEFAULT_SLEEP_TIME = 3 * 60 # 3 minutes
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

def log_debug(data):
    if DEBUG_MODE:
        logger.debug(data)

def create_new_session(session_path, username, password):
    log_debug('Create New Session')
    client = Client()
    client.delay_range = [1,3]

    if not client.login(username, password):
        logger.error(f'{username} login failed')                       
        return False 
    
    if not client.dump_settings(session_path):
        logger.error(f'dump settings into {session_path} failed')                      
        return False

    log_debug(f'Successfull new session for user {username}')
    return True

class IGBot:
    def __init__(self, username, password, session_path ,sleep_time=DEFAULT_SLEEP_TIME):
        """ 
        Create a new bot instance
        """
        self.username = username
        self.password = password
        self.sleep_time = sleep_time
        self.session_path = session_path
        self.last_bad_logins_time = [0,0]
        self.initiate_login()
 

    def get_license_checker(self, db):
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
    

    def initiate_login(self, dont_use_session=False):
        def default_handle_exception(client, e):
            log_debug(f'handle exception {e}')
            if isinstance(e, LoginRequired):
                logger.exception(e)
                client.relogin()
            else:
                raise e

        self.client = Client()
        self.client.handle_exception = default_handle_exception
        if (self.session_path and not dont_use_session):
            self.client.load_settings(self.session_path)
            self.client.login('', '')
        else:
            self.client.login(self.username, self.password)
            self.client.dump_settings(self.session_path)
        log_debug(f'Successfull initiate login for user {self.username}')

    def checked_logged_in(self):
        simple_client_functions = [
            (self.client.get_timeline_feed, ()),
            (self.client.user_info, (self.client.user_id, False)),
            (self.client.user_followers, (self.client.user_id, False, 2)),
            (self.client.user_following, (self.client.user_id, False, 2)),
            (self.client.user_friendship_v1, (self.client.user_id,)),
        ]
        try:
            func, args = random.choice(simple_client_functions)
            log_debug(f'try running {func.__name__}{args}')
            func(*args)
        except Exception as e:
            log_debug(f'failed running {func.__name__}{args}. error - {e}')
            return False, e
        return True, None
    
    def validate_login(self): 
        if not os.path.exists(self.session_path):	
            logger.error(f'session file {self.session_path} is not exist')			
        
        try: # check session
            logged_in, e = self.checked_logged_in()
            if not logged_in and isinstance(e, (LoginRequired, PleaseWaitFewMinutes)):
                time_from_last_bad_logins = time.time() - self.last_bad_login_time.pop()
                if (time_from_last_bad_logins < 60 * 60): # hour
                    time.sleep(max(60 * 60 - time_from_last_bad_logins, 1))
                self.initiate_login(dont_use_session=True)
                logged_in, e = self.checked_logged_in()
                if not logged_in:
                    raise e
                self.last_bad_logins_time.append(time.time())
                
        except Exception as e:
            logger.error(f'load broken session from {self.session_path}. error - {e}')
            return False
        
        return True
    
    def accept_licensed_pending_users(self):
        log_debug(f'accept licensed pending users. session path - {self.session_path}')
        if not self.validate_login():
            return [], False
        log_debug(f'successfully connect to session')

        approved = []
        try:
            pending_requests = self.client.get_pending_requests()
            log_debug(f'all requests - {list(map(lambda user: user.username, pending_requests))}')
            with DatabaseConnection() as db:
                licensed_users = filter(self.get_license_checker(db), pending_requests)
                for user in licensed_users:
                    if self.client.approve_pending_request(user.pk):
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

def run_auto_acceptor(session_path, log_file_path, sleep_time, username, password):
    global logger 
    logger = setup_logging(log_file_path)
    logger.info(f'Run - load session from {session_path}')

    bot = IGBot(username, password, session_path, sleep_time)
    
    while True:
        approved, valid_session = bot.accept_licensed_pending_users()
        if not valid_session:
            break 
        
        if approved:			
            logger.info(f'New accepted followers - {approved}')
        time.sleep(max(random.gauss(sleep_time, sleep_time/3), 1)) # for making the instagram automation detector work harder 

def new_subprocess(session_path, log_file_path, sleep_time, username, password):
    popen_args = ['python3', '-c', f'from {os.path.basename(__file__)[:-3]} import run_auto_acceptor; run_auto_acceptor(\"{session_path}\", \"{log_file_path}\", {sleep_time}, \"{username}\", \"{password}\");', '&']
    log_debug(popen_args)
    subprocess.Popen(popen_args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL, start_new_session=True)
    time.sleep(1)

def main(args):
    global logger 
    logger = setup_logging(args.log_file_path)
    username = input('Username: ')
    password = getpass() # Works only for linux. use win_getpass on windows
    
    if args.make_new_session:
        create_new_session(args.session_path, username=username, password=password)

    new_subprocess(args.session_path, args.log_file_path, args.sleep_time, username, password)

if __name__ == '__main__': 
    parser = argparse.ArgumentParser(description="Argument Parser Example")
    
    # Add command-line arguments
    parser.add_argument("session_path", type=str, help="Path to the session")
    parser.add_argument("log_file_path", type=str, help="Path to the log file")
    parser.add_argument(
        "--make-new-session", dest="make_new_session", action="store_true", help="Flag to make a new session"
    )

    parser.add_argument("--sleep-time", dest="sleep_time", type=int, default=DEFAULT_SLEEP_TIME, help="Seconds to wait between connections", required=False)
    
    args = parser.parse_args()
    main(args)
