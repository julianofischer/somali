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
from java.io import File
from java.io import StringReader
from java.lang import System
from org.apache.lucene.store import SimpleFSDirectory
from org.apache.lucene.document import Document, Field, StringField, TextField
from org.apache.lucene.index import IndexWriter
from org.apache.lucene.index import IndexWriterConfig
from org.apache.lucene.search import IndexSearcher
from org.apache.lucene.index import DirectoryReader
from org.apache.lucene.index import IndexReader
from org.apache.lucene.analysis.standard import StandardAnalyzer
from org.apache.lucene.util import Version
from org.apache.lucene.queryparser.classic import QueryParser
from org.apache.lucene.search.highlight import Highlighter
from org.apache.lucene.search.highlight import QueryScorer
from org.apache.lucene.search.highlight import SimpleHTMLFormatter
from org.apache.lucene.search.highlight import SimpleSpanFragmenter

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
    analyzer = StandardAnalyzer(Version.LUCENE_48)
    index_writer_config = IndexWriterConfig(Version.LUCENE_48, analyzer);
    index_writer = IndexWriter(dir, index_writer_config)

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
    print index_writer.numDocs()
    index_writer.close()


def lucene_search(query, MAX, showHighlight):
    dir = os.getcwd()
    lucene.initVM()
    index_dir = SimpleFSDirectory(File(dir))
    index_reader = DirectoryReader.open(index_dir)
    lucene_searcher = IndexSearcher(index_reader)
    lucene_analyzer = StandardAnalyzer(Version.LUCENE_48)
    my_query = QueryParser(Version.LUCENE_48, "text",
                           lucene_analyzer).parse(query)
    #We can define the MAX number of results (default 10)
    total_hits = lucene_searcher.search(my_query, MAX)

    query_scorer = QueryScorer(my_query)
    formatter = SimpleHTMLFormatter()
    highlighter = Highlighter(formatter, query_scorer)
    # Set the fragment size. We break text in to fragment of 50 characters
    fragmenter = SimpleSpanFragmenter(query_scorer, 50)
    highlighter.setTextFragmenter(fragmenter)

    print "Only shows at most %s documents" % MAX
    if showHighlight:
        print "<br>"

    for hit in total_hits.scoreDocs:

        doc = lucene_searcher.doc(hit.doc)
        text = doc.get("text")
        ts = lucene_analyzer.tokenStream("text", StringReader(text))
        
        if showHighlight:
            print "<p>"

        print doc.get("title")

        if showHighlight:
            print "<br>"
            print highlighter.getBestFragments(ts, text, 3, "...")
            print "</p>"

def main():
    parse = argparse.ArgumentParser()
    parse.add_argument("-update", help="Update the archive by\
        downloading the last monthly entries", action='store_true')
    parse.add_argument("-query", help="The query", required=True)
    parse.add_argument("-maxresults", metavar='N', type=int, 
        help='an integer for the max number of results to show')
    parse.add_argument("-highlight", action='store_true',
        help='show the highlighted query in context with html format')

    args = parse.parse_args(sys.argv[1:])

    createDB()

    showHighlighted = False
    if args.highlight:
        showHighlighted = True

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
    elif (args.query and args.maxresults):
        lucene_search(args.query, args.maxresults, showHighlighted)
    elif args.query:
        lucene_search(args.query, 10, showHighlighted)

if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        msg = "Exception occured in main: "+str(type(exc)) +\
        "  args:"+str(exc)+" line:"+str(exc_tb.tb_lineno)
        print msg