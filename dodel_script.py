from instagrapi import Client
from getpass import getpass
import logging # TODO
import os
import time
import subprocess
import sys
import boto3
import pymysql

DEFAULT_SESSION_JSON_PATH = '/tmp/session.json'
SLEEP_TIME = 30
LOG_FILE = '/tmp/logger.log'
ENDPOINT="mysqldb.123456789012.us-east-1.rds.amazonaws.com"
PORT="3306"
USER="jane_doe"
REGION="us-east-1"
DBNAME="mydb"
os.environ['LIBMYSQL_ENABLE_CLEARTEXT_PLUGIN'] = '1'
DEBUG_MODE = True

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
logger = setup_logging(LOG_FILE)

username = ''
password = ''
client = Client()



def log_debug(data):
	if DEBUG_MODE:
		log.debug(data)
		
def create_new_session(session_path=DEFAULT_SESSION_JSON_PATH):
	log_debug('Create New Session')
	username = input('Username: ')
	password = getpass() # Works only for linux. use win_getpass on windows
	client.delay_range = [1,3]

	if not client.login(username, password):
		logger.error(f'{username} login failed')			
		return False		 
	
	if not client.dump_settings(session_path):
		logger.error(f'dump settings into {session_path} failed')			
		return False

	log.debug(f'Successfull new session for user {username}')
	return True

def get_all_active_users(): # TODO
	log.debug(f'get all Active users')

	client = boto3.client('rds')

	#gets the credentials from .aws/credentials
	session = boto3.Session(profile_name='default')
	client = session.client('rds')

	token = client.generate_db_auth_token(DBHostname=ENDPOINT, Port=PORT, DBUsername=USER, Region=REGION)

	try:
	    conn =  pymysql.connect(host=ENDPOINT, user=USER, passwd=token, port=PORT, database=DBNAME, ssl_ca='SSLCERTIFICATE')
	    cur = conn.cursor()
	    cur.execute("""SELECT now()""") # TODO
	    query_results = cur.fetchall()
	    # print(query_results)

	except Exception as e:
	    logger.error("Database connection failed due to {}".format(e))         
	
	log.debug(f'get all active users {query_results}')
	
	client.close()
	return query_results

def is_licensed(user):
	return 'ydodeles' in user.username
		
def accept_licensed_pending_users(session_path=DEFAULT_SESSION_JSON_PATH):
	log.debug(f'accept licensed pending users. session path - {session_path}')
	
	if not os.path.exists(session_path):	
		logger.error(f'session file {session_path} is not exist')			
	
	client.load_settings(session_path)
	client.login(username, password)
	
	approved = []

	try: # check session
		client.get_timeline_feed()
	except:
		logger.error(f'load broken session from {session_path}')
		return approved, False
	
	log.debug(f'successfully connect to session')
	
	try:
		req = client.get_pending_requests()
		licensed_users = filter(is_licensed, req)
		log.debug(f'all requests - {map(lambda user: user.username, req)}')

		for user in licensed_users:
			if client.approve_pending_request(user.pk):
				approved.append(user.username)
			else:
				logger.error(f'Failed approve user {user.username} request')	
	except Exception as e:
		logger.error(f'Failed approve users requests.\n{e}')

	log.debug(f'successfull accept licensed users')
	return approved, True

def run(session_path=DEFAULT_SESSION_JSON_PATH):
	logger.info(f'Run - load session from {session_path}')

	while True:
		approved, valid_session = accept_licensed_pending_users(session_path)
		if not valid_session:
			break # TODO make new session
		
		if approved:			
			logger.info(f'New accepted followers - {approved}')
		time.sleep(SLEEP_TIME)

if __name__ == '__main__':
    subprocess.Popen(['python', '-c', f'from {os.path.basename(__file__)[:-3]} import run; run();', '&'] , stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL, start_new_session=True)
    time.sleep(4)