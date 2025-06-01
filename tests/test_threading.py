import threading


class Worker:
    def __init__(self, data):
        self.data = data

    def thread_task(self):
        self.data += 1

    def start(self):
        thread = threading.Thread(target=self.thread_task)
        thread.start()
        thread.join()

    def print(self):
        print(self.data)


# 使用示例
worker = Worker(0)
worker.start()
worker.print()