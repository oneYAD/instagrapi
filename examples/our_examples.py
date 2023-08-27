from instagrapi import Client
# great site - https://github.com/ramtinak/InstagramApiSharp/blob/master/src/InstagramApiSharp/API/InstaApiConstants.cs


cl = Client()
cl.login(ACCOUNT_USERNAME, ACCOUNT_PASSWORD)

def user_presence(cl, params={}):
    ans = cl.private_request("direct_v2/get_presence/", params={})
    up = ans['user_presence']
    l = list(map( lambda k: cl.user_info(k).username, up.keys()))

def threads_inbox(cl, params={}):
    pending = cl.private_request("direct_v2/pending_inbox/", params=params)
    inbox = cl.private_request("direct_v2/inbox/", params=params)
    return pending['inbox']['threads'], inbox['inbox']['threads']
