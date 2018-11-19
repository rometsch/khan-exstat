#!/usr/bin/env python3
""" A script to retrieve exercise status via the khanacademy API"""
from __future__ import print_function
import cgi
import rauth
import http.server
import socketserver
import time
import webbrowser
import json
import argparse

# You can get a CONSUMER_KEY and CONSUMER_SECRET for your app here:
# http://www.khanacademy.org/api-apps/register
CONSUMER_KEY = ''
CONSUMER_SECRET = ''

CALLBACK_BASE = '127.0.0.1'
SERVER_URL = 'http://www.khanacademy.org'

DEFAULT_API_RESOURCE = '/api/v1/playlists'
VERIFIER = None


# Create the callback server that's used to set the oauth verifier after the
# request token is authorized.
def create_callback_server():
    class CallbackHandler(http.server.SimpleHTTPRequestHandler):
        def do_GET(self):
            global VERIFIER

            params = cgi.parse_qs(self.path.split('?', 1)[1],
                keep_blank_values=False)
            VERIFIER = params['oauth_verifier'][0]

            self.send_response(200)
            self.send_header('Content-Type', 'text/plain')
            self.end_headers()
            self.wfile.write(b'OAuth request token fetched and authorized;' +
                b' you can close this window.')

        def log_request(self, code='-', size='-'):
            pass

    server = socketserver.TCPServer((CALLBACK_BASE, 0), CallbackHandler)
    return server

# Make an authenticated API call using the given rauth session.
def get_api_resource(session, resource_url):
    url = SERVER_URL + resource_url
    split_url = url.split('?', 1)
    params = {}

    # Separate out the URL's parameters, if applicable.
    if len(split_url) == 2:
        url = split_url[0]
        params = cgi.parse_qs(split_url[1], keep_blank_values=False)

    start = time.time()
    response = session.get(url, params=params)
    end = time.time()

    # print("\nTime: %ss\n" % (end - start))
    return response.text

def init_server(CONSUMER_KEY, CONSUMER_SECRET, SERVER_URL):

    # Create an OAuth1Service using rauth.
    service = rauth.OAuth1Service(
           name='test',
           consumer_key=CONSUMER_KEY,
           consumer_secret=CONSUMER_SECRET,
           request_token_url=SERVER_URL + '/api/auth2/request_token',
           access_token_url=SERVER_URL + '/api/auth2/access_token',
           authorize_url=SERVER_URL + '/api/auth2/authorize',
           base_url=SERVER_URL + '/api/auth2')

    callback_server = create_callback_server()

    # 1. Get a request token.
    request_token, secret_request_token = service.get_request_token(
        params={'oauth_callback': 'http://%s:%d/' %
            (CALLBACK_BASE, callback_server.server_address[1])})

    # 2. Authorize your request token.
    authorize_url = service.get_authorize_url(request_token)
    webbrowser.open(authorize_url)

    callback_server.handle_request()
    callback_server.server_close()

    # 3. Get an access token.
    session = service.get_auth_session(request_token, secret_request_token,
        params={'oauth_verifier': VERIFIER})

    return session

def load_keyfile(keyfile):
    global CONSUMER_KEY, CONSUMER_SECRET
    lines = []
    with open(keyfile, 'r') as infile:
        for line in infile:
            line = line.strip()
            if line != "":
                lines.append(line)
    if len(lines) != 2:
        raise ValueError("Invalid key file. Please specify a file with your consumer key in the first line and the consumer secret in the second line. The file should not contain anything else.")
    CONSUMER_KEY, CONSUMER_SECRET = lines
            

def get_students(students_file, session):
    if students_file is not None:
        students = []
        with open(students_file, 'r') as infile:
            for line in infile:
                if line.strip() == "":
                    continue
                parts = line.strip().split('\t')
                #print(parts)
                if len(parts) == 2:
                    nickname, userid = parts
                    student_id = ' '*7
                elif len(parts) == 3:
                    nickname, userid, student_id = parts
                else:
                    raise ValueError("Corrupt students file. Need syntax 'name' tab kahn id (tab student_id)")
                
                students.append( {'nickname' : nickname, 'user_id' : userid, 'student_id' : student_id })
    else:
        students = get_students_from_server(session)
    return students

def get_exercise_list(exercise_file):
    exercises = []
    with open(exercise_file, 'r') as infile:
        for line in infile:
            parts = [s.strip() for s in line.strip().split('\t')]
            parts = parts if len(parts)==2 else parts + ['']
            display_name, internal_name = parts
            exercises.append([display_name, internal_name])
    return exercises

def get_students_from_server(session):
    students_json = get_api_resource(session, '/api/v1/user/students')
    students = json.loads(students_json)
    return students

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--print-students", default=False, action="store_true")
    parser.add_argument("--keys", help="A file containing the consumer key in the first line and the consumer secret in the second line")
    parser.add_argument("--students", help="A tab separated list of student nicknames and user ids. [Default] get students from server.")
    parser.add_argument("--exercises", help="Tab separated list of excersices display names and exercise internal names")
    args = parser.parse_args()

    if any([s == "" for s in [CONSUMER_KEY, CONSUMER_SECRET]]):
        #print("No keys specified or key missing. Trying to get them from a file")
        if args.keys is None:
            print("Missing keys and key file not specified. Please define keys in the code or pass a key file with --keys")
            return
        else:
            load_keyfile(args.keys)
    
    session = init_server(CONSUMER_KEY, CONSUMER_SECRET, SERVER_URL)
    # resource_url = input("Resource relative url (e.g. %s): " % DEFAULT_API_RESOURCE) or DEFAULT_API_RESOURCE

    if args.print_students:
        students = get_students_from_server(session)
        for st in students:
            name = st['nickname']
            userid = st['user_id']
            print("{}\t{}".format(name, userid))
        return

    students = get_students(args.students, session)
    exercises2do = get_exercise_list(args.exercises)
    exercises2do_display = [ex[0] for ex in exercises2do]
    exercises2do_internal = [ex[1] for ex in exercises2do]

    #print(exercises2do_display)
    #print(exercises2do_internal)

    students_achievements = []
    
    for st in students:
    # Select a student
        user_id = st['user_id']        
        nickname = st['nickname']
    
        exercises_json = get_api_resource(
            session, '/api/v1/user/exercises?userId={}'.format(user_id))
        exercises = json.loads(exercises_json)

        #print(nickname)
        total_points = 0

        achieved = {}
        
        for ex in exercises:
            internal_name = ex['exercise']
            display_name = ex['exercise_model']['display_name']
            #readable_id = ex['exercise_model']['readable_id']

            #print(internal_name, display_name)
            
            if internal_name in exercises2do_internal or display_name in exercises2do_display:
                progress = ex['exercise_progress']
                if progress['mastered']:
                    points = 2
                elif progress['practiced']:
                    points = 1
                else:
                    points = 0
                #print("{} : {}".format(display_name, points))

                achieved[display_name] = points
        
        students_achievements.append(achieved)

    # print a table with the exercises and points respectively
    for n,ex in enumerate(exercises2do_display):
        print("# {}\t{}".format(n+1, ex))
    print("# Student Name\tid     \ttot\t{}".format("\t".join(["{}".format(n) for n in range(1,len(exercises2do)+1)])))
    for st, achieved in zip(students, students_achievements):
        # get a list of points for all exercises which are to be done
        points = [achieved[ex] if ex in achieved else 0 for ex in exercises2do_display]
        tot = sum(points)
        print("{}\t{}\t{}\t{}".format(st['nickname'], st['student_id'], tot, "\t".join(["{}".format(n) for n in points])))

if __name__ == "__main__":
    main()