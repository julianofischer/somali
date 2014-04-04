# !/usr/bin/python
# encoding: utf-8
# author: Juliano Fischer Naves
# contact: julianofischer at gmail dot com
import sys
import os
import glob
import getpass
from datetime import datetime
import requests
import sqlite3
import argparse
from BeautifulSoup import BeautifulSoup
import lucene
from lucene import SimpleFSDirectory, System, File, Document, Field,\
    StandardAnalyzer, IndexWriter, Version, IndexSearcher, QueryParser

db_filename = 'one.db'
db_schema = """create table if not exists monthly_archive (
                     id integer primary key autoincrement,
                     link text)
"""


# class: representing a connection with the DB
# filename: the file used by sqlite3

class DBConnection(object):
    def __init__(self):
        self.filename = db_filename

    def get_connection(self):
        return sqlite3.connect(self.filename)


class MonthlyArchive:

    def __init__(self, link):
            self.link = link

    def __repr__(self):
        return '[Doc id: %d - :%s]' % (self.id, self.link)


class MonthlyArchiveDAO(object):
    SQL_SELECT = "SELECT * FROM monthly_archive WHERE link='%s'"
    SQL_INSERT = "INSERT INTO monthly_archive (link) VALUES ('%s')"

    def __init__(self):
        self.db_connection = DBConnection()

    # Checks if the entry is already in the DB
    # returns True if the entry is already in DB
    # returns False otherwise
    def is_in_db(self, monthly_archive):
        with self.db_connection.get_connection() as conn:
            cur = conn.cursor()
            cur.execute(MonthlyArchiveDAO.SQL_SELECT % monthly_archive.link)
            rows = cur.fetchall()
            return bool(rows)

    # insert an entry in DB
    def insert(self, monthly_archive):
        with self.db_connection.get_connection() as conn:
            cur = conn.cursor()
            cur.execute(self.SQL_INSERT % (monthly_archive.link))
            conn.commit()


# create a DB if not exists
def createDB():
    db_is_new = not os.path.exists(db_filename)
    if db_is_new:
        with sqlite3.connect(db_filename) as conn:
            conn.execute(db_schema)


def successfully_logged(req):
    if req.text.find('Authentication') == -1:
        return True
    return False


def do_login():
    username = raw_input('Enter your registered e-mail\n')
    password = getpass.getpass('Enter your password\n')
    data = {'username': username, 'password': password}

    r = requests.post('https://www.netlab.tkk.fi/mailman/private/theone/',
                      data=data, verify=False)
    return r


# returns the monthly entries
def retrieve_monthly_archives(r):
    soup = BeautifulSoup(r.text)
    lista = soup.findAll("td")
    new_list = []

    for td in lista:
        all_a = td.findAll("a")
        for a in all_a:
            if a["href"].find("txt") != -1:
                new_list.append(MonthlyArchive(a["href"]))
    return new_list


# download a monthly archive entry
def downloadDocument(monthly_archive, r):
    link = "https://www.netlab.tkk.fi/mailman/private/theone/"
    link += monthly_archive.link
    req = requests.get(link, verify=False, cookies=r.cookies)
    file = monthly_archive.link.split('.gz')[0]

    with open(file, 'w') as new_file:
        new_file.write(req.text.encode('utf-8'))


def lucene_indexing():
    lucene.initVM()
    index_dir = os.getcwd()
    dir = SimpleFSDirectory(File(index_dir))
    analyzer = StandardAnalyzer(lucene.Version.LUCENE_CURRENT)

    index_writer = lucene.IndexWriter(
        dir, analyzer, True,
        lucene.IndexWriter.MaxFieldLength.LIMITED
    )

    for tfile in glob.glob(os.path.join(index_dir, '*.txt')):
        print "Indexing: ", tfile
        document = Document()
        with open(tfile, 'r') as f:
            content = f.read()
        document.add(Field("text", content, Field.Store.YES,
                           Field.Index.ANALYZED))
        document.add(Field("title", tfile, Field.Store.YES,
                           Field.Index.ANALYZED))
        index_writer.addDocument(document)

    index_writer.optimize()
    print index_writer.numDocs()
    index_writer.close()


def lucene_search(query):
    dir = os.getcwd()
    lucene.initVM()
    index_dir = SimpleFSDirectory(File(dir))
    lucene_analyzer = StandardAnalyzer(lucene.Version.LUCENE_CURRENT)
    lucene_searcher = IndexSearcher(index_dir)
    my_query = QueryParser(lucene.Version.LUCENE_CURRENT, "text",
                           lucene_analyzer).parse(query)
    MAX = 10
    total_hits = lucene_searcher.search(my_query, MAX)

    for hit in total_hits.scoreDocs:
        doc = lucene_searcher.doc(hit.doc)
        print doc.get("title")


def main():
    parse = argparse.ArgumentParser()
    parse.add_argument("-update", help="Update the archive by\
        downloadig the last monthly entries", action='store_true')
    parse.add_argument("-query", help="The query", required=True)
    args = parse.parse_args(sys.argv[1:])

    createDB()

    if args.update:
        r = do_login()

        if successfully_logged(r):
            print "Login successfully..."
            entries = retrieve_monthly_archives(r)
            dao = MonthlyArchiveDAO()
            for e in entries:
                if not dao.is_in_db(e):
                    print "Downloading: %s" % e.link
                    downloadDocument(e, r)
                    dao.insert(e)
            lucene_indexing()
        else:
            print "Wrong username/password..."
    elif args.query:
        lucene_search(args.query)

if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        msg = "Exception occured in main: "+str(type(exc)) +
        "  args:"+str(exc)+" line:"+str(exc_tb.tb_lineno)
        print msg
