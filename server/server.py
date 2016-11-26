#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
import os
import uuid
import threading

from datetime import datetime
import eventlet
from flask import Flask, send_from_directory, session, request
from flask_socketio import SocketIO, emit
from system import Pipeline
from dialogue.manager import DialogueTurn

app = Flask(__name__)
app.secret_key = uuid.uuid4()
socketio = SocketIO(app, ping_timeout=30)


class DialogueSession:
    def __init__(self, id: str):
        self.id = id
        self.started = str(datetime.now())
        self.ended = ""
        self.system = Pipeline()

    def json(self) -> object:
        return {
            "started": str(self.started),
            "ended": str(self.ended),
            "session_id" : self.id,
            "turns": list(map(lambda turn: {
                "type": turn.type,
                "data": str(turn.data),
                "time": str(turn.time)
            }, self.system.manager.interaction_sequence))
        }


sessions = {}


@app.route('/static/<path:path>')
def send_js(path):
    return send_from_directory('static', path)


@app.route('/')
def hello():
    return app.send_static_file('index.html')


@socketio.on('message')
def socket_message(message):
    print('Session:', request.sid)
    if request.sid not in sessions:
        sessions[request.sid] = DialogueSession(request.sid)
    query = message["query"]
    sessions[request.sid].system.manager.interaction_sequence.append(DialogueTurn("input", query, datetime.now()))
    for output in sessions[request.sid].system.input(query):
        if isinstance(output, str):
            emit('message', {
                'type': 'progress',
                'lines': [output]
            })
        else:
            emit('message', {
                'type': output.output_type.name,
                'lines': output.lines
            })
            sessions[request.sid].system.manager.interaction_sequence.append(DialogueTurn("output", {
                'type': output.output_type.name,
                'lines': output.lines
            }, datetime.now()))
        emit('state', sessions[request.sid].system.user_state())
        eventlet.sleep(0)


@socketio.on('my broadcast event')
def socket_message(message):
    emit('message', {'data': message['data']}, broadcast=True)


@socketio.on('connect')
def socket_connect():
    print('Session:', request.sid)
    sessions[request.sid] = DialogueSession(request.sid)
    for output in sessions[request.sid].system.output():
        emit('message', {
            'type': output.output_type.name,
            'lines': output.lines
        })
    emit('state', sessions[request.sid].system.user_state())
    print("New user connected")


def save_log(session_data):
    if not "turns" in session_data or len(session_data["turns"]) <= 1:
        return
    # save log
    filename = "log-%s.json" % str(datetime.now().date())
    session_log = None
    if os.path.isfile(filename):
        session_log = json.load(open(filename, "r"))
    if session_log is None or "sessions" not in session_log:
        session_log = {"sessions": []}

    session_log["sessions"].append(session_data)
    json.dump(session_log, open(filename, "w"), indent=4)


@socketio.on('disconnect')
def socket_disconnect():
    sessions[request.sid].ended = str(datetime.now())
    print('User disconnected')

    try:
        session_data = sessions[request.sid].json()
        del sessions[request.sid]
        thr = threading.Thread(target=save_log, args=[session_data], kwargs={})
        thr.start()
        print("Saved log for session %s." % request.sid)
        #  save_log(session_data)
    except:
        pass


if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000)
