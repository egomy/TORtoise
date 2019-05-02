import requests
import os
import threading

from stem import Signal
from stem.control import Controller
from bs4 import BeautifulSoup

""" Initiate Elasticsearch """

from datetime import datetime
from elasticsearch import Elasticsearch
es = Elasticsearch([{'host': 'localhost', 'port': 9200}])

session = requests.session()
session.proxies['http'] = 'socks5h://localhost:9050'
session.proxies['https'] = 'socks5h://localhost:9050'

stored_list = []
scanning_list = []

"""FUNCTIONS TO CHANGE TOR IDENTITIES"""


def renew_tor_ip():
    with Controller.from_port(port=9051) as controller:
        controller.authenticate(password="root")
        controller.signal(Signal.NEWNYM)
    print("Current IP address is %s" % get_current_ip())


def get_current_ip():
    session = requests.session()

    # TO Request URL with SOCKS over TOR
    session.proxies = {}
    session.proxies['http'] = 'socks5h://localhost:9050'
    session.proxies['https'] = 'socks5h://localhost:9050'

    try:
        r = session.get('http://httpbin.org/ip')
    except Exception as e:
        print(str(e))
    else:
        return r.text


"""ALL ELASTICSEARCH OPERATION FUNCTIONS"""

def retrieve_es():
    es_list = []
    count = 0
    s1 = {
        'size': 10000,
        "query":
              {
                  "match_all": {}
              }
          }

    try:
        all_es = es.search(index='onions', doc_type='up', body=s1)

        es_rec = all_es['hits']['hits']

        while count < len(es_rec):
            print(es_rec[count]['_source']['url'])
            es_list.append(es_rec[count]['_source']['url'])
            count += 1

    except Exception as e:
        print("[!!] No records in ES")

    return es_list


def add_to_es(url, title, status):

    now = datetime.now()
    date_time = now.strftime("%d/%m/%Y, %H:%M:%S")

    e1 = {"first_crawl_date_time": date_time,
            "title": title,
                "url": url,
                "status": status
               }

    es.index(index='onions', doc_type='up', body=e1, ignore=(400,409))
    print("[**]Link added to ES: %s." % url)


def update_es_link(url, title, status):
    now = datetime.now()
    date_time = now.strftime("%d/%m/%Y, %H:%M:%S")

    e1 = {
        "script": {
            "inline": "ctx._source.last_crawl_date_time = '%s'; ctx._source.status = '%s'; ctx._source.title = '%s'" % (date_time, status, title),
            "lang": "painless"
            }
        , "query": {
            "match": {
                "url": url}
               }
        }
    print("Updating ES link for %s with query %s" % (url, e1))
    es.update_by_query(index='onions', doc_type='up', body=e1, ignore=(400, 500, 409))
    print("[**]Link updated in ES: %s." % url)


"""ALL ONION OPERATION FUNCTIONS"""


def get_onion_list():
    # open the master list

    if os.path.exists("mega_list.txt"):

        with open("mega_list.txt", "rb") as fd:

            s_onions = fd.read().splitlines()
    else:
        print("[!!] No new onions from file.")
        s_onions = []
        return s_onions

    print("[*] Total new onions for scanning: %d" % len(s_onions))

    return s_onions


def clean_onion(onion):

    if ".." in onion:
        onion = onion.replace("..", ".")
        

    s_url = onion.split(".")
    s_count = len(s_url)

    if s_count > 2:
        print("[!] Need to clean URL")
        onion = s_url[s_count - 2] + "." + s_url[s_count - 1]
        print("[*] URL after cleaning: %s" % onion)
        return onion
    else:
        return onion


def check_onion(onion):
    if onion in stored_list:
        return True
    else:
        return False


def extract_onions(soup):
    global scanning_list

    links = soup.find_all('a')

    for tag in links:
        link = tag.get('href', None)

        if link is not None:
            if ".onion" in link and "=" not in link:
                if "http://" in link or "https://" in link:
                    link = link.split('/')[2]
                    if link not in scanning_list:
                        scanning_list.append(link)
                        print("[**]Added new link to scan: %s. Total links to scan is %s" % (link, len(scanning_list)))


def scan_onion(onion):

    global onion_list
    global session

    onion = clean_onion(onion)

    try:
        if "http://" in onion or "https://" in onion:
            response = session.get(onion)
        else:
            response = session.get("http://%s" % onion)

    except requests.exceptions.RequestException as e:
        print('[!!]Request Timed Out!')

        if not check_onion(onion):
            add_to_es(onion, "Site offline", "offline")
            stored_list.append(onion)
        else:
            update_es_link(onion, "Site offline", "offline")
        return
    else:

        soup = BeautifulSoup(response.content, features="lxml")

        if soup.find('title') is not None:
            otitle = (soup.find('title')).getText()
        else:
            otitle = "No Title"

        print("[*]Scanning %s - %s" % (onion, otitle))

        if not check_onion(onion):
            add_to_es(onion, otitle, "online")
            stored_list.append(onion)
        else:
            update_es_link(onion, otitle, "online")

        extract_onions(soup)


"""MAIN OPERATIONS"""

stored_list = retrieve_es()
scanning_list = get_onion_list()
scanning_list = scanning_list + stored_list


if scanning_list != []:

    count = 0
    t_count = 0
    circuit_count = 0
    t_list = []

    while count < len(scanning_list):
        print("Scanning %s of %s - %s" % (count, len(scanning_list), scanning_list[count]))

        for i in range(5):
            if count < len(scanning_list):
                t = threading.Thread(target=scan_onion, args=(scanning_list[count],))
                count += 1
                t_count += 1
                t_list.append(t)
                print("[*] Added Thread %s" % t_count)
            else:
                break

        for t in t_list:
            t.start()
            print("[*] Thread Started!")

        for t in t_list:
            t.join()
            circuit_count += 1

        if circuit_count > 50:
            renew_tor_ip()
            circuit_count = 0

        t_count = 0
        t_list = []
else:
    print("Please provide list of onions in new_onion.txt")