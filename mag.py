import socketio
from wikipedia import wikipedia
from tinydb import TinyDB, Query

import json
import random
from typing import Callable

# todo: make it async
sio = socketio.Client()
NAME = '[magpy]'
PREFIX = '$'
ROOM = 'ayoteyo'

with open('jokes.json') as f:
	jokes = json.load(f)

todos_db = TinyDB('db.json')
Todo = Query()

class CommandDispatcher:
	def __init__(self):
		self._cmds = {"help": {'fn': self.help, 'doc':self.help.__doc__}}

	def command(self, name: str) -> Callable:

		def decorator(handler: Callable) -> Callable:
			self._cmds[name]={}
			self._cmds[name].update({
				'fn': handler,
				'doc': handler.__doc__,
			})
			return handler

		return decorator

	# def command(self, fn):
	# 	self._cmds[name] = {}
	# 	self._cmds[name]['fn'] = func
	# 	self._cmds[name]['doc'] = func.__doc__

	def dispatch(self, name):
		if self._cmds.get(name, None) is not None:
			return self._cmds.get(name)['fn']
		else:
			return self._cmds['help']['fn']

	def help(self, sio, args, data):
		'''
		Tells you about my features
		'''
		hstr = ""
		for cmd in self._cmds:
			hstr+='-	'+cmd+'\n'
			hstr+='		'+str(self._cmds[cmd].get('doc',' '))+'\n'
		send_msg(sio, hstr, data)

def send_msg(sio, text, data): # a helper fn
	sio.emit('chatMessage', {
			'room': ROOM,
			'time': data['time'],
			'username':NAME,
			'text': text
	})

dis = CommandDispatcher()

@dis.command('joke')
def joke(sio, args, data):
	'''
		Tells a random joke. Attempts to be unfunny.
		Can be used like $joke <allowed joke types>.
		eg: $joke dad general
		Joke type can be 'dad', 'general', 'programming' or 'knock-knock'
	'''
	if len(args)<2:
		joke_filter = lambda x: True
	else:
		joke_filter = lambda x: x.get('type') in set(args[1:])

	joke = random.choice(list(filter(joke_filter, jokes)))

	
	send_msg(sio, f"{joke['setup']}\n***{joke['punchline']}***", data)
	
@dis.command('wiki')
def wiki(sio, args, data):
	'''
		Searches Wikipedia.
	'''
	if len(args)<2:
		text = 'Use it as $wiki <stuff u wanna search>'
	else:
		send_msg(sio,"Searching... Takes a few seconds", data)
		try:
			text =str(wikipedia.summary(args[1]))['summary']
		except Exception as e:
			text = 'No results'
	send_msg(sio, text, data)

@dis.command('todo')
def todo(sio, args, data):
	'''
		Your personal to-do list.
		Options:
			*add*, *done*, *show*, *help*
	'''
	helpstr = '''
		add - $todo add <task> <optional deadline>
		done - $todo done <taskid1> <taskid2> ...
		show - $todo show
		help - $todo help
	'''
	if len(args)<2:
		send_msg(sio, helpstr, data)
	elif args[1].lower() == 'add' and len(args)>=4:
		# $todo add eat 24/10/2024
		id_ = todos_db.insert({
			'task': args[2], 
			'deadline': args[3], 
			'user': data['username'],
			'status': 'Pending'
		})
		send_msg(sio, f'todo: **{args[2]}** added. \n Due by `{args[3]}` \n ID: {id_}', data)
	elif args[1].lower()=='add' and len(args)>=3:
		id_ = todos_db.insert({
			'task': args[2], 
			'deadline': 'Indefinite', 
			'user': data['username'],
			'status': 'Pending'
		})
		send_msg(sio, f'todo: **{args[2]}** added. \n No due date. \n ID: {id_}',data)
	elif args[1].lower()=='add': # invalid args case here
		send_msg(sio, 'use it as `$todo add <task> <deadline>',data)
	elif args[1].lower()=='done' and len(args)<=2:
		send_msg(sio, 'Which work is done?\n \
			specify with `$todo done <taskid> <taskid2>` where taskids are tasks you completed\
			\n You can find your task id by `$todo show`', data)
	elif args[1].lower()=='done' and len(args)>=3:
		try:
			todos_db.update({'status': 'Done'}, Todo.user==data['username'], doc_ids=[int(x) for x in args[2:]])
			send_msg(sio, 'Congratulations on the completions. Yaaay!!', data)
			msg='\n'
			for x in todos_db.search(Todo.user==data['username']):
				msg+=f"**Task:{x['task']}**\n\n------\n\n Deadline: {x['deadline']}\n\n Status: {x['status']}\n\n ID:{x.doc_id}\n\n\n"
			send_msg(sio, msg, data)
		except Exception as e:
			print(e)
			send_msg(sio, 'Something went boogie woogie. Couldn\'t do it', data)
	elif args[1].lower()=='show':
		msg = '\n'
		for x in todos_db.search(Todo.user==data['username']):
			msg+=f"**Task: {x['task']}**\n\n------\n\n Deadline: {x['deadline']}\n\n Status: {x['status']}\n\n ID: {x.doc_id}\n\n\n"
		if msg=='\n':
			msg = "empty :("
		send_msg(sio, msg, data)
	elif args[1].lower()=='clear':
		send_msg(sio, 'clearing your list', data)
		todos_db.remove(Todo.user==data['username'])
	else:
		send_msg(sio, helpstr, data)


def do_work(sio, data):
	if not data['text'].startswith(PREFIX):
		return # not intended for bot
	args = data['text'].split()
	command = args[0][1:]
	print(command)
	dis.dispatch(
		command,
	)(sio,args,data)


@sio.event
def connect():
	sio.emit('joinR', {'username': NAME, 'room': ROOM})
	print('connected')

@sio.event
def message(data):
	print('message!')
	print('message: '+str(data))
	do_work(sio, data)


sio.connect('https://magnolia.re-masashi.repl.co')
sio.wait()