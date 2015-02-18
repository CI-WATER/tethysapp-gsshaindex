####################################################################
#
#	Timeout Function Definitions
#
####################################################################

def timeout(func, args=(), kwargs={}, timeout=1, default=None, result_can_be_pickled=True):
	"""
	a wrapper function that allows a timeout to be set for the given function (func)

	arg: func - a function to be executed with timeout
	arg: args - a tuple of arguments for func
	arg: kwargs - a dictionary of key-word arguments for func
	arg: timeout - the amount of time in second to wait for func before timeing out
	arg: default - the value to return if func timesout before completing
	arg: result_can_be_pickled - boolean stating weather the result of func is picklable (default=True)

	return: the return value from func or default
	"""	
	if result_can_be_pickled:
		from multiprocessing import Process, Manager
		import thread
		class TimedProcess(Process):
			def __init__(self, l):
				super(TimedProcess, self).__init__()
				self.list = l

			def run(self):
				try:
					result = func(*args, **kwargs)
					self.list.append(result)
				except Exception as e:
					self.list.append(e)
		
		mng = Manager()
		l = mng.list()
		p = TimedProcess(l)
		p.start()
		p.join(timeout)
		if p.is_alive():
			p.terminate()
			return default
		else:
			return l[0]
	else:
		import time #, KeyboardInterrupt

		
		try:
			import thread as _thread
			import threading as _threading
		except ImportError:
			import dummy_thread as _thread
			import dummy_threading as _threading
			pass
		
		start = time.time() 

		def interrupt():
			print 'interrupting ', time.time() - start
			_thread.interrupt_main()

		result = default
		try:
			t = _threading.Timer(timeout, interrupt)
			t.start()
			start = time.time()
			result = func(*args, **kwargs)
			t.cancel()
		except KeyboardInterrupt as e:
			pass
		return result


def set_timeout(timeout_wait, default=None, result_can_be_pickled=True):
	"""
	a decorator for the timeout function above

	USAGE:  @set_timeout(1, None)
			def func():
				. . .

	arg: timeout_wait - the amount of time in second to wait for function to complete
	arg: default - the return value of the function if the function times out before completing
	"""
	def decorator(function):
		def function_wrapper(*args, **kwargs):
			return timeout(function, args=args, kwargs=kwargs, 
				timeout=timeout_wait, default=default, 
				result_can_be_pickled=result_can_be_pickled)
		return function_wrapper
	return decorator


####################################################################
#
#	Test Code
#
####################################################################

pickle = True

class Num(object):
	def __init__(self, num):
		from multiprocessing import Pipe
		self.num = num
		if not pickle:
			self.i, self.o = Pipe()
	def __str__(self):
		return str(self.num)

def sum_range(upper, lower=0):
    result=0
    for i in range(lower,upper):
        result += i
    num = Num(result)
    return num

@set_timeout(3, -1, pickle)
def sum_range_2(upper, lower=0):
	return sum_range(upper, lower)
import time
start = time.time()
print sum_range_2(10), 'time: %s' % (time.time() - start, )
start = time.time()
print sum_range_2(10**9), 'time: %s' % (time.time() - start, )
start = time.time()
# print sum_range(10**9), 'time: %s' % (time.time() - start, )

start = time.time()
print timeout(sum_range, args=(10,5), result_can_be_pickled=pickle), 'time: %s' % (time.time() - start, )
start = time.time()
print timeout(sum_range, (10**10,), kwargs={}, timeout=.1, default=None, result_can_be_pickled=pickle), 'time: %s' % (time.time() - start, )

def count_to_infinity():
	import time
	i = 0
	start = time.time()
	while True:
		print i, 'time: %s' % (time.time() - start, )
		for j in range(1000):
			j*i
		i += 1

# timeout(count_to_infinity, timeout=.001)
# print timeout(sum_range, args=(100000,), timeout = 1)