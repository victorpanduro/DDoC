<img src="icon/ddoc-icon.png" width="400" alt="DDoC logo">

# Daily Dose of Cosmos

A very simple desktop GUI for the NASA Astronomy Picture of the Day (APOD) API, made using Tkinter/TCL for Python. This is my first hobby project, tinkering with GUI applications, backend functionality, and HTTP request handling. The project was started to challenge myself, and just try to create something for fun, aimed at my always ongoing love for the great beyond, and computer science.

## Download, install dependencies, and compile application

Python 3.12 or newer is needed for the app to compile and run.

Download the repository to your machine and navigate to the repository root directory in your terminal. <br>
From here you can install dependencies with the command:

~~~ps
pip install -r requirements.txt
~~~

To compile the application, navigate to the *src* directory, and run the command:

~~~ ps
python -m compileall .
~~~

To start the app, run the command:

~~~ ps
python main.py
~~~

## Instructions of use

**API key:** <br>
For optimal usage of the NASA APOD API, I recommend you visit [NASA's](https://api.nasa.gov/) website and get a personal generated API key. If this is not of interest, NASA provides 'DEMO_KEY' for limited use.

If you use your own API key, it will be stored locally in *private/.env*, which will be created during run-time. This will be stored indefinitely (if not deleted manually) so do not be alarmed when your key appears on start-up, as it is fetched from your local environment variables.

**Date:** <br>
If no date is entered into the date entry field, the app will default to fetch today's APOD entry.

## Copyright

My application retrieves content from the NASA APOD API, and rights/credits to images/text lie with NASA or the stated authors.

It is therefore only the code for the project that is [licensed](LICENSE) under me.
