import threading

class WorkerTask(object):
    """A task to be performed by the ThreadPool."""

    def __init__(self, function, args=(), kwargs={}):
        self.function = function
        self.args = args
        self.kwargs = kwargs

    def __call__(self):
        self.function(*self.args, **self.kwargs)

class WorkerThread(threading.Thread):
    """A thread managed by a thread pool."""

    def __init__(self, pool):
        threading.Thread.__init__(self)
        self.daemon = True
        self.pool = pool
        self.busy = False
        self._started = False
        self._event = None

    def work(self):
        if self._started is True:
            if self._event is not None:
                self._event.set()
        else:
            self._started = True
            self.start()

    def run(self):
        self.busy = True
        while len(self.pool._tasks) > 0:
            try:
                task = self.pool._tasks.pop()
                task()
            except IndexError:
                # Just in case another thread grabbed the task 1st.
                pass

        # Sleep until needed again
        self.busy = False 
        self._event = threading.Event()
        self._event.wait()
        self.run()

class ThreadPool(object):
    """Executes queued tasks in the background."""

    def __init__(self, max_pool_size=10):
        self.max_pool_size = max_pool_size
        self._threads = []
        self._tasks = [] 

    def _addTask(self, task):
        self._tasks.append(task)

        worker_thread = None
        for thread in self._threads:
            if thread.busy is False:
                worker_thread = thread
                break

        if worker_thread is None and len(self._threads) < self.max_pool_size:
            worker_thread = WorkerThread(self)
            self._threads.append(worker_thread)

        worker_thread.work()

    def addTask(self, function, args=(), kwargs={}):
        self._addTask(WorkerTask(function, args, kwargs))

class GlobalThreadPool(object):
    """ThreadPool Singleton class."""

    _instance = None

    def __init__(self):
        """Create singleton instance """

        if GlobalThreadPool._instance is None:
            # Create and remember instance
            GlobalThreadPool._instance = ThreadPool()

    def __getattr__(self, attr):
        """ Delegate get access to implementation """
        return getattr(self._instance, attr)

    def __setattr__(self, attr, val):
        """ Delegate set access to implementation """
        return setattr(self._instance, attr, val)
