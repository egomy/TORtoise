import requests
import os
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

    es.index(index='onions', doc_type='up', body=e1, ignore=400)
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
    es.update_by_query(index='onions', doc_type='up', body=e1, ignore=(400, 500))
    print("[**]Link updated in ES: %s." % url)


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

        if link is not None and "onion" in link:
            link = link.split('/')[2]

            if link not in scanning_list:
                scanning_list.append(link)
                print("[**]Added new link to scan: %s. Total links to scan is %s" % (link, len(scanning_list)))


def scan_onion(onion):

    global onion_list
    global session

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
            title = soup.find('title')
        else:
            title = "No Title"

        print("[*]Scanning %s - %s" % (onion, title.getText()))

        if not check_onion(onion):
            add_to_es(onion, title.getText(), "online")
            stored_list.append(onion)
        else:
            update_es_link(onion, title.getText(), "online")

        extract_onions(soup)


stored_list = retrieve_es()
scanning_list = get_onion_list()

scanning_list = scanning_list + stored_list



if scanning_list != []:

    count = 0

    while count < len(scanning_list):
        print("Scanning %s of %s - %s" % (count, len(scanning_list), scanning_list[count]))
        scan_onion(scanning_list[count])
        count += 1
else:
    print("Please provide list of onions in new_onion.txt")