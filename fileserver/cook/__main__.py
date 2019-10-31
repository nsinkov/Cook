#!/usr/bin/env python3
"""Module implementing a file server to serve Cook job logs. """

import logging
import os.path
import sys

from logging.handlers import RotatingFileHandler
from flask import Flask, jsonify, request, send_from_directory

app = Flask(__name__)

def main(args=None):
    if args is None:
        args = sys.argv[1:]
    try:
        print(sys.version)
        handler = RotatingFileHandler('foo.log', maxBytes=10000, backupCount=1)
        handler.setLevel(logging.INFO)
        app.logger.addHandler(handler)
        #app.use_x_sendfile = True
        app.run()
        #result = run(args)
        #sys.exit(result)
    except Exception as e:
        logging.exception('exception when running with %s' % args)
        #print_error(str(e))
        sys.exit(1)

@app.route('/files/download/')
def download():
    path = request.args.get('path')
    if path is None:
        return "ERROR: No path given", 400
    print(path)
    return send_from_directory(os.path.dirname(os.path.realpath(__file__)), path, as_attachment=True)

@app.route('/files/read/')
def read():
    path = request.args.get('path')
    offset = request.args.get('offset', default = 0, type = int)
    length = request.args.get('length', type = int)
    if path is None:
        return "ERROR: No path given", 400
    file_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), path)
    if not os.path.exists(file_path):
        return "ERROR: File {path} not found".format(path=path), 404
    print(path)
    print(offset)
    print(length)
    f = open(file_path)
    f.seek(offset)
    data = f.read() if length is None else f.read(length)
    f.close()
    return jsonify({
        "data": data,
        "length": len(data),
        "offset": offset,
    })

if __name__ == '__main__':
    main()
