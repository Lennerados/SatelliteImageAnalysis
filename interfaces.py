import queue
from threading import Lock, Thread
from datetime import date

class WorkerThread:
	def __init__(self, dispatcher, data):
		self.dispatcher = dispatcher
		self.data = data

	def run(self, dispatcher):
		raise NotImplementedError


class Node:
	def finishPipeline(self):
		# Creates the needed queue
		if(hasattr(self, "succesor")):
			self.queue = queue.Queue()
			self.succesor.finishPipeline()
			# Lock is used for the update method
			self.updateLock = Lock()

	def empty(self):
		return self.queue.empty()

	def addData(self, data, firstTime = False):
		# Adds the data in the queue behind the dispatcher
		# TODO: Better multithreaded support (start this method in a new thread)
		# especially since update needs a lock
		if(hasattr(self, "succesor")):
			self.queue.put(data)
			if(not firstTime):
				Thread(target=self.succesor.update).start()

	def getData(self):
		if(hasattr(self, "succesor")):
			return self.queue.get()
		else:
			raise AttributeError("No Queue found")


class Source(Node):
	def finish(self):
		self.finishPipeline()
	
	def start(self):
		# Starts the program by calling the update method of the first dispatcher
		self.succesor.update()

	""" Needed for the Dispatcher to decide, if it is an input or an output """
	def checkSource(self):
		pass


class Dispatcher(Node):
	def __init__(self):
		# maxThreads = -1 => No checking
		# maxThreads set to 200
		self.maxThreads = 200
		self.threadCount = 0
		self.threadCountLock = Lock()
		self.initialize()

	def initialize(self):
		pass

	""" Default update method: Starts a new Thread, whenever there is new data """
	def update(self):
		# Checks if there is data in the queue
		while(True):
			self.source.updateLock.acquire()
			self.threadCountLock.acquire()
			if(self.source.empty() or (self.maxThreads > -1 and self.threadCount >= self.maxThreads)):
				self.threadCountLock.release()
				self.source.updateLock.release()
				break
			d = self.source.getData()
			self.source.updateLock.release()
			self.threadCount += 1
			self.threadCountLock.release()
			# Starting new thread
			thread = self.getWorkerThread(d)
			Thread(target=self.startThread, args=[thread]).start()

	def getWorkerThread(self, data):
		raise NotImplementedError

	def connect(self, connecter):
		try:
			connecter.checkSource()
			# It is a source so it goes in front of this dispatcher
			self.source = connecter
			connecter.succesor = self
		except:
			# It is coming behind this dispatcher with a queue
			self.succesor = connecter
			connecter.source = self
	
	def startThread(self, thread):
		t = Thread(target=thread.run)
		t.start()
		# Let's wait until the thread is finished
		t.join()
		self.threadCountLock.acquire()
		self.threadCount -= 1
		self.threadCountLock.release()
		self.update()
