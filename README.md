somali
======

Searching theONE mailing list via command line.

1st use: 
python somali.py -update -query "The text you're searching."

After: 
python somali.py -query "The text you're searching."

Recommended: 
python somali.py -query "The text you're searching." -maxresults 20 -highlight > results.html



### Dependencies ###
1. BeautifulSoup 3.2.1-1
	sudo apt-get install python-beautifulsoup
2. Requests 1.2.3-1
	sudo apt-get install python-requests
3. python setuptools 1.4.1-2
	sudo apt-get install python-pip
4. PyLucene 4.8.0-1
	http://bendemott.blogspot.mx/2013/11/installing-pylucene-4-451.html (change 4.5.1 for 4.8.0-1)